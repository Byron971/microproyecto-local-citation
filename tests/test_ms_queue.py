"""Cola M/S: admisión idempotente, entregas repetidas, reinicios y estados terminales."""
import threading

import pytest

from src.app.ms_queue import (
    ClaveReutilizada, ColaLlena, EntradaInvalida, ErrorEncolado, JobService, Limites,
    MemoryJobStore, MemoryQueue, TrabajoEnCurso, Worker, trabajo_id_desde_clave,
)

CLAVE = '0f1e2d3c-4b5a-4968-8776-655443322110'
SOLICITUD = {'paper_id': 'W05-0821', 'contexto': 'Prior work TARGETCIT.', 'version_contenido': 'v1'}


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def entorno(limites=None, ejecutar=None, max_recepciones=3):
    reloj = Reloj()
    limites = limites or Limites()
    store, queue = MemoryJobStore(), MemoryQueue(clock=reloj, visibilidad_s=180,
                                                  max_recepciones=max_recepciones)
    servicio = JobService(store, queue, limites, clock=reloj)
    llamadas = []

    def predeterminado(trabajo):
        llamadas.append(trabajo['trabajo_id'])
        return {'top3': [1, 2, 3], 'paper_id': trabajo['solicitud']['paper_id']}

    worker = Worker(store, queue, ejecutar or predeterminado, limites, clock=reloj,
                    worker_id='w1', espera_recepcion_s=0)
    return reloj, store, queue, servicio, worker, llamadas


def clave(n):
    return f'{n:08d}-0000-4000-8000-000000000000'


def test_admision_devuelve_en_cola_y_el_get_nunca_infiere():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    vista, nuevo = servicio.admitir(CLAVE, SOLICITUD)
    assert nuevo and vista['estado'] == 'en_cola' and vista['trabajo_id'] == trabajo_id_desde_clave(CLAVE)
    assert vista['espera_maxima_s'] == 900 and vista['retencion_s'] == 3600
    for _ in range(5):
        assert servicio.leer(vista['trabajo_id'])['estado'] == 'en_cola'
    assert llamadas == [] and queue.pendientes() == 1
    assert worker.procesar_uno()
    final = servicio.leer(vista['trabajo_id'])
    assert final['estado'] == 'completado' and final['resultado']['top3'] == [1, 2, 3]
    assert 'solicitud' not in store.obtener(vista['trabajo_id'])  # El contexto no se retiene.
    assert llamadas == [vista['trabajo_id']] and queue.pendientes() == 0
    assert store.contar_activos() == 0


def test_doble_clic_y_reenvio_devuelven_el_mismo_trabajo_sin_otra_inferencia():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    primero, _ = servicio.admitir(CLAVE, SOLICITUD)
    segundo, nuevo = servicio.admitir(CLAVE, SOLICITUD)
    assert not nuevo and segundo['trabajo_id'] == primero['trabajo_id']
    assert queue.pendientes() == 1 and store.contar_activos() == 1
    worker.procesar_uno()
    tercero, nuevo = servicio.admitir(CLAVE, SOLICITUD)  # Reenvío tras terminar.
    assert not nuevo and tercero['estado'] == 'completado'
    assert len(llamadas) == 1


def test_clave_reutilizada_con_otra_solicitud_o_vencida_se_rechaza():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    servicio.admitir(CLAVE, SOLICITUD)
    with pytest.raises(ClaveReutilizada):
        servicio.admitir(CLAVE, {**SOLICITUD, 'contexto': 'Otra TARGETCIT.'})
    worker.procesar_uno()
    reloj.t += 3601
    with pytest.raises(ClaveReutilizada):
        servicio.admitir(CLAVE, SOLICITUD)
    with pytest.raises(ValueError):
        servicio.admitir('corta', SOLICITUD)


def test_cola_llena_rechaza_sin_registrar_y_libera_al_terminar():
    reloj, store, queue, servicio, worker, llamadas = entorno(Limites(max_activos=2))
    servicio.admitir(clave(1), SOLICITUD)
    servicio.admitir(clave(2), SOLICITUD)
    with pytest.raises(ColaLlena):
        servicio.admitir(clave(3), SOLICITUD)
    assert servicio.leer(trabajo_id_desde_clave(clave(3))) is None and queue.pendientes() == 2
    worker.procesar_uno()
    servicio.admitir(clave(3), SOLICITUD)
    assert store.contar_activos() == 2


def test_orden_de_llegada_aproximado():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    ids = [servicio.admitir(clave(n), SOLICITUD)[0]['trabajo_id'] for n in range(3)]
    while worker.procesar_uno():
        pass
    assert llamadas == ids


