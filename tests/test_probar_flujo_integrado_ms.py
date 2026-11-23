"""El comprobador público debe esperar el mismo trabajo sin repetir inferencia."""
import io
import json
from urllib.error import HTTPError

import pytest
from scripts import probar_flujo_integrado_ms as probe


class Response(io.BytesIO):
    def __init__(self, status, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = status


def test_probe_waits_past_30_seconds_with_one_post_and_only_observation_gets(monkeypatch):
    job = 'a' * 32
    pending = {'estado': 'procesando', 'trabajo_id': job}
    result = {'articulo': {'paper_id': 'W05-0821'}, 'top3': [1, 2, 3]}
    now = [0]
    calls = []
    def call(request, timeout):
        calls.append((request.get_method(), request.full_url, request.data))
        return Response(200 if len(calls) == 42 else 202,
                        result if len(calls) == 42 else pending)
    monkeypatch.setattr(probe.urllib.request, 'urlopen', call)
    monkeypatch.setattr(probe.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(probe.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    assert probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'}) == result
    assert now[0] == 41
    assert sum(method == 'POST' for method, _, _ in calls) == 1
    assert json.loads(calls[0][2])['asincrono'] is True
    assert all(method == 'GET' and url.endswith('/' + job) and body is None
               for method, url, body in calls[1:])


@pytest.mark.parametrize('status', [429, 503])
def test_admission_failure_stops_without_new_post_or_polling(monkeypatch, status):
    calls = []
    def call(request, timeout):
        calls.append(request.get_method())
        raise HTTPError(request.full_url, status, 'Busy', {}, None)
    monkeypatch.setattr(probe.urllib.request, 'urlopen', call)
    with pytest.raises(HTTPError) as error:
        probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'})
    assert error.value.code == status and calls == ['POST']


def test_changed_job_id_is_rejected_without_resubmission(monkeypatch):
    responses = iter([(202, {'estado': 'procesando', 'trabajo_id': 'a'*32}),
                      (202, {'estado': 'procesando', 'trabajo_id': 'b'*32})])
    calls = []
    def read(base, path, payload=None, timeout=32):
        calls.append((path, payload))
        return next(responses)
    monkeypatch.setattr(probe, 'leer_json', read)
    monkeypatch.setattr(probe.time, 'sleep', lambda seconds: None)
    with pytest.raises(ValueError, match='identificador distinto'):
        probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'})
    assert len(calls) == 2 and calls[1][1] is None


def test_deadline_stops_polling_without_resubmission(monkeypatch):
    pending = {'estado': 'procesando', 'trabajo_id': 'a'*32}
    calls = []
    def read(base, path, payload=None, timeout=32):
        calls.append((path, payload))
        return 202, pending
    monkeypatch.setattr(probe, 'leer_json', read)
    monkeypatch.setattr(probe.time, 'sleep', lambda seconds: None)
    with pytest.raises(TimeoutError, match='no se repitió'):
        probe.analizar_asincrono('https://example.org', {}, max_wait=0)
    assert len(calls) == 1
