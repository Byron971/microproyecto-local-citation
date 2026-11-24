"""Adaptadores DynamoDB/SQS validados contra el modelo de la API de AWS, sin red."""
import json

import pytest

boto3 = pytest.importorskip('boto3')
from botocore.stub import ANY, Stubber  # noqa: E402

from src.app.ms_queue import ColaLlena, MemoryJobStore, MemoryQueue  # noqa: E402
from src.app.ms_queue_aws import DynamoJobStore, SqsJobQueue, crear_cola  # noqa: E402

TABLA, URL = 'citas-api-ms-jobs', 'https://sqs.us-east-1.amazonaws.com/000000000000/citas-api-ms-jobs'
TID = 'a' * 32
TRABAJO = {'trabajo_id': TID, 'estado': 'en_cola', 'hash_solicitud': 'h' * 64,
           'solicitud': {'paper_id': 'W05-0821', 'contexto': 'Prior TARGETCIT.', 'version_contenido': 'v'},
           'creado_en': 1000.5, 'espera_hasta': 1900.5, 'limite_hasta': 2140.5, 'intentos': 0,
           'expira_ttl': 5741}


def cliente(servicio):
    return boto3.client(servicio, region_name='us-east-1', aws_access_key_id='x',
                        aws_secret_access_key='x')


def item_dynamo(**cambios):
    trabajo = {**TRABAJO, **cambios}
    from src.app.ms_queue_aws import _a_dynamo, _pk
    return {'pk': _pk(TID), **_a_dynamo(trabajo)}


def cancelada(stub, motivos):
    stub.add_client_error('transact_write_items', service_error_code='TransactionCanceledException',
                          modeled_fields={'CancellationReasons': [{'Code': m} for m in motivos]})


def test_obtener_conserva_tipos_y_json():
    client = cliente('dynamodb')
    with Stubber(client) as stub:
        stub.add_response('get_item', {'Item': item_dynamo(resultado={'p': [0.123456, 1]})},
                          {'TableName': TABLA, 'Key': {'pk': {'S': 'trabajo#' + TID}}, 'ConsistentRead': True})
        trabajo = DynamoJobStore(client, TABLA).obtener(TID)
    assert trabajo['creado_en'] == 1000.5 and trabajo['intentos'] == 0 and trabajo['expira_ttl'] == 5741
    assert trabajo['solicitud']['paper_id'] == 'W05-0821' and trabajo['resultado'] == {'p': [0.123456, 1]}


def test_crear_nuevo_duplicado_y_cola_llena():
    client = cliente('dynamodb')
    store = DynamoJobStore(client, TABLA)
    with Stubber(client) as stub:
        stub.add_response('transact_write_items', {}, {'TransactItems': ANY})
        assert store.crear(TRABAJO, 10) is None
        cancelada(stub, ['ConditionalCheckFailed', 'None'])
        stub.add_response('get_item', {'Item': item_dynamo(estado='procesando')})
        assert store.crear(TRABAJO, 10)['estado'] == 'procesando'
        cancelada(stub, ['None', 'ConditionalCheckFailed'])
        with pytest.raises(ColaLlena):
            store.crear(TRABAJO, 10)
        stub.assert_no_pending_responses()


def test_crear_usa_condiciones_de_unicidad_y_capacidad():
    client = cliente('dynamodb')
    llamadas = []
    client.meta.events.register('provide-client-params.dynamodb.TransactWriteItems',
                                lambda params, **_: llamadas.append(params))
    with Stubber(client) as stub:
        stub.add_response('transact_write_items', {})
        DynamoJobStore(client, TABLA).crear(TRABAJO, 4)
    put, contador = llamadas[0]['TransactItems']
    assert put['Put']['ConditionExpression'] == 'attribute_not_exists(pk)'
    assert put['Put']['Item']['solicitud']['S'].startswith('{')
    assert contador['Update']['ExpressionAttributeValues'][':max'] == {'N': '4'}