def test_entrega_duplicada_no_repite_trabajo_terminado():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    vista, _ = servicio.admitir(CLAVE, SOLICITUD)
    queue.enviar(vista['trabajo_id'])  # SQS estándar entrega al menos una vez.
    assert worker.procesar_uno() and worker.procesar_uno()
    assert not worker.procesar_uno()
    assert llamadas == [vista['trabajo_id']] and queue.pendientes() == 0


def test_entrega_duplicada_durante_el_calculo_no_lo_duplica():
    empezo, liberar = threading.Event(), threading.Event()
    llamadas = []

    def lento(trabajo):
        llamadas.append(trabajo['trabajo_id'])
        empezo.set()
        assert liberar.wait(3)
        return {'ok': True}

    reloj, store, queue, servicio, worker, _ = entorno(ejecutar=lento)
    otro = Worker(store, queue, lento, servicio.limites, clock=reloj, worker_id='w2',
                  espera_recepcion_s=0)
    vista, _ = servicio.admitir(CLAVE, SOLICITUD)
    queue.enviar(vista['trabajo_id'])
    hilo = threading.Thread(target=worker.procesar_uno)
    hilo.start()
    try:
        assert empezo.wait(2)
        assert servicio.leer(vista['trabajo_id'])['estado'] == 'procesando'
        assert otro.procesar_uno()  # Ve la concesión vigente y deja el mensaje.
        assert llamadas == [vista['trabajo_id']]
    finally:
        liberar.set()
        hilo.join(3)
    assert servicio.leer(vista['trabajo_id'])['estado'] == 'completado'
    reloj.t += 200
    assert otro.procesar_uno()  # La copia restante se descarta sin inferir.
    assert llamadas == [vista['trabajo_id']] and queue.pendientes() == 0


def test_reinicio_durante_el_calculo_reintenta_una_vez_y_luego_falla():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    vista, _ = servicio.admitir(CLAVE, SOLICITUD)
    tid = vista['trabajo_id']

    def caida():
        # Un worker recibe y reclama, y el proceso muere sin finalizar ni borrar.
        mensaje = queue.recibir()
        assert mensaje is not None
        assert store.reclamar(tid, 'muerto', reloj(), reloj() + 120, 2) is not None

    caida()
    assert servicio.leer(tid)['estado'] == 'procesando'
    reloj.t += 130  # Concesión vencida; el mensaje aún no reaparece.
    leido = servicio.leer(tid)
    assert leido['estado'] == 'en_cola' and leido['reintentando'] is True
    assert not worker.procesar_uno()
    reloj.t += 60  # Vence la visibilidad: SQS reentrega.
    mensaje = queue.recibir()
    store.reclamar(tid, 'muerto-2', reloj(), reloj() + 120, 2)
    assert store.obtener(tid)['intentos'] == 2
    reloj.t += 200
    assert servicio.leer(tid)['estado'] == 'fallido'
    assert worker.procesar_uno()
    final = servicio.leer(tid)
    assert final['estado'] == 'fallido' and final['error']['codigo'] == 'reinicio'
    assert llamadas == [] and queue.pendientes() == 0 and store.contar_activos() == 0
    assert mensaje is not None


def test_reinicio_con_intentos_disponibles_completa_en_el_nuevo_worker():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    tid = servicio.admitir(CLAVE, SOLICITUD)[0]['trabajo_id']
    queue.recibir()
    store.reclamar(tid, 'muerto', reloj(), reloj() + 120, 2)
    reloj.t += 181
    assert worker.procesar_uno()
    assert servicio.leer(tid)['estado'] == 'completado' and llamadas == [tid]


def test_expira_en_cola_si_el_worker_no_llega_a_tiempo():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    tid = servicio.admitir(CLAVE, SOLICITUD)[0]['trabajo_id']
    reloj.t += 901
    vista = servicio.leer(tid)
    assert vista['estado'] == 'expirado' and vista['error']['codigo'] == 'expirado'
    assert worker.procesar_uno()
    assert servicio.leer(tid)['estado'] == 'expirado' and llamadas == []
    assert store.contar_activos() == 0


def test_cancelar_solo_en_cola_y_no_detener_un_calculo():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    tid = servicio.admitir(CLAVE, SOLICITUD)[0]['trabajo_id']
    assert servicio.cancelar(tid)['estado'] == 'cancelado'
    assert servicio.cancelar(tid)['estado'] == 'cancelado'  # Idempotente.
    assert worker.procesar_uno() and llamadas == [] and queue.pendientes() == 0
    otro = servicio.admitir(clave(9), SOLICITUD)[0]['trabajo_id']
    queue.recibir()
    store.reclamar(otro, 'w9', reloj(), reloj() + 120, 2)
    with pytest.raises(TrabajoEnCurso):
        servicio.cancelar(otro)
    assert servicio.cancelar('f' * 32) is None and servicio.cancelar('../x') is None


