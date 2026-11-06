"""PASO DE RED aislado: muestra fija con semilla de citados ACL-200 -> cache_ocl.

Uso (desde la raiz del repo):
  uv run --project packages/auditoria-corpus python -m auditoria_corpus.descarga --n 200 --semilla 101
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import adaptador_proyecto_grado as ad

SPLITS = ("train", "val", "test")


def citados_por_split(indice) -> dict[str, list[str]]:
    """Cada citado se asigna al primer split (train>val>test) donde aparece."""
    primero: dict[str, str] = {}
    for cid in sorted(indice.by_context):
        cited = indice.contexts[cid]["refid"]
        split = indice.by_context[cid]
        if cited not in primero or SPLITS.index(split) < SPLITS.index(primero[cited]):
            primero[cited] = split
    return {s: sorted(c for c, sp in primero.items() if sp == s) for s in SPLITS}


def asignar(cantidades: dict[str, int], n: int) -> dict[str, int]:
    """Reparto proporcional por mayor resto, determinista."""
    total = sum(cantidades.values())
    n = min(n, total)
    base = {s: n * c // total for s, c in cantidades.items()}
    restos = sorted(cantidades, key=lambda s: (-(n * cantidades[s] % total), s))
    for s in restos[: n - sum(base.values())]:
        base[s] += 1
    return base


def elegir_muestra(indice, n: int, semilla: int) -> dict[str, list[str]]:
    grupos = citados_por_split(indice)
    cuotas = asignar({s: len(v) for s, v in grupos.items()}, n)
    rng = random.Random(semilla)
    return {s: sorted(rng.sample(grupos[s], cuotas[s])) for s in SPLITS}


def _descargar(acl_id: str, cache: Path) -> dict:
    try:
        doc = ad.descargar_ocl(acl_id, cache)
    except Exception as exc:  # fallo de red: se registra, no se oculta
        return {"id": acl_id, "estado": "error", "detalle": f"{type(exc).__name__}: {exc}"}
    if doc is None:
        return {"id": acl_id, "estado": "404"}
    ruta = cache / f"{acl_id}.json"
    return {"id": acl_id, "estado": "descargado", "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--semilla", type=int, default=101)
    ap.add_argument("--raw", type=Path, default=ad.RAW)
    ap.add_argument("--cache", type=Path, default=ad.CACHE)
    ap.add_argument("--manifiesto", type=Path,
                    default=ad.REPO / "proyecto_de_grado/artifacts/auditoria_a1/manifiesto_muestra.json")
    ap.add_argument("--hilos", type=int, default=4)
    args = ap.parse_args(argv)
    if args.n < 1:
        ap.error("--n debe ser positivo")
    indice = ad.cargar_indice(args.raw)
    muestra = elegir_muestra(indice, args.n, args.semilla)
    ids = [i for s in SPLITS for i in muestra[s]]
    args.cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.hilos) as pool:
        resultados = sorted(pool.map(lambda i: _descargar(i, args.cache), ids), key=lambda r: r["id"])
    cuerpo = {
        "semilla": args.semilla, "n_solicitado": args.n, "n_efectivo": len(ids),
        "ids_por_split": muestra, "descargas": resultados,
    }
    canon = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    cuerpo["sha256_manifiesto"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    args.manifiesto.parent.mkdir(parents=True, exist_ok=True)
    args.manifiesto.write_text(json.dumps(cuerpo, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    estados = {e: sum(r["estado"] == e for r in resultados) for e in ("descargado", "404", "error")}
    print(f"Descarga A1 | semilla {args.semilla} | {len(ids)} citados | {estados} | {args.manifiesto}")
    return 1 if estados["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
