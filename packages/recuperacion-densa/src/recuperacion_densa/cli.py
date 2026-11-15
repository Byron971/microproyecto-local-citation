"""Raiz de composicion: evaluacion offline SciBERT Top-3 vs BM25 (solo train, sin gold).

Uso (desde la raiz del repo):
  uv run --project packages/recuperacion-densa python -m recuperacion_densa.cli --solo-validar
  uv run --project packages/recuperacion-densa --group modelo python -m recuperacion_densa.cli_modelo
(`cli` no importa torch; `cli_modelo` le inyecta el codificador real.)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from . import adaptador_proyecto_grado as ad
from . import dominio, servicio
from .cache_embeddings import CacheDisco
from .revision import REVISION_SCIBERT

SALIDA = ad.REPO / "proyecto_de_grado/artifacts/recuperacion_densa_a1"
MANIFIESTO_MODELO = (ad.REPO / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1"
                     / "manifiesto_modelo.json")
AVISO = "Solo comparacion tecnica train; sin Gold. Recall@3 no calculado."
COL_TOP3 = ["context_id", "metodo", "posicion", "cited_id", "chunk_id", "seccion",
            "perfil_seccion", "paragraph_indices", "puntaje"]
COL_CMP = ["context_id", "cited_id", "n_chunks", "interseccion", "solape_3", "jaccard",
           "mismo_top1", "abstencion_bm25"]
COL_LAT = ["tipo", "id", "segundos"]


def _sha_archivo(ruta: Path) -> str | None:
    return hashlib.sha256(ruta.read_bytes()).hexdigest() if ruta.is_file() else None


def _git() -> dict:
    def run(*a):
        return subprocess.run(["git", "-C", str(ad.REPO), *a], capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        return {"head": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"head": None, "dirty": None}


def _csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    with ruta.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def _json(ruta: Path, obj) -> None:
    with ruta.open("x", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _filas_top3(ev: servicio.Evaluacion, perfil) -> list[dict]:
    filas = []
    for ctx in sorted(ev.denso):
        for metodo, tops, clave in (("scibert", ev.denso, "similitud_coseno"),
                                    ("bm25", ev.bm25, "puntaje_bm25")):
            for pos, r in enumerate(tops[ctx], 1):
                filas.append({
                    "context_id": ctx, "metodo": metodo, "posicion": pos,
                    "cited_id": r["cited_id"], "chunk_id": r["chunk_id"],
                    "seccion": r.get("seccion") or dominio.SIN_SECCION,
                    "perfil_seccion": perfil(r.get("seccion")),
                    "paragraph_indices": "|".join(map(str, r.get("paragraph_indices") or [])),
                    "puntaje": r[clave]})
    return filas


def _md_ejemplos(ejemplos: list[dict]) -> str:
    out = ["# Ejemplos Top-3 (train, sin gold)", "",
           "Extractos de <=240 caracteres. Muestran acuerdo/desacuerdo, no relevancia.", ""]
    for e in ejemplos:
        out += [f"## {e['context_id']} ({e['cited_id']}) — coinciden {e['interseccion']}/3", "",
                f"> {e['contexto']}", ""]
        for m in ("denso", "bm25"):
            out.append(f"**{m}**")
            for pos, r in enumerate(e[m], 1):
                out.append(f"{pos}. `{r['chunk_id']}` ({r.get('seccion')}): {r['extracto']}")
            out.append("")
    return "\n".join(out) + "\n"


def escribir(ev: servicio.Evaluacion, salida: Path, perfil) -> list[Path]:
    _json(salida / "resumen.json", ev.resumen)
    _csv(salida / "top3.csv", COL_TOP3, _filas_top3(ev, perfil))
    _csv(salida / "comparacion.csv", COL_CMP, ev.comparacion)
    lat = ev.latencias
    filas_lat = [{"tipo": "warmup", "id": "", "segundos": lat["warmup_s"]}]
    for tipo in ("embedding_articulo", "consulta_densa", "bm25"):
        filas_lat += [{"tipo": tipo, "id": i, "segundos": s} for i, s in lat["muestras"][tipo]]
    _csv(salida / "latencias.csv", COL_LAT, filas_lat)
    _json(salida / "latencias_resumen.json", {k: v for k, v in lat.items() if k != "muestras"})
    _json(salida / "ejemplos_top3.json", ev.ejemplos)
    with (salida / "ejemplos_top3.md").open("x", encoding="utf-8") as f:
        f.write(_md_ejemplos(ev.ejemplos))
    _csv(salida / "diversidad.csv", ["cited_id", "contextos", "n_chunks", "chunks_distintos_top3",
                                     "cobertura", "chunk_top1_mas_frecuente", "cobertura_bm25",
                                     "chunk_top1_mas_frecuente_bm25"], ev.diversidad)
    return sorted(p for p in salida.iterdir() if p.is_file())


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--raw", type=Path, default=ad.RAW)
    ap.add_argument("--cache-ocl", type=Path, default=ad.CACHE)
    ap.add_argument("--entrada", type=Path, help="JSON S2.2 ya exportado (reemplaza el constructor)")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--revision", default=REVISION_SCIBERT)
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--sin-cache", action="store_true")
    ap.add_argument("--cache", type=Path, help="carpeta de la cache (def.: SALIDA/cache_embeddings)")
    ap.add_argument("--ejemplos", type=int, default=12)
    ap.add_argument("--semilla", type=int, default=102)
    ap.add_argument("--exportar-casos", type=Path)
    ap.add_argument("--calibracion-origen", type=Path)
    ap.add_argument("--calibracion-carpeta", type=Path)
    ap.add_argument("--solo-validar", action="store_true")
    return ap


def main(argv: list[str] | None = None, *,
         fabrica_codificador: Callable[[argparse.Namespace], object] | None = None,
         reloj: Callable[[], float] = time.perf_counter) -> int:
    ap = _parser()
    args = ap.parse_args(argv)
    if bool(args.calibracion_origen) != bool(args.calibracion_carpeta):
        ap.error("--calibracion-origen y --calibracion-carpeta van juntos")
    salida = args.salida or SALIDA / time.strftime("corrida_%Y%m%d_%H%M%S")
    if not args.solo_validar and salida.exists() and any(salida.iterdir()):
        ap.exit(2, f"Error: {salida} ya existe con contenido; no se sobrescribe.\n")
    try:
        excluidos = ad.cargar_exclusiones()
        if args.entrada:
            doc = json.loads(args.entrada.read_text(encoding="utf-8-sig"))
            casos, meta = doc["casos"], doc.get("resumen", {})
            if args.limite:
                casos = casos[:args.limite]
        else:
            indice = ad.cargar_indice(args.raw)
            papers = json.loads((args.raw / "papers.json").read_text(encoding="utf-8-sig"))
            casos, meta = servicio.construir_casos(indice, papers, args.cache_ocl, ad.integrar,
                                                   ad.fragmentar, excluidos, args.limite)
        validacion = dominio.validar_casos(casos, excluidos)
        print(f"Corpus valido: {validacion['contextos']} contextos / "
              f"{validacion['articulos']} articulos")
        if args.exportar_casos:
            with args.exportar_casos.open("x", encoding="utf-8") as f:
                json.dump(servicio.exportar_casos(casos, meta), f, ensure_ascii=False, indent=1)
    except (OSError, KeyError, TypeError, ValueError) as exc:  # FileExistsError es OSError
        ap.exit(2, f"Error de validacion: {exc}\n")
    if args.solo_validar:
        print(AVISO if not args.calibracion_origen else dominio.ETIQUETA_GOLD)
        return 0

    try:
        gold = (ad.cargar_gold_calibracion(args.calibracion_origen, args.calibracion_carpeta)
                if args.calibracion_origen else None)
        t0 = reloj()
        if fabrica_codificador is None:
            ap.exit(2, "Error: falta un codificador; use `cli_modelo` o --solo-validar.\n")
        codificador = fabrica_codificador(args)
        carga = reloj() - t0
        if gold is not None:
            esperado = {c["context_id"] for c in casos}
            if {ctx for ctx, _ in gold} != esperado:
                raise ad.ProtocoloError("Los contextos del gold no coinciden con los evaluados.")
        cache = None if args.sin_cache else CacheDisco(args.cache or SALIDA / "cache_embeddings")
        ev = servicio.evaluar(casos, codificador, ad.lexico, cache, reloj, ad.perfil_seccion,
                              max_length=args.max_length, pooling=getattr(codificador, "pooling", "mean"),
                              n_ejemplos=args.ejemplos, semilla=args.semilla, excluidos=excluidos,
                              gold=gold, puntuar=ad.puntuar)
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, ad.ProtocoloError) as exc:
        ap.exit(2, f"Error de evaluacion (no se escribio nada): {exc}\n")
    ev.latencias["carga_modelo_s"] = carga
    mem = getattr(codificador, "memoria_gpu_mb", lambda: None)()
    ev.latencias["memoria_gpu_max_mb"] = mem

    # escritura atomica: todo se genera en <salida>.tmp y se renombra al final
    final = salida
    salida = final.with_name(final.name + ".tmp")
    shutil.rmtree(salida, ignore_errors=True)
    salida.mkdir(parents=True)
    archivos = escribir(ev, salida, ad.perfil_seccion)
    mm = _sha_archivo(MANIFIESTO_MODELO)
    _json(salida / "manifiesto.json", {
        "estado": ev.resumen["estado"], "argv": sys.argv[1:] if argv is None else argv,
        "git": _git(), "encoder": codificador.info(), "sha256_manifiesto_modelo": mm,
        "entradas": {"train.json": _sha_archivo(args.raw / "train.json"),
                     "contexts.json": _sha_archivo(args.raw / "contexts.json"),
                     "entrada_s22": _sha_archivo(args.entrada) if args.entrada else None},
        "exclusiones": {p.name: _sha_archivo(p) for p in ad.EXCLUSIONES},
        "salidas": {p.name: _sha_archivo(p) for p in archivos},
    })
    if final.exists():
        final.rmdir()  # solo llega aqui vacia (verificado al inicio)
    salida.rename(final)
    salida = final
    c = ev.resumen["comparacion"]
    print(f"Evaluados {validacion['contextos']} contextos | salida: {salida}")
    print(json.dumps(c, ensure_ascii=False))
    print(AVISO if gold is None else dominio.ETIQUETA_GOLD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
