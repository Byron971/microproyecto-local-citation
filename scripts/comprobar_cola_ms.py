"""Comprueba la cola M/S real sin inferencia ni trabajos de usuario.

- DynamoDB: escritura condicional (unicidad), actualización condicional, TTL activo.
  Usa una clave `comprobacion#…` que no es un trabajo ni toca el contador `cola#activos`.
- SQS: envío, recepción y borrado de un mensaje propio; cifrado, retención y DLQ.
  Cualquier mensaje ajeno recibido se devuelve a la cola de inmediato (visibilidad 0).
- IAM: simula, con el rol de tarea, las acciones que usa el worker sobre esos recursos.
"""
import argparse
import json
import time
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ACCIONES_SQS = ['sqs:SendMessage', 'sqs:ReceiveMessage', 'sqs:DeleteMessage',
                'sqs:ChangeMessageVisibility', 'sqs:GetQueueAttributes']
ACCIONES_DYNAMO = ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:Scan']


def comprobar_dynamo(db, tabla):
    pk = {'S': 'comprobacion#' + uuid.uuid4().hex}
    expira = {'N': str(int(time.time()) + 600)}
    db.put_item(TableName=tabla, Item={'pk': pk, 'estado': {'S': 'en_cola'}, 'expira_ttl': expira},
                ConditionExpression='attribute_not_exists(pk)')
    try:
        try:
            db.put_item(TableName=tabla, Item={'pk': pk, 'estado': {'S': 'en_cola'}, 'expira_ttl': expira},
                        ConditionExpression='attribute_not_exists(pk)')
            duplicado_rechazado = False
        except ClientError as exc:
            duplicado_rechazado = exc.response['Error']['Code'] == 'ConditionalCheckFailedException'
        db.update_item(TableName=tabla, Key={'pk': pk}, UpdateExpression='SET estado = :p',
                       ConditionExpression='estado = :c',
                       ExpressionAttributeValues={':p': {'S': 'procesando'}, ':c': {'S': 'en_cola'}})
        try:
            db.update_item(TableName=tabla, Key={'pk': pk}, UpdateExpression='SET estado = :p',
                           ConditionExpression='estado = :c',
                           ExpressionAttributeValues={':p': {'S': 'procesando'}, ':c': {'S': 'en_cola'}})
            reclamo_doble_rechazado = False
        except ClientError as exc:
            reclamo_doble_rechazado = exc.response['Error']['Code'] == 'ConditionalCheckFailedException'
    finally:
        db.delete_item(TableName=tabla, Key={'pk': pk})
    ttl = db.describe_time_to_live(TableName=tabla)['TimeToLiveDescription']
    return {'duplicado_rechazado': duplicado_rechazado, 'reclamo_doble_rechazado': reclamo_doble_rechazado,
            'ttl': {'estado': ttl.get('TimeToLiveStatus'), 'atributo': ttl.get('AttributeName')},
            'elemento_de_prueba_borrado': True}


def comprobar_sqs(sqs, url):
    atributos = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['All'])['Attributes']
    propio = 'comprobacion-' + uuid.uuid4().hex
    sqs.send_message(QueueUrl=url, MessageBody=json.dumps({'comprobacion': propio}))
    borrado, ajenos, limite = False, 0, time.monotonic() + 40
    while not borrado and time.monotonic() < limite:
        respuesta = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=5)
        for m in respuesta.get('Messages', []):
            if json.loads(m['Body']).get('comprobacion') == propio:
                sqs.delete_message(QueueUrl=url, ReceiptHandle=m['ReceiptHandle'])
                borrado = True
            else:
                ajenos += 1  # Trabajo real: devolverlo sin retrasarlo.
                sqs.change_message_visibility(QueueUrl=url, ReceiptHandle=m['ReceiptHandle'],
                                              VisibilityTimeout=0)
    redrive = json.loads(atributos.get('RedrivePolicy', '{}'))
    return {'mensaje_propio_recibido_y_borrado': borrado, 'mensajes_ajenos_devueltos': ajenos,
            'cifrado_sqs': atributos.get('SqsManagedSseEnabled') == 'true',
            'visibilidad_s': int(atributos['VisibilityTimeout']),
            'retencion_s': int(atributos['MessageRetentionPeriod']),
            'espera_larga_s': int(atributos['ReceiveMessageWaitTimeSeconds']),
            'dlq_max_recepciones': redrive.get('maxReceiveCount')}


def comprobar_iam(iam, rol, recursos):
    permitidas = {}
    for acciones, recurso in ((ACCIONES_SQS, recursos['cola_arn']), (ACCIONES_DYNAMO, recursos['tabla_arn'])):
        resultado = iam.simulate_principal_policy(PolicySourceArn=rol, ActionNames=acciones,
                                                  ResourceArns=[recurso])
        for r in resultado['EvaluationResults']:
            permitidas[r['EvalActionName']] = r['EvalDecision'] == 'allowed'
    return permitidas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proyecto', default='citas-api')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--salida', type=Path, default=Path('artifacts/ms-queue-check.json'))
    args = parser.parse_args()
    sesion = boto3.Session(region_name=args.region)
    db, sqs, iam = sesion.client('dynamodb'), sesion.client('sqs'), sesion.client('iam')
    tabla = f'{args.proyecto}-ms-jobs'
    url = sqs.get_queue_url(QueueName=f'{args.proyecto}-ms-jobs')['QueueUrl']
    recursos = {
        'tabla_arn': db.describe_table(TableName=tabla)['Table']['TableArn'],
        'cola_arn': sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['QueueArn'])['Attributes']['QueueArn'],
    }
    rol = iam.get_role(RoleName=f'{args.proyecto}-ecs-task')['Role']['Arn']
    informe = {'tabla': tabla, 'cola': url.rsplit('/', 1)[-1], 'inferencias': 0,
               'dynamodb': comprobar_dynamo(db, tabla), 'sqs': comprobar_sqs(sqs, url),
               'iam_rol_tarea': comprobar_iam(iam, rol, recursos)}
    informe['ok'] = (informe['dynamodb']['duplicado_rechazado'] and informe['dynamodb']['reclamo_doble_rechazado']
                     and informe['dynamodb']['ttl']['estado'] in ('ENABLED', 'ENABLING')
                     and informe['sqs']['mensaje_propio_recibido_y_borrado'] and informe['sqs']['cifrado_sqs']
                     and informe['sqs']['dlq_max_recepciones'] == 3
                     and all(informe['iam_rol_tarea'].values()))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(informe, indent=2, ensure_ascii=False))
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    if not informe['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
