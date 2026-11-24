"""Comprueba DynamoDB con una clave aislada, sin cuota diaria ni proveedor."""
import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from src.app import commercial_limits as limits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', action='store_true')
    args = parser.parse_args()
    if args.public:
        return check_public()
    limits.LEASE_ID = 'concurrency-check:' + uuid4().hex
    with limits.commercial_slot():
        try:
            with limits.commercial_slot():
                raise AssertionError('DynamoDB admitió dos propietarios')
        except HTTPException as exc:
            assert exc.status_code == 429 and exc.headers['Retry-After'] == '5'
    # Simular una reserva abandonada ya vencida; no esperar el borrado por TTL.
    db = limits.dynamodb_client()
    db.update_item(TableName=os.environ['CITAS_COMMERCIAL_LIMIT_TABLE'],
                   Key={'id': {'S': limits.LEASE_ID}},
                   UpdateExpression='SET lease_owner = :owner, lease_until = :until',
                   ExpressionAttributeValues={':owner': {'S': 'abandoned-check'}, ':until': {'N': '0'}})
    with limits.commercial_slot():
        pass
    report = {'ok': True, 'atomic_busy_429': True, 'reacquire_after_release': True,
              'recover_expired_lease': True, 'provider_calls': 0, 'daily_quota_used': 0,
              'isolated_key': limits.LEASE_ID}
    Path('artifacts/t10-concurrency-check.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def check_public():
    # Ejecutar únicamente tras confirmar la imagen nueva y ECS estable.
    table = os.environ['CITAS_COMMERCIAL_LIMIT_TABLE']
    daily = 'openai:' + datetime.now(timezone.utc).strftime('%Y-%m-%d')
    db = limits.dynamodb_client()

    def calls():
        row = db.get_item(TableName=table, Key={'id': {'S': daily}}, ConsistentRead=True)
        return int(row.get('Item', {}).get('calls', {}).get('N', '0'))

    with limits.commercial_slot():
        before = calls()
        body = json.dumps({'contexto': 'Our synthetic system uses TARGETCIT for evaluation.',
                           'paper_id': 'W05-0821', 'consentimiento': True}).encode()
        request = urllib.request.Request(
            'https://api.proyectocitas-grupo19.click/api/comercial/clasificar',
            data=body, headers={'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request, timeout=15)
            raise AssertionError('La API pública no rechazó la reserva ocupada')
        except urllib.error.HTTPError as exc:
            assert exc.code == 429
            assert exc.headers['Retry-After'] == '5'
            assert 'ocupado' in json.load(exc)['detail']
        assert calls() == before, 'La petición ocupada consumió cuota'
    report = {'ok': True, 'public_busy_429': True, 'retry_after': 5,
              'daily_quota_unchanged': True, 'provider_calls': 0}
    Path('artifacts/t10-concurrency-public-check.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
