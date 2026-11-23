"""Adaptadores DynamoDB (estado/resultados) y SQS (entrega) para la cola M/S.

Misma semántica condicional que `MemoryJobStore`/`MemoryQueue`. boto3 se importa solo
al configurar AWS: el entorno científico local puede no tenerlo instalado.
"""
from __future__ import annotations

import json
import logging
import os
import time

from src.app.ms_queue import (
    ID_RE, ColaLlena, JobService, Limites, MemoryJobStore, MemoryQueue, Mensaje, TERMINALES, Worker,
)

log = logging.getLogger(__name__)

CONTADOR = 'cola#activos'
JSON = frozenset({'solicitud', 'resultado', 'error'})
TEXTO = frozenset({'trabajo_id', 'estado', 'hash_solicitud', 'worker_id'})


def _pk(trabajo_id):
    return {'S': 'trabajo#' + trabajo_id}


def _numero(valor):
    texto = repr(float(valor)) if isinstance(valor, float) else str(int(valor))
    return {'N': texto}


def _a_dynamo(campos):
    item = {}
    for nombre, valor in campos.items():
        if valor is None:
            continue
        if nombre in JSON:
            item[nombre] = {'S': json.dumps(valor, ensure_ascii=False, separators=(',', ':'))}
        elif nombre in TEXTO:
            item[nombre] = {'S': str(valor)}
        else:
            item[nombre] = _numero(valor)
    return item


def _desde_dynamo(item):
    trabajo = {}
    for nombre, valor in item.items():
        if nombre == 'pk':
            continue
        if 'N' in valor:
            texto = valor['N']
            trabajo[nombre] = float(texto) if any(c in texto for c in '.eE') else int(texto)
        elif nombre in JSON:
            trabajo[nombre] = json.loads(valor['S'])
        else:
            trabajo[nombre] = valor['S']
    return trabajo


