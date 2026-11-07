"""Raiz de composicion sin torch.

Uso (desde la raiz del repo):
  PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.cli \\
      preparar --solo-validar
  PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.cli preparar
Todo resultado es PROVISIONAL: las etiquetas de entrenamiento y de eval son de Haiku.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from auditoria_corpus.dominio import perfil_seccion
from recuperacion_densa.cache_embeddings import CacheDisco
from recuperacion_densa.dominio import SIN_SECCION

from . import adaptador_proyecto_grado as ad
from . import dominio, servicio

EVIDENCIAS = ad.REPO / "proyecto_de_grado/docs/evidencias_clasificacion_a4"
ARTEFACTOS = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/preparacion"
COL_MOTIVOS = ["conjunto", "context_id", "motivo"]
COL_ETIQUETAS = ["context_id", "indice", "etiqueta"]
COL_TOP3 = ["context_id", "posicion", "cited_id", "chunk_id", "seccion", "perfil_seccion",
            "paragraph_indices", "puntaje"]
TOP3_A1 = ad.REPO / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/top3.csv"
CACHE_EMBEDDINGS = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/cache_embeddings"


def crear_fuentes():
    return ad.FuentesProyectoGrado()


def _sha_archivo(ruta: Path) -> str | None:
    ruta = Path(ruta)
    return hashlib.sha256(ruta.read_bytes()).hexdigest() if ruta.is_file() else None


def _git() -> dict:
    def run(*a):
        return subprocess.run(["git", "-C", str(ad.REPO), *a], capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        return {"head": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"head": None, "dirty": None}


def _publicar(destino: Path, contenido: str) -> None:
    """Escritura atomica que nunca sobrescribe: .tmp y enlace duro (falla si ya existe)."""
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(contenido, encoding="utf-8", newline="")
    try:
        os.link(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)


def _csv_texto(columnas: list[str], filas: list[dict]) -> str:
    buffer = io.StringIO()
    w = csv.DictWriter(buffer, fieldnames=columnas, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(filas)
    return buffer.getvalue()


def _json_texto(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _lineas(valores) -> str:
    return "".join(f"{v}\n" for v in valores)


def _resumen(r: dict) -> dict:
    conjuntos = r["conjuntos"]
    abst: dict = {}
    for a in r["abstenciones"]:
        por = abst.setdefault(a["conjunto"], {})
        por[a["motivo"]] = por.get(a["motivo"], 0) + 1
    return {
        "estado": r["estado"],
        "fuente_etiquetas": r["fuente_etiquetas"],
        "casos": {n: len(c) for n, c in conjuntos.items()},
        "abstenciones": abst,
        "excluidos": len(r["excluidos"]),
        "citados_requeridos": len(r["citados_requeridos"]),
        "total_fugas": r["fugas"]["total_fugas"],
    }


def _archivos(r: dict, fuentes, args) -> tuple[dict[Path, str], dict[Path, str]]:
    """(evidencias versionadas, artefactos ignorados por git) -> contenido."""
    conjuntos = r["conjuntos"]
    ev, art = {}, {}
    for nombre, casos in conjuntos.items():
        ev[args.salida / f"ids_{nombre}.txt"] = _lineas(sorted(c["context_id"] for c in casos))
    for nombre in ("train", "val", "eval_2015"):
        art[args.artefactos / f"etiquetas_{nombre}.csv"] = _csv_texto(COL_ETIQUETAS, [
            {"context_id": c["context_id"], "indice": c["indice"], "etiqueta": c["etiqueta"]}
            for c in conjuntos[nombre]])
    ev[args.salida / "abstenciones.csv"] = _csv_texto(COL_MOTIVOS, r["abstenciones"])
    ev[args.salida / "excluidos_preparacion.csv"] = _csv_texto(COL_MOTIVOS, r["excluidos"])
    ev[args.salida / "fugas.json"] = _json_texto(r["fugas"])
    ev[args.salida / "citados_requeridos.txt"] = _lineas(r["citados_requeridos"])
    hashes = {}
    for nombre in ("train", "val", "eval_2015"):
        hashes[nombre] = {
            "ids_sha256": dominio.sha_ids(c["context_id"] for c in conjuntos[nombre]),
            "labels_sha256": dominio.sha_etiquetas(
                {c["context_id"]: c["indice"] for c in conjuntos[nombre]}),
        }
    hashes["gold_v2"] = {"ids_sha256": dominio.sha_ids(c["context_id"] for c in conjuntos["gold_v2"])}
    manifiesto = {
        **_resumen(r), "hashes": hashes, "git": _git(), "limite": args.limite,
        "entradas": {n: _sha_archivo(p) for n, p in sorted(fuentes.rutas().items())},
    }
    ev[args.salida / "manifiesto_preparacion.json"] = _json_texto(manifiesto)
    return ev, art


def preparar(args) -> int:
    fuentes = crear_fuentes()
    r = servicio.cargar_conjuntos(fuentes, args.fuente_etiquetas, args.limite)
    print(_json_texto(_resumen(r)), end="")
    if args.solo_validar:
        print("--solo-validar: no se escribio nada.")
        return 0
    ev, art = _archivos(r, fuentes, args)
    existentes = [p for p in (*ev, *art) if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    for carpeta in (args.salida, args.artefactos):
        carpeta.mkdir(parents=True, exist_ok=True)
    for ruta, contenido in {**ev, **art}.items():
        _publicar(ruta, contenido)
    print(f"Evidencias: {args.salida}\nArtefactos (gitignored): {args.artefactos}")
    return 0


def _filas_top3(top3: dict[str, list[dict]]) -> list[dict]:
    return [{"context_id": ctx, "posicion": r["posicion"], "cited_id": r["cited_id"],
             "chunk_id": r["chunk_id"], "seccion": r.get("seccion") or SIN_SECCION,
             "perfil_seccion": perfil_seccion(r.get("seccion")),
             "paragraph_indices": "|".join(map(str, r.get("paragraph_indices") or [])),
             "puntaje": r["similitud_coseno"]}
            for ctx in sorted(top3) for r in top3[ctx]]


def _resumen_casos(casos: dict, excluidos: list[dict], conjuntos: dict) -> dict:
    por_conjunto = {}
    for n, original in conjuntos.items():
        motivos: dict[str, int] = {}
        for e in excluidos:
            if e["conjunto"] == n:
                motivos[e["motivo"]] = motivos.get(e["motivo"], 0) + 1
        total = len(original)
        por_conjunto[n] = {"contextos": total, "con_chunks": len(casos[n]),
                           "cobertura_pct": round(100 * len(casos[n]) / total, 2) if total else None,
                           "excluidos_por_motivo": dict(sorted(motivos.items()))}
    return por_conjunto


def recuperar(args, fabrica_codificador: Callable | None) -> int:
    """Top-3 con SciBERT base (revision de A1) para train/val/eval_2015/gold_v2."""
    fuentes = crear_fuentes()
    r = servicio.cargar_conjuntos(fuentes, args.fuente_etiquetas, args.limite)
    contextos = fuentes.indice()[1]
    casos, excluidos = servicio.construir_casos_split(
        r["conjuntos"], contextos, ad.cargar_papers(args.raw), args.cache_ocl, ad.integrar,
        ad.fragmentar)
    cobertura = _resumen_casos(casos, excluidos, r["conjuntos"])
    print(_json_texto({"cobertura": cobertura}), end="")
    if args.solo_validar:
        print("--solo-validar: no se cargo el modelo ni se escribio nada.")
        return 0
    if fabrica_codificador is None:
        raise ValueError("Falta un codificador; use `cli_modelo` o --solo-validar.")
    destinos = [args.salida / f"top3_{n}.csv" for n in casos] + [
        args.salida / "excluidos_recuperacion.csv", args.salida / "manifiesto_recuperacion.json"]
    existentes = [p for p in destinos if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    t0 = time.perf_counter()
    codificador = fabrica_codificador(args)
    cache = None if args.sin_cache else CacheDisco(args.cache)
    resultados = {n: servicio.recuperar_top3(c, codificador, cache, max_length=args.max_length,
                                             pooling=getattr(codificador, "pooling", "mean"))
                  for n, c in casos.items()}
    regresion = None
    if args.regresion_a1 and Path(args.regresion_a1).is_file():
        regresion = servicio.regresion_top3(
            resultados["train"]["top3"], leer_csv_top3(args.regresion_a1))
        if regresion["discrepancias"]:
            raise ValueError(f"Regresion contra A1 fallida: {regresion['discrepancias'][:5]}")
    contenido = {args.salida / f"top3_{n}.csv": _csv_texto(COL_TOP3, _filas_top3(res["top3"]))
                 for n, res in resultados.items()}
    contenido[args.salida / "excluidos_recuperacion.csv"] = _csv_texto(COL_MOTIVOS, excluidos)
    manifiesto = {
        "estado": r["estado"], "git": _git(), "limite": args.limite, "cobertura": cobertura,
        "encoder": codificador.info(),
        "sha256_manifiesto_modelo": _sha_manifiesto(args.manifiesto_modelo),
        "huellas": {n: res["huella"] for n, res in resultados.items()},
        "chunks_en_cache": {n: res["chunks_en_cache"] for n, res in resultados.items()},
        "regresion_a1": regresion,
        "segundos": round(time.perf_counter() - t0, 1),
        "entradas": {"manifiesto_ocl": _sha_archivo(args.manifiesto_ocl),
                     "manifiesto_preparacion": _sha_archivo(args.salida / "manifiesto_preparacion.json"),
                     "papers.json": _sha_archivo(args.raw / "papers.json"),
                     "contexts.json": _sha_archivo(args.raw / "contexts.json")},
        "salidas": {p.name: hashlib.sha256(t.encode("utf-8")).hexdigest()
                    for p, t in sorted(contenido.items())},
    }
    contenido[args.salida / "manifiesto_recuperacion.json"] = _json_texto(manifiesto)
    args.salida.mkdir(parents=True, exist_ok=True)
    for ruta, texto in contenido.items():
        _publicar(ruta, texto)
    print(f"Top-3 escrito en {args.salida} | regresion A1: {regresion}")
    return 0


def _sha_manifiesto(ruta: Path) -> str | None:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8")).get("sha256_manifiesto")
    except (OSError, ValueError):
        return None


def leer_csv_top3(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clasificacion_funcion.cli", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("preparar", help="construye train/val/eval y verifica fugas")
    s.add_argument("--solo-validar", action="store_true", help="valida y no escribe nada")
    s.add_argument("--limite", type=int, default=None, help="primeros N casos por conjunto")
    s.add_argument("--fuente-etiquetas", default="haiku", choices=servicio.FUENTES_ETIQUETAS)
    s.add_argument("--salida", type=Path, default=EVIDENCIAS)
    s.add_argument("--artefactos", type=Path, default=ARTEFACTOS)
    s.set_defaults(accion=preparar)
    t = sub.add_parser("recuperar", help="Top-3 denso (SciBERT base, regla de A1) para todos los conjuntos")
    t.add_argument("--solo-validar", action="store_true", help="solo cobertura de chunks; sin modelo")
    t.add_argument("--limite", type=int, default=None, help="primeros N casos por conjunto")
    t.add_argument("--fuente-etiquetas", default="haiku", choices=servicio.FUENTES_ETIQUETAS)
    t.add_argument("--raw", type=Path, default=ad.RAW)
    t.add_argument("--cache-ocl", type=Path, default=ad.CACHE_OCL)
    t.add_argument("--salida", type=Path, default=EVIDENCIAS)
    t.add_argument("--cache", type=Path, default=CACHE_EMBEDDINGS, help="cache de embeddings")
    t.add_argument("--sin-cache", action="store_true")
    t.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    t.add_argument("--batch-size", type=int, default=16)
    t.add_argument("--max-length", type=int, default=512)
    t.add_argument("--regresion-a1", type=Path, default=TOP3_A1,
                   help="top3.csv de A1: los chunk_id deben coincidir en los contextos compartidos")
    t.add_argument("--manifiesto-modelo", type=Path, default=EVIDENCIAS / "manifiesto_modelo_scibert.json")
    t.add_argument("--manifiesto-ocl", type=Path, default=EVIDENCIAS / "manifiesto_ocl.json")
    t.set_defaults(accion=recuperar)
    return p


def main(argv: list[str] | None = None, *, fabrica_codificador: Callable | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.accion is recuperar:
            return recuperar(args, fabrica_codificador)
        return args.accion(args)
    except (ValueError, OSError, RuntimeError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
