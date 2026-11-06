"""Cache de embeddings en disco (array('d'), escritura atomica) y en memoria."""
from __future__ import annotations

import hashlib
import math
import os
import tempfile
from array import array
from pathlib import Path


def clave_embedding(model_id: str, revision: str, max_length: int, pooling: str, texto: str) -> str:
    base = "\x1f".join((model_id, revision, str(max_length), pooling, texto))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class CacheMemoria:
    def __init__(self) -> None:
        self._d: dict[str, tuple[float, ...]] = {}

    def get(self, clave: str):
        return self._d.get(clave)

    def put(self, clave: str, vector) -> None:
        self._d[clave] = tuple(vector)


class CacheDisco:
    def __init__(self, carpeta: Path) -> None:
        self.carpeta = Path(carpeta)

    def _ruta(self, clave: str) -> Path:
        if not clave or any(c not in "0123456789abcdef" for c in clave):
            raise ValueError("Clave de cache invalida.")
        return self.carpeta / f"{clave}.f64"

    def get(self, clave: str):
        ruta = self._ruta(clave)
        try:
            datos = ruta.read_bytes()
        except FileNotFoundError:
            return None
        if not datos or len(datos) % 8:
            return None  # archivo truncado/corrupto: se trata como fallo de cache
        a = array("d")
        a.frombytes(datos)
        if not all(math.isfinite(x) for x in a):
            return None
        return tuple(a)

    def put(self, clave: str, vector) -> None:
        ruta = self._ruta(clave)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.carpeta, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(array("d", vector).tobytes())
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, ruta)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