def test_reclamar_condicional():
    client = cliente('dynamodb')
    store = DynamoJobStore(client, TABLA)
    with Stubber(client) as stub:
        stub.add_client_error('update_item', service_error_code='ConditionalCheckFailedException')
        assert store.reclamar(TID, 'w1', 1001.0, 1121.0, 2) is None
        stub.add_response('update_item', {'Attributes': item_dynamo(estado='procesando', intentos=1,
                                                                    worker_id='w1', lease_hasta=1121.0)})
        reclamado = store.reclamar(TID, 'w1', 1001.0, 1121.0, 2)
    assert reclamado['estado'] == 'procesando' and reclamado['worker_id'] == 'w1'


def test_finalizar_quita_contexto_y_respeta_dueno():
    client = cliente('dynamodb')
    llamadas = []
    client.meta.events.register('provide-client-params.dynamodb.TransactWriteItems',
                                lambda params, **_: llamadas.append(params))
    store = DynamoJobStore(client, TABLA)
    with Stubber(client) as stub:
        stub.add_response('transact_write_items', {})
        assert store.finalizar(TID, 'completado', {'resultado': {'ok': True}, 'terminado_en': 1.5},
                               desde={'procesando'}, worker_id='w1')
        cancelada(stub, ['ConditionalCheckFailed', 'None'])
        assert not store.finalizar(TID, 'fallido', {}, desde={'procesando'}, lease_vencido_en=9.0)
    actualizacion = llamadas[0]['TransactItems'][0]['Update']
    assert actualizacion['UpdateExpression'].endswith('REMOVE solicitud')
    assert 'worker_id = :w' in actualizacion['ConditionExpression']
    assert 'lease_hasta <= :vence' in llamadas[1]['TransactItems'][0]['Update']['ConditionExpression']
    assert 'ConditionExpression' not in llamadas[0]['TransactItems'][1]['Update']


def test_renovar_contar_y_reconciliar_paginado():
    client = cliente('dynamodb')
    store = DynamoJobStore(client, TABLA)
    with Stubber(client) as stub:
        stub.add_client_error('update_item', service_error_code='ConditionalCheckFailedException')
        assert store.renovar(TID, 'w1', 2000.0) is False
        stub.add_response('get_item', {'Item': {'pk': {'S': 'cola#activos'}, 'activos': {'N': '-2'}}})
        assert store.contar_activos() == 0
        stub.add_response('scan', {'Count': 2, 'LastEvaluatedKey': {'pk': {'S': 'trabajo#x'}}})
        stub.add_response('scan', {'Count': 1})
        stub.add_response('put_item', {}, {'TableName': TABLA,
                                           'Item': {'pk': {'S': 'cola#activos'}, 'activos': {'N': '3'}}})
        assert store.reconciliar() == 3
        stub.assert_no_pending_responses()


def test_sqs_enviar_recibir_y_descartar_invalidos():
    client = cliente('sqs')
    cola = SqsJobQueue(client, URL)
    with Stubber(client) as stub:
        stub.add_response('send_message', {'MessageId': 'm', 'MD5OfMessageBody': 'x'},
                          {'QueueUrl': URL, 'MessageBody': json.dumps({'trabajo_id': TID})})
        cola.enviar(TID)
        stub.add_response('receive_message', {'Messages': [{'Body': json.dumps({'trabajo_id': TID}),
                                                            'ReceiptHandle': 'r1',
                                                            'Attributes': {'ApproximateReceiveCount': '2'}}]},
                          {'QueueUrl': URL, 'MaxNumberOfMessages': 1, 'WaitTimeSeconds': 20,
                           'MessageSystemAttributeNames': ['ApproximateReceiveCount']})
        mensaje = cola.recibir(20)
        assert (mensaje.trabajo_id, mensaje.recibo, mensaje.recepciones) == (TID, 'r1', 2)
        stub.add_response('receive_message', {'Messages': [{'Body': 'no-json', 'ReceiptHandle': 'r2'}]})
        stub.add_response('delete_message', {}, {'QueueUrl': URL, 'ReceiptHandle': 'r2'})
        assert cola.recibir(0) is None
        stub.add_response('receive_message', {})
        assert cola.recibir(0) is None
        stub.add_response('change_message_visibility', {},
                          {'QueueUrl': URL, 'ReceiptHandle': 'r1', 'VisibilityTimeout': 120})
        assert cola.cambiar_visibilidad('r1', 120)
        stub.assert_no_pending_responses()