def _codigo(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code')


def _motivos(exc):
    return [m.get('Code') for m in getattr(exc, 'response', {}).get('CancellationReasons', [])]


class DynamoJobStore:
    def __init__(self, client, tabla):
        self.client, self.tabla = client, tabla

    def obtener(self, trabajo_id):
        respuesta = self.client.get_item(TableName=self.tabla, Key={'pk': _pk(trabajo_id)},
                                         ConsistentRead=True)
        item = respuesta.get('Item')
        return _desde_dynamo(item) if item else None

    def crear(self, trabajo, max_activos):
        item = {'pk': _pk(trabajo['trabajo_id']), **_a_dynamo(trabajo)}
        try:
            self.client.transact_write_items(TransactItems=[
                {'Put': {'TableName': self.tabla, 'Item': item,
                         'ConditionExpression': 'attribute_not_exists(pk)',
                         'ReturnValuesOnConditionCheckFailure': 'ALL_OLD'}},
                {'Update': {'TableName': self.tabla, 'Key': {'pk': {'S': CONTADOR}},
                            'UpdateExpression': 'SET activos = if_not_exists(activos, :cero) + :uno',
                            'ConditionExpression': 'attribute_not_exists(activos) OR activos < :max',
                            'ExpressionAttributeValues': {':cero': {'N': '0'}, ':uno': {'N': '1'},
                                                          ':max': {'N': str(max_activos)}}}},
            ], ClientRequestToken=trabajo['trabajo_id'])
            return None
        except Exception as exc:
            if _codigo(exc) != 'TransactionCanceledException':
                raise
            motivos = _motivos(exc)
            if motivos and motivos[0] == 'ConditionalCheckFailed':
                existente = self.obtener(trabajo['trabajo_id'])
                if existente is not None:
                    return existente
            if len(motivos) > 1 and motivos[1] == 'ConditionalCheckFailed':
                raise ColaLlena() from None
            raise

    def reclamar(self, trabajo_id, worker_id, ahora, lease_hasta, max_intentos):
        try:
            respuesta = self.client.update_item(
                TableName=self.tabla, Key={'pk': _pk(trabajo_id)},
                UpdateExpression=('SET estado = :proc, intentos = intentos + :uno, worker_id = :w, '
                                  'lease_hasta = :lease, iniciado_en = if_not_exists(iniciado_en, :ahora)'),
                ConditionExpression=('(estado = :cola AND espera_hasta > :ahora) OR '
                                     '(estado = :proc AND lease_hasta <= :ahora AND intentos < :max '
                                     'AND limite_hasta > :ahora)'),
                ExpressionAttributeValues={
                    ':proc': {'S': 'procesando'}, ':cola': {'S': 'en_cola'}, ':uno': {'N': '1'},
                    ':w': {'S': worker_id}, ':lease': _numero(lease_hasta), ':ahora': _numero(ahora),
                    ':max': {'N': str(max_intentos)}},
                ReturnValues='ALL_NEW')
        except Exception as exc:
            if _codigo(exc) == 'ConditionalCheckFailedException':
                return None
            raise
        return _desde_dynamo(respuesta['Attributes'])

    def renovar(self, trabajo_id, worker_id, lease_hasta):
        try:
            self.client.update_item(
                TableName=self.tabla, Key={'pk': _pk(trabajo_id)},
                UpdateExpression='SET lease_hasta = :lease',
                ConditionExpression='estado = :proc AND worker_id = :w',
                ExpressionAttributeValues={':lease': _numero(lease_hasta), ':proc': {'S': 'procesando'},
                                           ':w': {'S': worker_id}})
            return True
        except Exception as exc:
            if _codigo(exc) == 'ConditionalCheckFailedException':
                return False
            raise

    def finalizar(self, trabajo_id, estado, campos, desde, worker_id=None, lease_vencido_en=None):
        assert estado in TERMINALES and not set(desde) & TERMINALES
        valores = {':estado': {'S': estado}}
        asignaciones = ['estado = :estado']
        for i, (nombre, valor) in enumerate(_a_dynamo(campos).items()):
            asignaciones.append(f'#c{i} = :c{i}')
            valores[f':c{i}'] = valor
        nombres = {f'#c{i}': nombre for i, nombre in enumerate(_a_dynamo(campos))}
        origen = []
        for i, actual in enumerate(sorted(desde)):
            valores[f':d{i}'] = {'S': actual}
            origen.append(f':d{i}')
        condicion = f'estado IN ({", ".join(origen)})'
        if worker_id is not None:
            condicion += ' AND worker_id = :w'
            valores[':w'] = {'S': worker_id}
        if lease_vencido_en is not None:
            condicion += ' AND lease_hasta <= :vence'
            valores[':vence'] = _numero(lease_vencido_en)
        actualizacion = {'TableName': self.tabla, 'Key': {'pk': _pk(trabajo_id)},
                         'UpdateExpression': 'SET ' + ', '.join(asignaciones) + ' REMOVE solicitud',
                         'ConditionExpression': condicion, 'ExpressionAttributeValues': valores}
        if nombres:
            actualizacion['ExpressionAttributeNames'] = nombres
        try:
            self.client.transact_write_items(TransactItems=[
                {'Update': actualizacion},
                # Sin condición: un desajuste del contador nunca impide terminar un trabajo.
                {'Update': {'TableName': self.tabla, 'Key': {'pk': {'S': CONTADOR}},
                            'UpdateExpression': 'ADD activos :menos',
                            'ExpressionAttributeValues': {':menos': {'N': '-1'}}}},
            ])
            return True
        except Exception as exc:
            if _codigo(exc) == 'TransactionCanceledException' and _motivos(exc)[:1] == ['ConditionalCheckFailed']:
                return False
            raise

    def contar_activos(self):
        item = self.client.get_item(TableName=self.tabla, Key={'pk': {'S': CONTADOR}},
                                    ConsistentRead=True).get('Item')
        return max(0, int(item['activos']['N'])) if item and 'activos' in item else 0

    def reconciliar(self):
        """Recuento acotado al arrancar; la tabla solo contiene trabajos recientes (TTL)."""
        total, inicio = 0, None
        while True:
            argumentos = {
                'TableName': self.tabla, 'Select': 'COUNT', 'ConsistentRead': True,
                'FilterExpression': 'begins_with(pk, :p) AND estado IN (:cola, :proc)',
                'ExpressionAttributeValues': {':p': {'S': 'trabajo#'}, ':cola': {'S': 'en_cola'},
                                              ':proc': {'S': 'procesando'}}}
            if inicio:
                argumentos['ExclusiveStartKey'] = inicio
            respuesta = self.client.scan(**argumentos)
            total += respuesta.get('Count', 0)
            inicio = respuesta.get('LastEvaluatedKey')
            if not inicio:
                break
        self.client.put_item(TableName=self.tabla,
                             Item={'pk': {'S': CONTADOR}, 'activos': {'N': str(total)}})
        return total


class SqsJobQueue:
    def __init__(self, client, url):
        self.client, self.url = client, url

    def enviar(self, trabajo_id):
        self.client.send_message(QueueUrl=self.url, MessageBody=json.dumps({'trabajo_id': trabajo_id}))

    def recibir(self, espera_s=20):
        respuesta = self.client.receive_message(
            QueueUrl=self.url, MaxNumberOfMessages=1, WaitTimeSeconds=int(espera_s),
            MessageSystemAttributeNames=['ApproximateReceiveCount'])
        for m in respuesta.get('Messages', []):
            try:
                trabajo_id = json.loads(m['Body'])['trabajo_id']
                valido = isinstance(trabajo_id, str) and ID_RE.fullmatch(trabajo_id)
            except (ValueError, KeyError, TypeError):
                valido = False
            if not valido:
                log.warning('Mensaje M/S inválido descartado')
                self.borrar(m['ReceiptHandle'])
                return None
            recepciones = int(m.get('Attributes', {}).get('ApproximateReceiveCount', 1))
            return Mensaje(trabajo_id, m['ReceiptHandle'], recepciones)
        return None

    def cambiar_visibilidad(self, recibo, segundos):
        self.client.change_message_visibility(QueueUrl=self.url, ReceiptHandle=recibo,
                                              VisibilityTimeout=int(segundos))
        return True

    def borrar(self, recibo):
        self.client.delete_message(QueueUrl=self.url, ReceiptHandle=recibo)
        return True


def crear_cola(ejecutar, env=None, clock=time.time):
    """Devuelve (servicio, worker, backend). Sin configuración AWS usa memoria (solo local)."""
    env = os.environ if env is None else env
    limites = Limites.desde_entorno(env)
    tabla, url = env.get('MS_JOBS_TABLE', ''), env.get('MS_JOBS_QUEUE_URL', '')
    if bool(tabla) != bool(url):
        raise RuntimeError('Configura MS_JOBS_TABLE y MS_JOBS_QUEUE_URL juntos')
    if tabla:
        import boto3
        from botocore.config import Config
        region = env.get('AWS_REGION', 'us-east-1')
        reintentos = {'mode': 'standard', 'total_max_attempts': 2}
        dynamo = boto3.client('dynamodb', region_name=region, config=Config(
            connect_timeout=2, read_timeout=3, retries=reintentos))
        # El long polling de SQS mantiene la lectura abierta hasta 20 s.
        sqs = boto3.client('sqs', region_name=region, config=Config(
            connect_timeout=2, read_timeout=25, retries=reintentos))
        store, queue, backend, espera = DynamoJobStore(dynamo, tabla), SqsJobQueue(sqs, url), 'dynamodb_sqs', 20
    else:
        log.warning('Cola M/S en memoria: no sobrevive a reinicios; usar solo en desarrollo local.')
        store = MemoryJobStore()
        queue = MemoryQueue(clock=clock, visibilidad_s=limites.lease_s + 60)
        backend, espera = 'memoria', 1
    servicio = JobService(store, queue, limites, clock=clock)
    worker = Worker(store, queue, ejecutar, limites, clock=clock, espera_recepcion_s=espera)
    return servicio, worker, backend
