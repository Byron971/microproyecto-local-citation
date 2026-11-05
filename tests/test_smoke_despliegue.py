"""Smoke sin Docker: conserva contrato del verificador HTTP en CI.

La evaluación real del wheel y contenedores corre aparte en el workflow E2E.
"""
import json

import pytest

from scripts import smoke_despliegue as smoke


@pytest.mark.parametrize("error_detail", [
    "chunk_id no puede estar vacio ni repetido.",
    [{"loc": ["body", "parrafos"], "msg": "Duplicate chunk_id"}],
])
def test_smoke_accepts_both_fastapi_422_error_shapes(monkeypatch, error_detail):
    def fake_request(base, ruta, *, metodo="GET", json_data=None, timeout=30):
        if ruta == "/api/salud/viva":
            status, result = 200, {"estado": "vivo"}
        elif ruta == "/api/salud/lista":
            status, result = 200, {"estado": "listo"}
        elif ruta == "/api/estado":
            status, result = 200, {"listo": True, "modelo": {"version": "test"}}
        elif ruta == "/api/capacidades":
            status, result = 200, {
                "recomendacion_articulos": {"disponible": True},
                "top3_manual": {"disponible": True},
                "top3_scibert": {"disponible": False},
                "clasificacion_funcion_cita": {"disponible": False},
                "BM25_lexico_baseline": True,
            }
        elif ruta == "/api/recomendar":
            status, result = 200, {"total": 1, "recomendaciones": [{"id": "paper"}]}
        elif ruta == "/api/top3-fragmentos":
            parrafos = json_data["parrafos"]
            if parrafos[0]["chunk_id"] == "too-large":
                return 413, b"<html>large</html>", 1.0
            if len({p["chunk_id"] for p in parrafos}) < len(parrafos):
                status, result = 422, {"detail": error_detail}
            else:
                status, result = 200, {
                    "metodo": "BM25_lexico_baseline",
                    "total_resultados": 1,
                    "clasificacion": {"estado": "no_ejecutada"},
                }
        elif ruta in {"/", "/static/top3.html", "/static/top3.js", "/static/top3.css"}:
            samples = {
                "/": b"<html>Home</html>",
                "/static/top3.html": b"<html id='capacidades-servicio'></html>",
                "/static/top3.js": b"/api/capacidades",
                "/static/top3.css": b"body {" + b"x" * 200 + b"}",
            }
            return 200, samples[ruta], 1.0
        else:
            raise AssertionError(f"Ruta de smoke no esperada: {ruta}")
        return status, json.dumps(result).encode("utf-8"), 1.0

    monkeypatch.setattr(smoke, "solicitar", fake_request)
    report = smoke.smoke("http://api", "http://dashboard", timeout=5, check_ingress_limit=True)
    assert report["status"] == "ok"
    assert report["n_checks"] == 13
    assert any(item["name"] == "limite_ingress_413" for item in report["checks"])
    assert "SciBERT" in report["warning"]


def test_smoke_detects_false_positive_scibert(monkeypatch):
    def lie(base, ruta, *, metodo="GET", json_data=None, timeout=30):
        if ruta == "/api/salud/viva":
            return 200, b'{"estado":"vivo"}', 0.1
        if ruta == "/api/salud/lista":
            return 200, b'{"estado":"listo"}', 0.1
        if ruta == "/api/estado":
            return 200, b'{"listo":true,"modelo":{}}', 0.1
        if ruta == "/api/capacidades":
            return 200, (
                b'{"recomendacion_articulos":{"disponible":true},'
                b'"top3_manual":{"disponible":true},'
                b'"top3_scibert":{"disponible":true},'
                b'"clasificacion_funcion_cita":{"disponible":false}}'
            ), 0.1
        raise AssertionError("No debe llegar a los otros endpoints")

    monkeypatch.setattr(smoke, "solicitar", lie)
    with pytest.raises(RuntimeError, match="SciBERT"):
        smoke.smoke("http://api", "http://dashboard", timeout=5)
