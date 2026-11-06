"""Validación de configuración común para proveedores de evaluación.

Se aplica al construir un cliente real. Los errores de configuración se
devuelven sin incluir claves ni URLs con información sensible.
"""
from __future__ import annotations

import math
import os
from typing import Mapping
from urllib.parse import urlsplit


def request_timeout_seconds(environ: Mapping[str, str] | None = None) -> float:
    env = os.environ if environ is None else environ
    raw = env.get("CITATION_PROVIDER_TIMEOUT_SECONDS", "60")
    try:
        seconds = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("CITATION_PROVIDER_TIMEOUT_SECONDS debe ser un número") from exc
    if not math.isfinite(seconds) or not 1 <= seconds <= 600:
        raise ValueError("CITATION_PROVIDER_TIMEOUT_SECONDS debe estar entre 1 y 600")
    return seconds


def validate_openweight_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("OPENWEIGHT_BASE_URL no puede estar vacía")
    try:
        url = urlsplit(base_url.strip())
        hostname = url.hostname
        port = url.port
    except ValueError as exc:
        raise ValueError("OPENWEIGHT_BASE_URL tiene sintaxis inválida") from exc
    if (
        url.scheme not in {"http", "https"} or not hostname
        or url.username is not None or url.password is not None
        or url.query or url.fragment or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError(
            "OPENWEIGHT_BASE_URL requiere HTTP(S), host válido y sin credenciales ni query"
        )
    return base_url.strip()
