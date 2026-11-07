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
from pathlib import Path

from . import adaptador_proyecto_grado as ad
from . import dominio, servicio

EVIDENCIAS = ad.REPO / "proyecto_de_grado/docs/evidencias_clasificacion_a4"
ARTEFACTOS = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/preparacion"
COL_MOTIVOS = ["conjunto", "context_id", "motivo"]
COL_ETIQUETAS = ["context_id", "indice", "etiqueta"]


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
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.accion(args)
    except (ValueError, FileExistsError, FileNotFoundError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
