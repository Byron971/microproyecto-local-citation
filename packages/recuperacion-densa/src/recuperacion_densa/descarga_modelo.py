"""UNICO paso con red: resuelve el SHA de la revision y descarga el modelo con manifiesto."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from .revision import MODEL_ID, REVISION_SCIBERT, validar_revision

MANIFIESTO = (Path(__file__).resolve().parents[4]
              / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json")


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def manifiesto_de(carpeta: Path, model_id: str, revision: str) -> dict:
    # los symlinks del snapshot apuntan a blobs; se hashea el contenido
    archivos = {str(p.relative_to(carpeta)): sha256_archivo(p)
                for p in sorted(carpeta.rglob("*")) if p.is_file()}
    return {"model_id": model_id, "revision": revision, "archivos": archivos}


def hash_manifiesto(m: dict) -> str:
    return hashlib.sha256(json.dumps(m, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resolver", action="store_true", help="imprime el SHA actual y sale")
    ap.add_argument("--model", default=MODEL_ID)
    ap.add_argument("--revision", default=REVISION_SCIBERT)
    ap.add_argument("--manifiesto", type=Path, default=MANIFIESTO)
    a = ap.parse_args(argv)
    if a.resolver:
        print(HfApi().model_info(a.model, revision="main").sha)
        return 0
    revision = validar_revision(a.revision)
    carpeta = Path(snapshot_download(a.model, revision=revision))
    m = manifiesto_de(carpeta, a.model, revision)
    if a.manifiesto.exists():
        previo = json.loads(a.manifiesto.read_text(encoding="utf-8"))
        esperado = previo.get("sha256_manifiesto")
        if hash_manifiesto(m) != esperado:
            print(f"Error: el snapshot no coincide con {a.manifiesto}", file=sys.stderr)
            return 1
        print(f"Verificado {a.model}@{revision} | {len(m['archivos'])} archivos")
        return 0
    m["sha256_manifiesto"] = hash_manifiesto({k: v for k, v in m.items()})
    a.manifiesto.parent.mkdir(parents=True, exist_ok=True)
    with a.manifiesto.open("x", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"Modelo {a.model}@{revision} | {len(m['archivos'])} archivos | {a.manifiesto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
