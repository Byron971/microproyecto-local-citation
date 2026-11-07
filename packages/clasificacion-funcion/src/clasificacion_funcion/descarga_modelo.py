"""PASO CON RED (junto a `descarga_ocl`): resuelve el SHA de la revision y descarga el
encoder con manifiesto. Requiere el grupo `modelo` (huggingface-hub).

  python -m clasificacion_funcion.descarga_modelo --encoder specter --resolver
  python -m clasificacion_funcion.descarga_modelo --encoder scibert
"""
import argparse
import json
import sys
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download
from recuperacion_densa.descarga_modelo import hash_manifiesto, manifiesto_de

from . import revision

REPO = Path(__file__).resolve().parents[4]
EVIDENCIAS = REPO / "proyecto_de_grado/docs/evidencias_clasificacion_a4"
MANIFIESTO_A1 = REPO / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json"


def ruta_manifiesto(encoder: str, carpeta: Path = EVIDENCIAS) -> Path:
    return carpeta / f"manifiesto_modelo_{encoder}.json"


def verificar_o_escribir(ruta: Path, manifiesto: dict, esperado: str | None = None) -> str:
    """Verifica el manifiesto existente o lo crea (sin sobrescribir). Devuelve 'verificado'
    o 'creado'. `esperado`: SHA que el manifiesto nuevo debe tener (p. ej. el de A1)."""
    huella = hash_manifiesto(manifiesto)
    if ruta.exists():
        previo = json.loads(ruta.read_text(encoding="utf-8")).get("sha256_manifiesto")
        if huella != previo:
            raise ValueError(f"el snapshot no coincide con {ruta}")
        return "verificado"
    if esperado is not None and huella != esperado:
        raise ValueError("el manifiesto de SciBERT difiere del de A1: no se escribe nada.")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("x", encoding="utf-8") as fh:
        json.dump({**manifiesto, "sha256_manifiesto": huella}, fh, ensure_ascii=False,
                  indent=2, sort_keys=True)
        fh.write("\n")
    return "creado"


def sha_a1(ruta: Path = MANIFIESTO_A1) -> str | None:
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8")).get("sha256_manifiesto")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--encoder", required=True, choices=revision.ENCODERS)
    ap.add_argument("--resolver", action="store_true", help="imprime el SHA actual de `main` y sale")
    ap.add_argument("--manifiesto", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.resolver:
        print(HfApi().model_info(revision.MODELOS[a.encoder]["model_id"], revision="main").sha)
        return 0
    try:
        model_id, rev = revision.modelo(a.encoder)
        carpeta = Path(snapshot_download(model_id, revision=rev))
        m = manifiesto_de(carpeta, model_id, rev)
        ruta = a.manifiesto or ruta_manifiesto(a.encoder)
        esperado = sha_a1() if a.encoder == "scibert" else None
        estado = verificar_o_escribir(ruta, m, esperado)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"{estado.capitalize()} {model_id}@{rev} | {len(m['archivos'])} archivos | {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
