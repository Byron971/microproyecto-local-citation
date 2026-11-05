"""Smoke E2E de DESPLIEGUE: API real + Nginx + modelo empaquetado.

No ejecuta clasificación de nueve funciones ni evaluación del Test Gold.
Python estándar; apto para CI y para validar una URL autorizada de staging.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def solicitar(
    base: str,
    ruta: str,
    *,
    metodo: str = "GET",
    json_data: object | None = None,
    timeout: float = 30.0,
) -> tuple[int, bytes, float]:
    url = base.rstrip("/") + ruta
    body = None if json_data is None else json.dumps(json_data).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=metodo)
    before = perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(2_000_000), round((perf_counter() - before) * 1000, 2)
    except HTTPError as error:
        with error:
            return error.code, error.read(2_000_000), round((perf_counter() - before) * 1000, 2)


def _expect(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def _json(blob: bytes) -> dict:
    try:
        result = json.loads(blob)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("La API no devolvió JSON válido") from exc
    if not isinstance(result, dict):
        raise RuntimeError("La respuesta no contiene un objeto JSON")
    return result


def smoke(api: str, dashboard: str, timeout: float, check_ingress_limit: bool = False) -> dict:
    """Prueba endpoints públicos con al menos una inferencia real empaquetada."""
    checks: list[dict] = []

    def check(label: str, base: str, path: str, *, expected: int = 200, method: str = "GET",
              payload: object | None = None) -> tuple[dict | None, bytes]:
        code, data, duration = solicitar(base, path, metodo=method, json_data=payload, timeout=timeout)
        _expect(code == expected, f"{label}: HTTP {code} (se esperaba {expected})")
        checks.append({"name": label, "status": code, "latency_ms": duration})
        if path.startswith("/api/") and expected != 413:
            return _json(data), data
        return None, data

    live, _ = check("liveness", api, "/api/salud/viva")
    _expect(live == {"estado": "vivo"}, "liveness inválido")
    ready, _ = check("readiness", api, "/api/salud/lista")
    _expect(ready == {"estado": "listo"}, "readiness no confirma recursos cargados")

    estado, _ = check("modelo_empacado_real", api, "/api/estado")
    _expect(estado.get("listo") is True and isinstance(estado.get("modelo"), dict),
            "No se cargó el modelo empaquetado de recomendación")

    capacidades, _ = check("capacidades", api, "/api/capacidades")
    _expect(capacidades["recomendacion_articulos"]["disponible"] is True, "Recomendador no disponible")
    _expect(capacidades["top3_manual"]["disponible"] is True, "BM25 no disponible")
    _expect(capacidades["top3_scibert"]["disponible"] is False,
            "SciBERT no debe publicarse como integrado antes de validarlo")
    _expect(capacidades["clasificacion_funcion_cita"]["disponible"] is False,
            "Clasificador no debe publicarse como integrado antes de validarlo")

    recomendacion, _ = check(
        "inferencia_de_articulos", api, "/api/recomendar", method="POST",
        payload={"contexto": "Graph neural networks improve node representations and message passing.", "top_k": 2},
    )
    _expect(isinstance(recomendacion.get("recomendaciones"), list), "Falta salida de inferencia")
    _expect(recomendacion.get("total", 0) >= 1, "El recomendador no produjo candidatos")

    corpus = {
        "contexto": "Neural graph methods TARGETCIT",
        "cited_id": "DOCUMENTO-DEMO-SINTETICO",
        "parrafos": [
            {"chunk_id": "c1", "texto": "Neural graph methods learn node representations.", "seccion": "Methods"},
            {"chunk_id": "c2", "texto": "We measure memory consumption of neural systems.", "seccion": "Results"},
        ],
    }
    top3, _ = check("top3_bm25", api, "/api/top3-fragmentos", method="POST", payload=corpus)
    _expect(top3.get("metodo") == "BM25_lexico_baseline", "Método Top-3 incorrecto")
    _expect(top3.get("total_resultados", 0) >= 1, "El baseline BM25 no retornó fragmentos")
    _expect(top3.get("clasificacion", {}).get("estado") == "no_ejecutada", "Clasificación ficticia")

    invalid = {**corpus, "parrafos": [corpus["parrafos"][0], corpus["parrafos"][0]]}
    response, _ = check(
        "validacion_422", api, "/api/top3-fragmentos",
        method="POST", payload=invalid, expected=422,
    )
    # FastAPI devuelve lista para errores Pydantic y nuestro validador de\n    # chunk_id devuelve un texto; ambos son errores 422 documentados.\n    detalle = response.get("detail")\n    _expect(isinstance(detalle, (str, list)) and bool(detalle),\n            "Error 422 sin detalle de validación")

    _, html = check("tablero_nginx", dashboard, "/")
    _expect(b"<html" in html.lower(), "El dashboard no devuelve HTML")
    _, html_top3 = check("interfaz_top3", dashboard, "/static/top3.html")
    _expect(b"capacidades-servicio" in html_top3, "La interfaz no informa disponibilidad real")
    _, js = check("js_top3", dashboard, "/static/top3.js")
    _expect(b"/api/capacidades" in js, "El JavaScript no consulta capacidades del backend")

    _, through_proxy = check("proxy_api", dashboard, "/api/capacidades")
    _expect(b"BM25_lexico_baseline" in through_proxy, "Nginx no enruta API a FastAPI")

    if check_ingress_limit:
        huge = {**corpus, "parrafos": [
            {"chunk_id": "too-large", "texto": "x" * 150_000, "seccion": "Methods"},
        ]}
        check("limite_ingress_413", dashboard, "/api/top3-fragmentos",
              expected=413, method="POST", payload=huge)

    return {
        "status": "ok",
        "type": "deployment_smoke_not_scientific_evaluation",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_checks": len(checks),
        "checks": checks,
        "warning": "No demuestra clasificación de 9 funciones, SciBERT ni Test Gold humano.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke E2E del despliegue real actual.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8080")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--check-ingress-limit", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = smoke(args.api_url, args.dashboard_url, args.timeout, args.check_ingress_limit)
    except (RuntimeError, ValueError, OSError, URLError) as error:
        print(f"Smoke de despliegue FALLIDO: {error}", file=sys.stderr)
        return 2
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Smoke de despliegue OK: {result['n_checks']} comprobaciones.")
    for check in result["checks"]:
        print(f"  {check['name']}: HTTP {check['status']} | {check['latency_ms']:.2f} ms")
    print("ATENCIÓN: SciBERT, clasificación de funciones y Test Gold aún no están evaluados aquí.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
