"""Cola duradera de análisis M/S: estado en un almacén, entrega en una cola.

- Consultar el estado nunca ejecuta inferencia.
- La misma clave de idempotencia devuelve el mismo trabajo (doble clic, reenvíos).
- Una entrega repetida de la cola no repite un trabajo terminado ni uno en curso.
- Solo un reinicio con la concesión (lease) vencida permite un reintento acotado.
- No se promete detener un cálculo ya iniciado: cancelar solo afecta a trabajos en cola.

Las implementaciones en memoria de este módulo existen para pruebas; producción usa
DynamoDB (estado/resultados) y SQS (entrega) con la misma semántica condicional.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass

log = logging.getLogger(__name__)

TERMINALES = frozenset({'completado', 'fallido', 'expirado', 'cancelado'})
ID_RE = re.compile(r'[a-f0-9]{32}')
CLAVE_RE = re.compile(r'[A-Za-z0-9-]{16,64}')

MENSAJES = {
    'expirado': 'El análisis esperó demasiado en la cola y no llegó a ejecutarse. '
                'Tu contexto se conserva; puedes volver a intentarlo.',
    'reinicio': 'El servicio se reinició durante el cálculo y no pudo completarlo. '
                'Tu contexto se conserva; puedes volver a intentarlo.',
    'entrada_invalida': 'No se pudo analizar esta cita con el artículo seleccionado.',
    'error_modelo': 'No se pudo completar el análisis científico.',
    'encolado': 'No se pudo poner el análisis en la cola. Inténtalo de nuevo en unos segundos.',
    'version': 'El contenido del artículo cambió desde que se pidió el análisis. Vuelve a analizar.',
}


class ColaLlena(Exception):
    """Se alcanzó el máximo de trabajos activos (en cola o en proceso)."""


class ClaveReutilizada(Exception):
    """La clave de idempotencia ya se usó para otra solicitud o ya venció."""


class TrabajoEnCurso(Exception):
    """El trabajo ya se está calculando; no puede cancelarse."""


class ErrorEncolado(Exception):
    """El trabajo se registró pero no pudo enviarse a la cola."""


class EntradaInvalida(Exception):
    """Error determinista de la entrada: no se reintenta."""

    def __init__(self, codigo='entrada_invalida', mensaje=None):
        super().__init__(codigo)
        self.codigo = codigo
        self.mensaje = mensaje or MENSAJES.get(codigo, MENSAJES['entrada_invalida'])


def _entero(env, nombre, defecto, minimo, maximo):
    valor = env.get(nombre)
    try:
        numero = defecto if valor in (None, '') else int(valor)
    except ValueError:
        raise ValueError(f'{nombre} debe ser un entero') from None
    if not minimo <= numero <= maximo:
        raise ValueError(f'{nombre} debe estar entre {minimo} y {maximo}')
    return numero


@dataclass(frozen=True)
class Limites:
    max_activos: int = 10        # en cola + en proceso
    espera_max_s: int = 900      # tiempo máximo en cola antes de expirar
    lease_s: int = 120           # concesión renovada por el latido mientras se calcula
    max_intentos: int = 2        # ejecuciones como máximo (1 reintento tras reinicio)
    retencion_s: int = 3600      # disponibilidad del resultado terminal
    latido_s: int = 30           # renovación de lease y visibilidad

    def __post_init__(self):
        if not (1 <= self.max_activos <= 100 and 60 <= self.espera_max_s <= 3600
                and 30 <= self.lease_s <= 900 and 1 <= self.max_intentos <= 3
                and 60 <= self.retencion_s <= 86400 and 1 <= self.latido_s < self.lease_s):
            raise ValueError('Límites de la cola M/S fuera de rango')

    @classmethod
    def desde_entorno(cls, env=None):
        env = os.environ if env is None else env
        return cls(
            max_activos=_entero(env, 'MS_COLA_MAX_ACTIVOS', 10, 1, 100),
            espera_max_s=_entero(env, 'MS_COLA_ESPERA_MAX_S', 900, 60, 3600),
            lease_s=_entero(env, 'MS_TRABAJO_LEASE_S', 120, 30, 900),
            max_intentos=_entero(env, 'MS_TRABAJO_MAX_INTENTOS', 2, 1, 3),
            retencion_s=_entero(env, 'MS_RESULTADO_RETENCION_S', 3600, 60, 86400),
            latido_s=_entero(env, 'MS_TRABAJO_LATIDO_S', 30, 1, 899),
        )

    def publicos(self):
        return {'espera_maxima_s': self.espera_max_s, 'retencion_s': self.retencion_s}


def trabajo_id_desde_clave(clave):
    return hashlib.sha256(('ms-trabajo:' + clave).encode()).hexdigest()[:32]


def hash_solicitud(solicitud):
    texto = json.dumps(solicitud, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(texto.encode()).hexdigest()


def error(codigo, mensaje=None):
    return {'codigo': codigo, 'mensaje': mensaje or MENSAJES[codigo]}


def campos_terminales(limites, ahora, **extra):
    disponible = ahora + limites.retencion_s
    return {'terminado_en': ahora, 'disponible_hasta': disponible,
            'expira_ttl': int(math.ceil(disponible)) + 60, **extra}


# --------------------------------------------------------------------------- dobles

class MemoryJobStore:
    """Almacén en memoria con la misma semántica condicional que DynamoDB."""

    def __init__(self):
        self.items = {}
        self.activos = 0
        self.guard = threading.Lock()

    def obtener(self, trabajo_id):
        with self.guard:
            return copy.deepcopy(self.items.get(trabajo_id))

    def crear(self, trabajo, max_activos):
        """Devuelve None si lo creó; el existente si la clave ya existía."""
        with self.guard:
            existente = self.items.get(trabajo['trabajo_id'])
            if existente is not None:
                return copy.deepcopy(existente)
            if self.activos >= max_activos:
                raise ColaLlena()
            self.items[trabajo['trabajo_id']] = copy.deepcopy(trabajo)
            self.activos += 1
            return None

    def reclamar(self, trabajo_id, worker_id, ahora, lease_hasta, max_intentos):
        with self.guard:
            t = self.items.get(trabajo_id)
            if t is None:
                return None
            en_cola = t['estado'] == 'en_cola' and t['espera_hasta'] > ahora
            huerfano = (t['estado'] == 'procesando' and t['lease_hasta'] <= ahora
                        and t['intentos'] < max_intentos and t['limite_hasta'] > ahora)
            if not (en_cola or huerfano):
                return None
            t.update(estado='procesando', intentos=t['intentos'] + 1,
                     worker_id=worker_id, lease_hasta=lease_hasta)
            t.setdefault('iniciado_en', ahora)
            return copy.deepcopy(t)

    def renovar(self, trabajo_id, worker_id, lease_hasta):
        with self.guard:
            t = self.items.get(trabajo_id)
            if not t or t['estado'] != 'procesando' or t.get('worker_id') != worker_id:
                return False
            t['lease_hasta'] = lease_hasta
            return True

    def finalizar(self, trabajo_id, estado, campos, desde, worker_id=None, lease_vencido_en=None):
        """Transición condicional a un estado terminal; libera una plaza activa."""
        assert estado in TERMINALES and not set(desde) & TERMINALES
        with self.guard:
            t = self.items.get(trabajo_id)
            if (t is None or t['estado'] not in desde
                    or (worker_id is not None and t.get('worker_id') != worker_id)
                    or (lease_vencido_en is not None and t.get('lease_hasta', 0) > lease_vencido_en)):
                return False
            t.update(campos, estado=estado)
            t.pop('solicitud', None)  # El contexto del usuario no se conserva tras terminar.
            self.activos = max(0, self.activos - 1)
            return True

    def contar_activos(self):
        with self.guard:
            return self.activos

    def reconciliar(self):
        with self.guard:
            self.activos = sum(t['estado'] not in TERMINALES for t in self.items.values())
            return self.activos


@dataclass(frozen=True)
class Mensaje:
    trabajo_id: str
    recibo: str
    recepciones: int


class MemoryQueue:
    """Cola en memoria con visibilidad, reentrega y DLQ al estilo SQS estándar."""

    def __init__(self, clock=time.time, visibilidad_s=180, max_recepciones=3):
        self.clock, self.visibilidad_s, self.max_recepciones = clock, visibilidad_s, max_recepciones
        self.mensajes, self.dlq = [], []
        self.guard = threading.Condition()

    def enviar(self, trabajo_id):
        with self.guard:
            self.mensajes.append({'trabajo_id': trabajo_id, 'visible_en': 0.0,
                                  'recepciones': 0, 'recibo': None})
            self.guard.notify_all()

    def recibir(self, espera_s=0):
        """Espera hasta `espera_s` segundos reales (como el long polling de SQS)."""
        limite = time.monotonic() + espera_s
        while True:
            mensaje = self._recibir_visible()
            restante = limite - time.monotonic()
            if mensaje is not None or restante <= 0:
                return mensaje
            with self.guard:
                self.guard.wait(min(restante, 0.5))

    def _recibir_visible(self):
        with self.guard:
            ahora = self.clock()
            for m in list(self.mensajes):
                if m['visible_en'] > ahora:
                    continue
                if m['recepciones'] >= self.max_recepciones:
                    self.mensajes.remove(m)
                    self.dlq.append(m)
                    continue
                m['recepciones'] += 1
                m['recibo'] = uuid.uuid4().hex
                m['visible_en'] = ahora + self.visibilidad_s
                return Mensaje(m['trabajo_id'], m['recibo'], m['recepciones'])
            return None

    def cambiar_visibilidad(self, recibo, segundos):
        with self.guard:
            for m in self.mensajes:
                if m['recibo'] == recibo:
                    m['visible_en'] = self.clock() + segundos
                    return True
            return False

    def borrar(self, recibo):
        with self.guard:
            for m in self.mensajes:
                if m['recibo'] == recibo:
                    self.mensajes.remove(m)
                    return True
            return False

    def pendientes(self):
        with self.guard:
            return len(self.mensajes)


# --------------------------------------------------------------------------- servicio

class JobService:
    """Admisión, lectura y cancelación. Nunca ejecuta inferencia."""

    def __init__(self, store, queue, limites=None, clock=time.time):
        self.store, self.queue = store, queue
        self.limites = limites or Limites()
        self.clock = clock

    def admitir(self, clave, solicitud):
        """Devuelve (vista, nuevo). Lanza ColaLlena, ClaveReutilizada o ErrorEncolado."""
        if not isinstance(clave, str) or not CLAVE_RE.fullmatch(clave):
            raise ValueError('Clave de idempotencia inválida')
        ahora, lim = self.clock(), self.limites
        trabajo_id, firma = trabajo_id_desde_clave(clave), hash_solicitud(solicitud)
        espera_hasta = ahora + lim.espera_max_s
        limite_hasta = espera_hasta + lim.lease_s * lim.max_intentos
        trabajo = {
            'trabajo_id': trabajo_id, 'estado': 'en_cola', 'hash_solicitud': firma,
            'solicitud': solicitud, 'creado_en': ahora, 'espera_hasta': espera_hasta,
            'limite_hasta': limite_hasta, 'intentos': 0,
            'expira_ttl': int(math.ceil(limite_hasta + lim.retencion_s)),
        }
        existente = self.store.crear(trabajo, lim.max_activos)
        if existente is not None:
            vista = self.vista(existente, ahora)
            if existente.get('hash_solicitud') != firma or vista is None:
                raise ClaveReutilizada()
            return vista, False
        try:
            self.queue.enviar(trabajo_id)
        except Exception:
            log.exception('No se pudo encolar el trabajo M/S')
            self.store.finalizar(trabajo_id, 'fallido',
                                 campos_terminales(lim, self.clock(), error=error('encolado')),
                                 desde={'en_cola'})
            raise ErrorEncolado() from None
        return self.vista(trabajo, ahora), True

    def leer(self, trabajo_id):
        if not isinstance(trabajo_id, str) or not ID_RE.fullmatch(trabajo_id):
            return None
        trabajo = self.store.obtener(trabajo_id)
        return None if trabajo is None else self.vista(trabajo, self.clock())

    def cancelar(self, trabajo_id):
        """Solo en_cola → cancelado. Un cálculo iniciado no se detiene."""
        if not isinstance(trabajo_id, str) or not ID_RE.fullmatch(trabajo_id):
            return None
        ahora = self.clock()
        actual = self.store.obtener(trabajo_id)
        if (actual and actual['estado'] == 'en_cola' and actual['espera_hasta'] > ahora
                and self.store.finalizar(trabajo_id, 'cancelado',
                                         campos_terminales(self.limites, ahora), desde={'en_cola'})):
            return self.leer(trabajo_id)
        vista = self.leer(trabajo_id)
        if vista is not None and vista['estado'] in ('procesando', 'en_cola'):
            raise TrabajoEnCurso()
        return vista

    def hay_activos(self):
        return self.store.contar_activos() > 0

    def vista(self, trabajo, ahora):
        """Estado observable. Evalúa vencimientos al leer: el TTL de DynamoDB borra tarde."""
        estado, err = trabajo['estado'], trabajo.get('error')
        reintentando = False
        if estado in TERMINALES:
            if trabajo.get('disponible_hasta', 0) <= ahora:
                return None
        else:
            if trabajo.get('expira_ttl', 0) <= ahora:
                return None
            if estado == 'en_cola' and trabajo['espera_hasta'] <= ahora:
                estado, err = 'expirado', error('expirado')
            elif estado == 'procesando' and trabajo['lease_hasta'] <= ahora:
                if (trabajo['intentos'] >= self.limites.max_intentos
                        or trabajo['limite_hasta'] <= ahora):
                    estado, err = 'fallido', error('reinicio')
                else:
                    estado, reintentando = 'en_cola', True
        vista = {'trabajo_id': trabajo['trabajo_id'], 'estado': estado,
                 'creado_en': trabajo['creado_en'], **self.limites.publicos()}
        for campo in ('iniciado_en', 'terminado_en', 'disponible_hasta'):
            if trabajo.get(campo) is not None:
                vista[campo] = trabajo[campo]
        if reintentando:
            vista['reintentando'] = True
        if estado == 'completado':
            vista['resultado'] = trabajo['resultado']
        if err and estado in ('fallido', 'expirado'):
            vista['error'] = err
        return vista


# --------------------------------------------------------------------------- worker

class Worker:
    """Consume la cola dentro de la tarea científica (el modelo ya está cargado ahí)."""

    def __init__(self, store, queue, ejecutar, limites=None, clock=time.time,
                 worker_id=None, espera_recepcion_s=20):
        self.store, self.queue, self.ejecutar = store, queue, ejecutar
        self.limites = limites or Limites()
        self.clock = clock
        self.worker_id = worker_id or uuid.uuid4().hex
        self.espera_recepcion_s = espera_recepcion_s

    def procesar_uno(self):
        """Procesa como máximo un mensaje. Devuelve False si la cola estaba vacía."""
        mensaje = self.queue.recibir(self.espera_recepcion_s)
        if mensaje is None:
            return False
        tid, lim, ahora = mensaje.trabajo_id, self.limites, self.clock()
        trabajo = self.store.obtener(tid)
        if trabajo is None or trabajo['estado'] in TERMINALES:
            self.queue.borrar(mensaje.recibo)  # Entrega duplicada o trabajo vencido.
            return True
        if trabajo['estado'] == 'en_cola' and trabajo['espera_hasta'] <= ahora:
            self.store.finalizar(tid, 'expirado', campos_terminales(lim, ahora, error=error('expirado')),
                                 desde={'en_cola'})
            self.queue.borrar(mensaje.recibo)
            return True
        if trabajo['estado'] == 'procesando' and trabajo['lease_hasta'] > ahora:
            # Otro worker lo calcula (p. ej., durante un despliegue). No duplicar.
            restante = max(1, math.ceil(trabajo['lease_hasta'] - ahora))
            self.queue.cambiar_visibilidad(mensaje.recibo, restante)
            return True
        if trabajo['estado'] == 'procesando' and (trabajo['intentos'] >= lim.max_intentos
                                                  or trabajo['limite_hasta'] <= ahora):
            self.store.finalizar(tid, 'fallido', campos_terminales(lim, ahora, error=error('reinicio')),
                                 desde={'procesando'}, lease_vencido_en=ahora)
            self.queue.borrar(mensaje.recibo)
            return True
        reclamado = self.store.reclamar(tid, self.worker_id, ahora, ahora + lim.lease_s, lim.max_intentos)
        if reclamado is not None:
            self._ejecutar(reclamado, mensaje)
        return True

    def _ejecutar(self, trabajo, mensaje):
        tid = trabajo['trabajo_id']
        parar = threading.Event()
        latido = threading.Thread(target=self._latir, args=(tid, mensaje.recibo, parar),
                                  daemon=True, name='ms-latido')
        latido.start()
        try:
            try:
                estado, extra = 'completado', {'resultado': self.ejecutar(trabajo)}
            except EntradaInvalida as exc:
                estado, extra = 'fallido', {'error': error(exc.codigo, exc.mensaje)}
            except Exception:
                log.exception('Error al ejecutar el análisis M/S %s', tid)
                estado, extra = 'fallido', {'error': error('error_modelo')}
        finally:
            parar.set()
            latido.join(timeout=5)
        if self.store.finalizar(tid, estado, campos_terminales(self.limites, self.clock(), **extra),
                                desde={'procesando'}, worker_id=self.worker_id):
            self.queue.borrar(mensaje.recibo)
        else:
            log.warning('El trabajo %s cambió de dueño antes de terminar; se conserva el mensaje', tid)

    def _latir(self, tid, recibo, parar):
        while not parar.wait(self.limites.latido_s):
            if not self.store.renovar(tid, self.worker_id, self.clock() + self.limites.lease_s):
                log.warning('No se pudo renovar la concesión del trabajo %s', tid)
                return
            try:
                self.queue.cambiar_visibilidad(recibo, self.limites.lease_s)
            except Exception:
                log.warning('No se pudo extender la visibilidad del trabajo %s', tid)

    def ejecutar_en_bucle(self, detener):
        try:
            self.store.reconciliar()
        except Exception:
            log.exception('No se pudo reconciliar el contador de la cola M/S')
        while not detener.is_set():
            try:
                self.procesar_uno()
            except Exception:
                log.exception('Fallo del worker M/S; se reintenta la recepción')
                detener.wait(5)

    def iniciar(self):
        detener = threading.Event()
        hilo = threading.Thread(target=self.ejecutar_en_bucle, args=(detener,),
                                daemon=True, name='ms-worker')
        hilo.start()
        return hilo, detener
