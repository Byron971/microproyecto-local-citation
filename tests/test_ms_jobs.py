"""Endpoints de trabajos M/S: contrato nuevo, contrato anterior y modo síncrono."""
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.ms_lock import LOCK
from src.app.ms_queue import (EntradaInvalida, JobService, Limites, MemoryJobStore, MemoryQueue,
                              Worker)
from src.app.ms_router import ejecutar_trabajo, router

CLAVE = '0f1e2d3c-4b5a-4968-8776-655443322110'
PAYLOAD = {'paper_id': 'W05-0821', 'contexto': 'Prior work TARGETCIT.'}


class Reloj:
    t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def cola(monkeypatch):
    monkeypatch.setenv('MS_CORPUS_PATH', 'config/corpus_ms.json')
    reloj, llamadas = Reloj(), []
    store, queue = MemoryJobStore(), MemoryQueue(clock=reloj)
    limites = Limites(max_activos=3)
    servicio = JobService(store, queue, limites, clock=reloj)

    def ejecutar(trabajo):
        llamadas.append(trabajo['solicitud'])
        if 'FALLA' in trabajo['solicitud']['contexto']:
            raise EntradaInvalida()
        return {'top3': [1, 2, 3], 'articulo': {'paper_id': trabajo['solicitud']['paper_id']}}

    worker = Worker(store, queue, ejecutar, limites, clock=reloj, espera_recepcion_s=0)
    app = FastAPI()
    app.include_router(router)
    app.state.ms_jobs = servicio
    return SimpleNamespace(client=TestClient(app), worker=worker, llamadas=llamadas,
                           store=store, reloj=reloj, app=app)


def crear(client, clave=CLAVE, **extra):
    return client.post('/api/analisis-cita-ms/trabajos',
                       json={**PAYLOAD, 'clave_idempotencia': clave, **extra})


def test_contrato_nuevo_cola_resultado_y_get_sin_inferencia(cola):
    admitido = crear(cola.client)
    assert admitido.status_code == 202
    cuerpo = admitido.json()
    assert cuerpo['estado'] == 'en_cola' and cuerpo['espera_maxima_s'] == 900
    tid = cuerpo['trabajo_id']
    for _ in range(3):
        leido = cola.client.get(f'/api/analisis-cita-ms/trabajos/{tid}')
        assert leido.status_code == 200 and leido.json()['estado'] == 'en_cola'
    repetido = crear(cola.client)
    assert repetido.status_code == 202 and repetido.json()['trabajo_id'] == tid
    assert cola.llamadas == []
    assert cola.worker.procesar_uno()
    final = cola.client.get(f'/api/analisis-cita-ms/trabajos/{tid}').json()
    assert final['estado'] == 'completado' and final['resultado']['top3'] == [1, 2, 3]
    assert len(cola.llamadas) == 1
    solicitud = cola.llamadas[0]
    assert solicitud['paper_id'] == 'W05-0821' and len(solicitud['version_contenido']) == 64
    tras = crear(cola.client)  # Reenvío tras terminar: mismo resultado, sin inferir.
    assert tras.status_code == 200 and tras.json()['estado'] == 'completado'
    assert len(cola.llamadas) == 1


@pytest.mark.parametrize('extra,status', [
    ({'clave_idempotencia': 'corta'}, 422),
    ({'paper_id': 'W05-9999'}, 404),
    ({'contexto': 'Sin marcador.'}, 422),
])
def test_validacion_antes_de_admitir(cola, extra, status):
    respuesta = cola.client.post('/api/analisis-cita-ms/trabajos',
                                 json={**PAYLOAD, 'clave_idempotencia': CLAVE, **extra})
    assert respuesta.status_code == status and cola.store.contar_activos() == 0


def test_clave_reutilizada_cola_llena_e_inexistente(cola):
    crear(cola.client)
    assert crear(cola.client, contexto='Otra TARGETCIT.').status_code == 409
    for n in range(2):
        assert crear(cola.client, clave=f'{n:08d}-0000-4000-8000-000000000000').status_code == 202
    lleno = crear(cola.client, clave='99999999-0000-4000-8000-000000000000')
    assert lleno.status_code == 429 and lleno.headers['Retry-After'] == '30'
    assert 'demasiados' in lleno.json()['detail']
    assert cola.client.get('/api/analisis-cita-ms/trabajos/' + 'f' * 32).status_code == 404
    assert cola.client.get('/api/analisis-cita-ms/trabajos/no-valido').status_code == 404


def test_cancelar_en_cola_y_no_un_calculo_en_curso(cola):
    tid = crear(cola.client).json()['trabajo_id']
    cancelado = cola.client.post(f'/api/analisis-cita-ms/trabajos/{tid}/cancelar')
    assert cancelado.status_code == 200 and cancelado.json()['estado'] == 'cancelado'
    assert cola.worker.procesar_uno() and cola.llamadas == []
    otro = crear(cola.client, clave='11111111-0000-4000-8000-000000000000').json()['trabajo_id']
    cola.store.reclamar(otro, 'w', cola.reloj(), cola.reloj() + 120, 2)
    en_curso = cola.client.post(f'/api/analisis-cita-ms/trabajos/{otro}/cancelar')
    assert en_curso.status_code == 409 and 'no se puede detener' in en_curso.json()['detail']
    assert cola.client.post('/api/analisis-cita-ms/trabajos/' + 'f' * 32 + '/cancelar').status_code == 404