def test_retencion_se_comprueba_al_leer():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    tid = servicio.admitir(CLAVE, SOLICITUD)[0]['trabajo_id']
    worker.procesar_uno()
    reloj.t += 3599
    assert servicio.leer(tid)['estado'] == 'completado'
    reloj.t += 2
    assert servicio.leer(tid) is None  # Aunque el TTL de DynamoDB aún no lo haya borrado.
    assert store.obtener(tid) is not None


@pytest.mark.parametrize('falla,codigo', [
    (EntradaInvalida(), 'entrada_invalida'),
    (EntradaInvalida('version'), 'version'),
    (RuntimeError('/ruta/privada'), 'error_modelo'),
])
def test_errores_son_terminales_saneados_y_sin_reintento(falla, codigo):
    def fallar(trabajo):
        raise falla

    reloj, store, queue, servicio, worker, _ = entorno(ejecutar=fallar)
    tid = servicio.admitir(CLAVE, SOLICITUD)[0]['trabajo_id']
    worker.procesar_uno()
    vista = servicio.leer(tid)
    assert vista['estado'] == 'fallido' and vista['error']['codigo'] == codigo
    assert '/ruta' not in vista['error']['mensaje']
    assert queue.pendientes() == 0 and store.contar_activos() == 0


def test_fallo_al_encolar_deja_fallido_y_libera_plaza():
    class ColaRota(MemoryQueue):
        def enviar(self, trabajo_id):
            raise OSError('sin red')

    reloj = Reloj()
    store = MemoryJobStore()
    servicio = JobService(store, ColaRota(clock=reloj), Limites(), clock=reloj)
    with pytest.raises(ErrorEncolado):
        servicio.admitir(CLAVE, SOLICITUD)
    vista = servicio.leer(trabajo_id_desde_clave(CLAVE))
    assert vista['estado'] == 'fallido' and vista['error']['codigo'] == 'encolado'
    assert store.contar_activos() == 0


def test_latido_renueva_concesion_y_visibilidad_en_calculos_largos():
    empezo, liberar = threading.Event(), threading.Event()

    def lento(trabajo):
        empezo.set()
        assert liberar.wait(3)
        return {'ok': True}

    limites = Limites(lease_s=30, latido_s=1)
    reloj, store, queue, servicio, worker, _ = entorno(limites, ejecutar=lento)
    tid = servicio.admitir(CLAVE, SOLICITUD)[0]['trabajo_id']
    hilo = threading.Thread(target=worker.procesar_uno)
    hilo.start()
    try:
        assert empezo.wait(2)
        reloj.t += 25
        deadline = threading.Event()
        for _ in range(40):
            if store.obtener(tid)['lease_hasta'] >= reloj.t + 29:
                break
            deadline.wait(.1)
        assert store.obtener(tid)['lease_hasta'] >= reloj.t + 29
    finally:
        liberar.set()
        hilo.join(3)
    assert servicio.leer(tid)['estado'] == 'completado'


def test_reconciliar_corrige_el_contador_tras_un_fallo_parcial():
    reloj, store, queue, servicio, worker, llamadas = entorno()
    servicio.admitir(clave(1), SOLICITUD)
    servicio.admitir(clave(2), SOLICITUD)
    store.activos = 7  # Desajuste simulado entre escrituras.
    assert store.reconciliar() == 2
    detener = threading.Event()
    detener.set()
    worker.ejecutar_en_bucle(detener)  # Reconciliar al arrancar, aun sin procesar.
    assert store.contar_activos() == 2


def test_limites_desde_entorno_validan_rangos():
    assert Limites.desde_entorno({}) == Limites()
    assert Limites.desde_entorno({'MS_COLA_MAX_ACTIVOS': '4'}).max_activos == 4
    for env in ({'MS_COLA_MAX_ACTIVOS': '0'}, {'MS_TRABAJO_LEASE_S': 'x'},
                {'MS_TRABAJO_LATIDO_S': '200', 'MS_TRABAJO_LEASE_S': '120'}):
        with pytest.raises(ValueError):
            Limites.desde_entorno(env)


def test_dlq_tras_recepciones_maximas():
    reloj, store, queue, servicio, worker, llamadas = entorno(max_recepciones=2)
    queue.enviar('a' * 32)
    for _ in range(2):
        assert queue.recibir() is not None
        reloj.t += 181
    assert queue.recibir() is None and len(queue.dlq) == 1