def test_crear_cola_segun_configuracion():
    servicio, worker, backend = crear_cola(lambda t: {}, env={})
    assert backend == 'memoria' and isinstance(servicio.store, MemoryJobStore)
    assert isinstance(servicio.queue, MemoryQueue) and worker.espera_recepcion_s == 1
    with pytest.raises(RuntimeError):
        crear_cola(lambda t: {}, env={'MS_JOBS_TABLE': TABLA})
    servicio, worker, backend = crear_cola(lambda t: {}, env={
        'MS_JOBS_TABLE': TABLA, 'MS_JOBS_QUEUE_URL': URL, 'AWS_REGION': 'us-east-1',
        'MS_COLA_MAX_ACTIVOS': '5'})
    assert backend == 'dynamodb_sqs' and servicio.limites.max_activos == 5
    assert isinstance(servicio.store, DynamoJobStore) and worker.espera_recepcion_s == 20


def sin_espera(monkeypatch):
    import src.app.ms_queue_aws as aws_mod
    monkeypatch.setattr(aws_mod.time, 'sleep', lambda s: None)


def test_conflicto_de_transaccion_en_alta_se_reintenta(monkeypatch):
    # Dos altas simultáneas tocan el contador compartido: DynamoDB cancela una con
    # TransactionConflict. Debe reintentarse, no responder 503.
    sin_espera(monkeypatch)
    client = cliente('dynamodb')
    with Stubber(client) as stub:
        cancelada(stub, ['None', 'TransactionConflict'])
        cancelada(stub, ['TransactionConflict', 'None'])
        stub.add_response('transact_write_items', {})
        assert DynamoJobStore(client, TABLA).crear(TRABAJO, 10) is None
        stub.assert_no_pending_responses()


def test_conflicto_de_transaccion_al_finalizar_se_reintenta(monkeypatch):
    sin_espera(monkeypatch)
    client = cliente('dynamodb')
    with Stubber(client) as stub:
        cancelada(stub, ['None', 'TransactionConflict'])
        stub.add_response('transact_write_items', {})
        assert DynamoJobStore(client, TABLA).finalizar(TID, 'completado', {'terminado_en': 1.0},
                                                       desde={'procesando'}, worker_id='w1')
        stub.assert_no_pending_responses()


def test_conflicto_persistente_se_propaga_tras_reintentos_acotados(monkeypatch):
    sin_espera(monkeypatch)
    client = cliente('dynamodb')
    with Stubber(client) as stub:
        for _ in range(5):
            cancelada(stub, ['None', 'TransactionConflict'])
        with pytest.raises(Exception, match='TransactionCanceled'):
            DynamoJobStore(client, TABLA).crear(TRABAJO, 10)
        stub.assert_no_pending_responses()


def test_conflicto_en_actualizacion_simple_se_reintenta(monkeypatch):
    sin_espera(monkeypatch)
    client = cliente('dynamodb')
    with Stubber(client) as stub:
        stub.add_client_error('update_item', service_error_code='TransactionConflictException')
        stub.add_response('update_item', {'Attributes': item_dynamo(estado='procesando', intentos=1,
                                                                    worker_id='w1', lease_hasta=1121.0)})
        assert DynamoJobStore(client, TABLA).reclamar(TID, 'w1', 1001.0, 1121.0, 2)['worker_id'] == 'w1'
