"""Reserva global comercial, compartida por tareas y revisiones del API."""
import logging
import os
import time
from contextlib import contextmanager
from functools import lru_cache
from uuid import uuid4

from fastapi import HTTPException

LEASE_ID = 'openai:inflight'
LEASE_SECONDS = 120


@lru_cache(maxsize=1)
def dynamodb_client():
    import boto3
    from botocore.config import Config
    # Acotar también la espera de AWS antes de iniciar la llamada comercial.
    return boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                        config=Config(connect_timeout=2, read_timeout=2,
                                      retries={'total_max_attempts': 1}))


@contextmanager
def commercial_slot():
    """Rechazar ocupados antes de reservar cuota; recuperar reservas abandonadas."""
    from botocore.exceptions import ClientError
    owner = uuid4().hex
    try:
        db = dynamodb_client()
        table = os.environ['CITAS_COMMERCIAL_LIMIT_TABLE']
        now = int(time.time())
        db.update_item(
            TableName=table, Key={'id': {'S': LEASE_ID}},
            UpdateExpression='SET lease_owner = :owner, lease_until = :until, expires_at = :ttl',
            ConditionExpression='attribute_not_exists(lease_owner) OR lease_until <= :now',
            ExpressionAttributeValues={':owner': {'S': owner}, ':now': {'N': str(now)},
                ':until': {'N': str(now + LEASE_SECONDS)},
                ':ttl': {'N': str(now + 172800)}})
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise HTTPException(429, 'El modelo comercial está ocupado. Intenta más tarde.',
                                headers={'Retry-After': '5'}) from None
        raise HTTPException(503, 'No se pudo reservar el modelo comercial. Intenta más tarde.') from None
    except Exception as exc:
        logging.getLogger(__name__).warning('Fallo de reserva comercial: %s', type(exc).__name__)
        raise HTTPException(503, 'No se pudo reservar el modelo comercial. Intenta más tarde.') from None
    try:
        yield
    finally:
        try:
            db.update_item(
                TableName=table, Key={'id': {'S': LEASE_ID}},
                UpdateExpression='REMOVE lease_owner, lease_until',
                ConditionExpression='lease_owner = :owner',
                ExpressionAttributeValues={':owner': {'S': owner}})
        except Exception:
            # Nunca liberar la reserva de otra petición ni ocultar el resultado original.
            # La reserva propia caduca aunque falle esta operación; no depende del borrado TTL.
            logging.getLogger(__name__).warning('No se pudo liberar la reserva comercial.')