def test_fallo_terminal_visible_en_ambos_contratos(cola):
    tid = crear(cola.client, contexto='FALLA TARGETCIT.').json()['trabajo_id']
    cola.worker.procesar_uno()
    vista = cola.client.get(f'/api/analisis-cita-ms/trabajos/{tid}').json()
    assert vista['estado'] == 'fallido' and vista['error']['codigo'] == 'entrada_invalida'
    anterior = cola.client.get(f'/api/analisis-cita-ms/articulo/{tid}')
    assert anterior.status_code == 422


def test_contrato_anterior_sobre_la_misma_cola(cola):
    admitido = cola.client.post('/api/analisis-cita-ms/articulo', json={**PAYLOAD, 'asincrono': True})
    assert admitido.status_code == 202
    cuerpo = admitido.json()
    assert cuerpo['estado'] == 'procesando'  # Lo que validan los bundles anteriores.
    tid = cuerpo['trabajo_id']
    pendiente = cola.client.get(f'/api/analisis-cita-ms/articulo/{tid}')
    assert pendiente.status_code == 202 and pendiente.json() == {'estado': 'procesando', 'trabajo_id': tid}
    cola.worker.procesar_uno()
    final = cola.client.get(f'/api/analisis-cita-ms/articulo/{tid}')
    assert final.status_code == 200 and final.json()['top3'] == [1, 2, 3]
    assert cola.client.get('/api/analisis-cita-ms/articulo/' + 'f' * 32).status_code == 410
    faltante = cola.client.post('/api/analisis-cita-ms/articulo',
                                json={**PAYLOAD, 'paper_id': 'W05-9999', 'asincrono': True})
    assert faltante.status_code == 404 and len(cola.llamadas) == 1


def test_modo_sincrono_no_se_adelanta_a_la_cola(cola):
    with patch('src.app.ms_router.analisis_cita_ms', return_value={'top3': [9]}) as infer:
        libre = cola.client.post('/api/analisis-cita-ms/articulo', json=PAYLOAD)
        assert libre.status_code == 200 and libre.json()['articulo']['paper_id'] == 'W05-0821'
        crear(cola.client)
        ocupado = cola.client.post('/api/analisis-cita-ms/articulo', json=PAYLOAD)
        assert ocupado.status_code == 429 and infer.call_count == 1


def test_sin_cola_configurada_responde_503(monkeypatch):
    monkeypatch.setenv('MS_CORPUS_PATH', 'config/corpus_ms.json')
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.post('/api/analisis-cita-ms/trabajos',
                       json={**PAYLOAD, 'clave_idempotencia': CLAVE}).status_code == 503
    assert client.get('/api/analisis-cita-ms/trabajos/' + 'a' * 32).status_code == 503


def test_errores_del_almacen_se_traducen_a_503(cola):
    class Roto(MemoryJobStore):
        def crear(self, trabajo, max_activos):
            raise OSError('dynamodb')

        def obtener(self, trabajo_id):
            raise OSError('dynamodb')

    cola.app.state.ms_jobs = JobService(Roto(), MemoryQueue(), Limites())
    assert crear(cola.client).status_code == 503
    leido = cola.client.get('/api/analisis-cita-ms/trabajos/' + 'a' * 32)
    assert leido.status_code == 503 and 'dynamodb' not in leido.text


def trabajo_real(version):
    return {'trabajo_id': 'a' * 32, 'solicitud': {**PAYLOAD, 'version_contenido': version}}


def test_ejecutar_trabajo_usa_bloqueo_por_etapa_y_valida_version(monkeypatch):
    monkeypatch.setenv('MS_CORPUS_PATH', 'config/corpus_ms.json')
    from src.app.article_corpus import corpus
    _, version = corpus()
    bloqueado = []

    class Servicio:
        def analizar(self, contexto, titulo, abstract, candidatos, por_etapa):
            def comprobar():
                otro = []
                hilo = threading.Thread(target=lambda: otro.append(LOCK.acquire(blocking=False)))
                hilo.start(); hilo.join()
                bloqueado.append(not otro[0])
                return {'top3': [c['chunk_id'] for c in candidatos[:3]]}
            return por_etapa(comprobar)

    # Sin importar torch: el doble sustituye al módulo de inferencia en ambos entornos.
    import sys
    monkeypatch.setitem(sys.modules, 'src.app.ms_runtime',
                        SimpleNamespace(obtener_servicio=lambda: Servicio()))
    resultado = ejecutar_trabajo(trabajo_real(version))
    assert bloqueado == [True] and resultado['articulo']['version_contenido'] == version
    assert resultado['articulo']['paper_id'] == 'W05-0821'
    with pytest.raises(EntradaInvalida) as cambio:
        ejecutar_trabajo(trabajo_real('otra-version'))
    assert cambio.value.codigo == 'version'
    assert LOCK.acquire(blocking=False)
    LOCK.release()
