"""PASO CON RED: descarga de ACL OCL de los citados requeridos hacia la `cache_ocl` compartida.

Uso (desde la raiz del repo):
  PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.descarga_ocl
Lee `citados_requeridos.txt` (salida de `cli preparar`) y escribe `manifiesto_ocl.json`."""
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import adaptador_proyecto_grado as ad
from .cli import EVIDENCIAS

ESTADOS = ("descargado", "404", "error")


def leer_citados(ruta: Path) -> list[str]:
    if not Path(ruta).is_file():
        raise FileNotFoundError(f"Falta {ruta}: ejecute `cli preparar` primero.")
    ids = [l.strip() for l in Path(ruta).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("citados_requeridos.txt vacio o con duplicados.")
    return ids


def descargar_uno(acl_id: str, cache: Path, descargar=None) -> dict:
    descargar = descargar or ad.descargar_ocl
    try:
        doc = descargar(acl_id, cache)
    except Exception as exc:  # fallo de red: se registra en el manifiesto, no se oculta
        return {"id": acl_id, "estado": "error", "detalle": f"{type(exc).__name__}: {exc}"}
    if doc is None:
        return {"id": acl_id, "estado": "404"}
    ruta = Path(cache) / f"{acl_id}.json"
    return {"id": acl_id, "estado": "descargado",
            "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}


def construir_manifiesto(resultados: list[dict], citados_sha: str) -> dict:
    resultados = sorted(resultados, key=lambda r: r["id"])
    cuerpo = {
        "citados_requeridos_sha256": citados_sha,
        "n_citados": len(resultados),
        "estados": {e: sum(r["estado"] == e for r in resultados) for e in ESTADOS},
        "descargas": resultados,
    }
    canon = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {**cuerpo, "sha256_manifiesto": hashlib.sha256(canon.encode("utf-8")).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--citados", type=Path, default=EVIDENCIAS / "citados_requeridos.txt")
    ap.add_argument("--cache", type=Path, default=ad.CACHE_OCL)
    ap.add_argument("--manifiesto", type=Path, default=EVIDENCIAS / "manifiesto_ocl.json")
    ap.add_argument("--hilos", type=int, default=4)
    ap.add_argument("--limite", type=int, default=None, help="solo los primeros N citados")
    a = ap.parse_args(argv)
    try:
        if a.hilos < 1 or (a.limite is not None and a.limite < 1):
            raise ValueError("--hilos y --limite deben ser positivos.")
        ids = leer_citados(a.citados)
        if a.manifiesto.exists():
            raise FileExistsError(f"No se sobrescribe: {a.manifiesto}")
        citados_sha = hashlib.sha256(a.citados.read_bytes()).hexdigest()
        if a.limite:
            ids = ids[:a.limite]
        a.cache.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=a.hilos) as pool:
            resultados = list(pool.map(lambda i: descargar_uno(i, a.cache), ids))
        manifiesto = construir_manifiesto(resultados, citados_sha)
        a.manifiesto.parent.mkdir(parents=True, exist_ok=True)
        with a.manifiesto.open("x", encoding="utf-8") as f:
            f.write(json.dumps(manifiesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Descarga OCL | {len(ids)} citados | {manifiesto['estados']} | {a.manifiesto}")
    return 1 if manifiesto["estados"]["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
