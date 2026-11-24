"""Concurrencia real entre hilos con el estado atómico compartido simulado."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from src.app import commercial_limits as limits


class AtomicTable:
    def __init__(self):
        self.lock = Lock()
        self.owner = None
        self.until = 0
        self.fail_release = False

    def update_item(self, **kwargs):
        values = kwargs['ExpressionAttributeValues']
        owner = values[':owner']['S']
        with self.lock:
            if kwargs['UpdateExpression'].startswith('SET'):
                now = int(values[':now']['N'])
                if self.owner is not None and self.until > now:
                    raise ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'UpdateItem')
                self.owner, self.until = owner, int(values[':until']['N'])
            else:
                if self.fail_release:
                    raise RuntimeError('private-database-details')
                if self.owner != owner:
                    raise ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'UpdateItem')
                self.owner, self.until = None, 0


@pytest.fixture
def table(monkeypatch):
    db = AtomicTable()
    monkeypatch.setenv('CITAS_COMMERCIAL_LIMIT_TABLE', 'unit-table')
    monkeypatch.setattr(limits, 'dynamodb_client', lambda: db)
    monkeypatch.setattr(limits.time, 'time', lambda: 1000)
    return db


def test_separate_requests_share_one_slot(table):
    entered, finish = Event(), Event()

    def first():
        with limits.commercial_slot():
            entered.set()
            assert finish.wait(5)

    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(first)
        try:
            assert entered.wait(5)
            with pytest.raises(HTTPException) as error:
                with limits.commercial_slot():
                    pytest.fail('Second provider must never start')
            assert error.value.status_code == 429
            assert error.value.headers == {'Retry-After': '5'}
        finally:
            finish.set()
        request.result(timeout=5)
    with limits.commercial_slot():
        assert table.owner is not None
    assert table.owner is None


def test_abandoned_slot_expires_without_waiting_for_dynamodb_ttl(table, monkeypatch):
    table.owner, table.until = 'crashed-request', 1001
    with pytest.raises(HTTPException):
        with limits.commercial_slot():
            pass
    monkeypatch.setattr(limits.time, 'time', lambda: 1001)
    with limits.commercial_slot():
        assert table.owner != 'crashed-request'
    assert table.owner is None


def test_old_owner_cannot_release_replacement_lease(table, monkeypatch, caplog):
    old = limits.commercial_slot()
    old.__enter__()
    monkeypatch.setattr(limits.time, 'time', lambda: 1000 + limits.LEASE_SECONDS)
    with limits.commercial_slot():
        current_owner = table.owner
        old.__exit__(None, None, None)
        assert table.owner == current_owner
    assert table.owner is None


def test_release_failure_keeps_result_and_recovers_after_expiry(table, monkeypatch, caplog):
    table.fail_release = True
    with limits.commercial_slot():
        pass
    assert table.owner is not None
    assert 'private-database-details' not in caplog.text
    table.fail_release = False
    monkeypatch.setattr(limits.time, 'time', lambda: 1000 + limits.LEASE_SECONDS)
    with limits.commercial_slot():
        pass
    assert table.owner is None


@pytest.mark.parametrize('error', [RuntimeError('private-connection-details'),
    ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'UpdateItem')])
def test_aws_failure_closes_access_without_exposing_details(table, monkeypatch, error):
    monkeypatch.setattr(limits, 'dynamodb_client', Mock(side_effect=error))
    with pytest.raises(HTTPException) as caught:
        with limits.commercial_slot():
            pytest.fail('Provider must never start')
    assert caught.value.status_code == 503
    assert 'private' not in caught.value.detail
