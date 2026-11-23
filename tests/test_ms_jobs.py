"""Polling never repeats inference, queues work, or leaks expired results."""
import threading
import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.app.ms_jobs import AnalysisJobs
from src.app.ms_lock import LOCK
from src.app.ms_router import router


def wait_result(jobs, key):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = jobs.read(key)
        if isinstance(result, dict):
            return result
        time.sleep(.005)
    raise AssertionError('Worker did not finish')


def test_pending_result_and_one_shared_inference_slot():
    jobs = AnalysisJobs()
    release = threading.Event()
    calls = []
    def operation():
        calls.append(1)
        assert release.wait(3)
        return {'top3': [1,2,3]}
    try:
        pending = jobs.submit(operation)
        import json
        key = json.loads(pending.body)['trabajo_id']
        assert pending.status_code == jobs.read(key).status_code == 202
        assert not LOCK.acquire(blocking=False)  # Worker owns the existing shared lock.
        with pytest.raises(HTTPException) as busy:
            jobs.submit(operation)
        assert busy.value.status_code == 429
        for _ in range(3):
            assert jobs.read(key).status_code == 202
        assert calls == [1]
    finally:
        release.set()
    assert wait_result(jobs, key) == {'top3': [1,2,3]}
    assert jobs.read(key) == {'top3': [1,2,3]} and calls == [1]


def test_existing_synchronous_slot_rejects_async_without_computing():
    jobs = AnalysisJobs()
    with LOCK:
        with pytest.raises(HTTPException) as busy:
            jobs.submit(lambda: pytest.fail('must not infer'))
    assert busy.value.status_code == 429 and busy.value.headers == {'Retry-After':'5'}


def test_errors_expiration_and_capacity_are_bounded():
    now = [0.]
    jobs = AnalysisJobs(ttl=120, capacity=2, clock=lambda: now[0])
    import json
    ids = []
    for i in range(3):
        key = json.loads(jobs.submit(lambda i=i: {'number':i}).body)['trabajo_id']
        assert wait_result(jobs, key) == {'number':i}
        ids.append(key)
    assert len(jobs.jobs) == 2
    for key in [ids[0], 'unknown']:
        with pytest.raises(HTTPException) as expired:
            jobs.read(key)
        assert expired.value.status_code == 410
    now[0] = 121
    with pytest.raises(HTTPException) as expired:
        jobs.read(ids[-1])
    assert expired.value.status_code == 410 and jobs.jobs == {}


def test_article_route_is_backwards_compatible_and_polling_reuses_result(monkeypatch):
    import json
    jobs = AnalysisJobs()
    monkeypatch.setattr('src.app.ms_jobs.JOBS', jobs)
    monkeypatch.setenv('MS_CORPUS_PATH', 'config/corpus_ms.json')
    app = FastAPI(); app.include_router(router)
    client = TestClient(app)
    payload = {'paper_id':'W05-0821', 'contexto':'Prior work TARGETCIT.'}
    with patch('src.app.ms_router.analisis_cita_ms', return_value={'top3':[1,2,3]}) as infer:
        sync = client.post('/api/analisis-cita-ms/articulo', json=payload)
        response = client.post('/api/analisis-cita-ms/articulo', json={**payload,'asincrono':True})
        assert sync.status_code == 200 and response.status_code == 202
        key = response.json()['trabajo_id']
        wait_result(jobs, key)
        result = client.get('/api/analisis-cita-ms/articulo/'+key)
        assert result.status_code == 200 and result.json() == sync.json()
        assert client.get('/api/analisis-cita-ms/articulo/'+key).json() == sync.json()
        assert infer.call_count == 2  # Exactly one computation for each POST, none for GET.
        missing = client.post('/api/analisis-cita-ms/articulo', json={**payload,'paper_id':'W05-9999','asincrono':True})
        assert missing.status_code == 404 and infer.call_count == 2


@pytest.mark.parametrize('failure,status', [(HTTPException(422, 'Entrada inválida'),422), (RuntimeError('/private/internal-detail'),503)])
def test_failure_releases_slot_and_sanitizes_unexpected_errors(failure, status):
    jobs = AnalysisJobs()
    def fail():
        raise failure
    import json
    key = json.loads(jobs.submit(fail).body)['trabajo_id']
    with pytest.raises(HTTPException) as error:
        wait_result(jobs, key)
    assert error.value.status_code == status
    assert '/private' not in str(error.value.detail)
    assert jobs.active is None
    assert LOCK.acquire(blocking=False)
    LOCK.release()
    import json
    key = json.loads(jobs.submit(lambda: {'ok':True}).body)['trabajo_id']
    assert wait_result(jobs, key) == {'ok':True}
