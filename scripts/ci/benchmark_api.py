"""Benchmark A7 operacional sin Gold ni APIs comerciales: localhost por defecto.

La latencia se mide de extremo a extremo por HTTP, con muestras secuenciales
tras warmup. No calcula F1/Recall ni aproxima costos cloud sin tarifas reales.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_PAYLOADS = {
    "recommend": ("/api/recomendar", {
        "contexto": "Graph neural networks for representation learning and language processing.",
        "top_k": 3,
    }),
    "top3-bm25": ("/api/top3-fragmentos", {
        "contexto": "Graph neural networks learn embeddings TARGETCIT.",
        "cited_id": "P14-1001",
        "parrafos": [
            {"chunk_id": "p1", "texto": "Graph methods model node embeddings."},
            {"chunk_id": "p2", "texto": "Language models use token embeddings."},
            {"chunk_id": "p3", "texto": "Graph networks learn structured representation."},
        ],
    }),
    "top3-scibert": ("/api/top3-scibert", {
        "contexto": "Graph neural networks learn embeddings TARGETCIT.",
        "cited_id": "P14-1001",
        "parrafos": [
            {"chunk_id": "p1", "texto": "Graph methods model node embeddings."},
            {"chunk_id": "p2", "texto": "Language models use token embeddings."},
            {"chunk_id": "p3", "texto": "Graph networks learn structured representation."},
        ],
    }),
}


def validar_url(base: str, permitir_remoto: bool = False) -> str:
    url = urlparse(base)
    if (url.scheme not in ("http", "https") or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or url.path not in ("", "/")):
        raise ValueError("Se exige URL base HTTP(S) sin usuario, ruta, query ni fragmento.")
    local = url.hostname in ("localhost", "127.0.0.1", "::1")
    if not local and (not permitir_remoto or url.scheme != "https"):
        raise ValueError("Benchmark remoto requiere HTTPS y --permitir-remoto explícito.")
    return base.rstrip("/")


def resumir(values: list[float]) -> dict:
    if not values:
        raise ValueError("Se necesitan latencias.")
    if not all(math.isfinite(v) and v >= 0 for v in values):
        raise ValueError("Latencia inválida.")
    vals = sorted(values)

    def percentile(q):
        return vals[max(1, math.ceil(q * len(vals) / 100)) - 1]

    return {
        "n": len(vals),
        "min_ms": min(vals),
        "p50_ms": percentile(50),
        "p95_ms": percentile(95),
        "media_ms": statistics.fmean(vals),
        "max_ms": max(vals),
    }


def _request(url: str, data: dict, timeout: float) -> dict:
    encoded = json.dumps(data, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=encoded, method="POST",
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return json.load(response)


def benchmark(base: str, endpoint: str, muestras: int = 20, warmup: int = 3,
              timeout: float = 15.0, *, request_fn=_request) -> dict:
    if endpoint not in _PAYLOADS or not 1 <= muestras <= 100 or not 0 <= warmup <= 20:
        raise ValueError("Endpoint o cantidad de muestras fuera de rango.")
    if not 0 < timeout <= 120:
        raise ValueError("Timeout inválido.")
    path, body = _PAYLOADS[endpoint]
    url = base.rstrip("/") + path
    latencies = []
    for i in range(warmup + muestras):
        start = time.perf_counter()
        response = request_fn(url, body, timeout)
        elapsed = (time.perf_counter() - start) * 1000
        if endpoint == "recommend":
            if not isinstance(response.get("recomendaciones"), list) or not response["recomendaciones"]:
                raise RuntimeError("Respuesta del modelo real no contiene recomendaciones.")
        elif not isinstance(response.get("fragmentos"), list) or response.get("metodo") != (
            "BM25_lexico_baseline" if endpoint == "top3-bm25" else "scibert_base_mean_pooling_cosine"
        ):
            raise RuntimeError("Respuesta inválida o backend de Top-3 diferente al solicitado.")
        if i >= warmup:
            latencies.append(round(elapsed, 4))
    return {
        "estado": "benchmark_tecnico_no_gold",
        "endpoint": endpoint,
        "metodo": "HTTP_secuencial_cliente_sin_concurrencia",
        "muestras": muestras,
        "warmup_excluidos": warmup,
        "timeout_segundos": timeout,
        "plataforma_cliente": platform.system(),
        "sha256_payload": hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "latencias_ms": latencies,
        "resumen": resumir(latencies),
        "advertencia": (
            "Mide tiempo HTTP cliente del endpoint disponible, no relevancia Gold, "
            "calidad del clasificador ni costos de AWS."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--permitir-remoto", action="store_true")
    p.add_argument("--endpoint", choices=sorted(_PAYLOADS), default="recommend")
    p.add_argument("--muestras", type=int, default=20)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--salida", type=Path, required=True, help="Ruta nueva para JSON (no sobrescribe).")
    a = p.parse_args(argv)
    try:
        base = validar_url(a.url, a.permitir_remoto)
        result = benchmark(base, a.endpoint, a.muestras, a.warmup, a.timeout)
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        with a.salida.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except (ValueError, OSError, HTTPError, URLError, RuntimeError) as exc:
        p.exit(2, f"Benchmark no completado: {exc}\n")
    print(json.dumps(result["resumen"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
