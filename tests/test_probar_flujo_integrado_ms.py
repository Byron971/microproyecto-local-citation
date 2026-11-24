"""El comprobador público espera el mismo trabajo sin repetir inferencia."""
import io
import json
from urllib.error import HTTPError

import pytest
from scripts import probar_flujo_integrado_ms as probe

JOB = 'a' * 32


def job(estado, **extra):
    return {'trabajo_id': JOB, 'estado': estado, 'espera_maxima_s': 900, **extra}


class Response(io.BytesIO):
    def __init__(self, status, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = status


def test_cola_y_calculo_largos_con_un_post_y_solo_get(monkeypatch):
    result = {'articulo': {'paper_id': 'W05-0821'}, 'top3': [1, 2, 3]}
    now, calls = [0], []

    def call(request, timeout):
        calls.append((request.get_method(), request.full_url, request.data))
        n = len(calls)
        if n == 1:
            return Response(202, job('en_cola'))
        if n < 10:
            return Response(200, job('en_cola'))
        if n < 40:
            return Response(200, job('procesando'))
        return Response(200, job('completado', resultado=result))

    monkeypatch.setattr(probe.urllib.request, 'urlopen', call)
    monkeypatch.setattr(probe.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(probe.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    estados = []
    assert probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'},
                                    estados=estados) == result
    assert estados == ['en_cola', 'procesando', 'completado'] and now[0] == 78
    assert sum(method == 'POST' for method, _, _ in calls) == 1
    cuerpo = json.loads(calls[0][2])
    assert calls[0][1].endswith('/api/analisis-cita-ms/trabajos') and len(cuerpo['clave_idempotencia']) == 36
    assert all(method == 'GET' and url.endswith('/trabajos/' + JOB) and body is None
               for method, url, body in calls[1:])


@pytest.mark.parametrize('status', [429, 503])
def test_fallo_de_admision_se_detiene_sin_otro_post(monkeypatch, status):
    calls = []

    def call(request, timeout):
        calls.append(request.get_method())
        raise HTTPError(request.full_url, status, 'Busy', {}, None)

    monkeypatch.setattr(probe.urllib.request, 'urlopen', call)
    with pytest.raises(HTTPError) as error:
        probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'})
    assert error.value.code == status and calls == ['POST']


@pytest.mark.parametrize('estado', ['fallido', 'expirado'])
def test_estado_terminal_de_error_se_informa_sin_reenvio(monkeypatch, estado):
    respuestas = iter([(202, job('en_cola')),
                       (200, job(estado, error={'mensaje': 'detalle'}))])
    calls = []

    def read(base, path, payload=None, timeout=32):
        calls.append(payload)
        return next(respuestas)

    monkeypatch.setattr(probe, 'leer_json', read)
    monkeypatch.setattr(probe.time, 'sleep', lambda seconds: None)
    with pytest.raises(RuntimeError, match=estado):
        probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'})
    assert len(calls) == 2 and calls[1] is None


def test_identificador_cambiado_se_rechaza(monkeypatch):
    respuestas = iter([(202, job('en_cola')), (200, {**job('en_cola'), 'trabajo_id': 'b' * 32})])
    monkeypatch.setattr(probe, 'leer_json', lambda *a, **k: next(respuestas))
    monkeypatch.setattr(probe.time, 'sleep', lambda seconds: None)
    with pytest.raises(ValueError, match='identificador distinto'):
        probe.analizar_asincrono('https://example.org', {'paper_id': 'W05-0821'})


def test_limite_de_espera_sin_reenvio(monkeypatch):
    calls = []

    def read(base, path, payload=None, timeout=32):
        calls.append(payload)
        return 202, job('en_cola')

    monkeypatch.setattr(probe, 'leer_json', read)
    with pytest.raises(TimeoutError, match='no se repitió'):
        probe.analizar_asincrono('https://example.org', {}, max_wait=0)
    assert len(calls) == 1


def test_gradual_acotado_y_se_detiene_ante_el_primer_fallo(monkeypatch):
    llamados = []

    def caso(base, indice):
        llamados.append(indice)
        return {'caso': indice + 1, 'ok': indice == 0}

    monkeypatch.setattr(probe, 'caso', caso)
    informe = probe.gradual('https://example.org', 3, 2)
    assert llamados == [0, 1] and informe['simultaneos'] == [] and not informe['ok']
    with pytest.raises(SystemExit):
        probe.gradual('https://example.org', 50, 0)
