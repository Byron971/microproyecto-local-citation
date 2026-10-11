"""S2.5.b: perfilador exploratorio de MultiCite train, sin homologar etiquetas.

--execute es la ÚNICA opción que realiza una petición de red. El modo por
defecto presenta un plan y no toca ficheros. El muestreo de categorías no es
representativo de la población. No procesa dev/test ni modifica ACL-200.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_COMMIT = "120671924b5ab968b98c7f696c4b67b4f8118948"
SOURCE_PATH = "data/classification_1_context/train.json"
SOURCE_URL = f"https://raw.githubusercontent.com/allenai/multicite/{SOURCE_COMMIT}/{SOURCE_PATH}"
SOURCE_BLOB_SHA1 = "fdb9dfe5aa5de396e687924a4da1c5dbd62f6255"
SOURCE_SIZE = 1_667_641
MAX_BYTES = 2_000_000
LABELS = frozenset({
    "motivation", "background", "uses", "extends",
    "similarities", "differences", "future_work",
})
ACL_ID = re.compile(r"^[A-Z]\d{2}-\d{4}$")
DEFAULT_OUT = REPO_ROOT / "proyecto_de_grado/artifacts/multicite_s2_5"


def git_blob_sha1(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def descargar_train(*, abrir=urllib.request.urlopen) -> bytes:
    """Descarga única acotada del train de una oración, con hash Git fijado."""
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "proyecto-de-grado-educacion-s2-5/1.0"},
    )
    with abrir(req, timeout=30) as response:
        stated = response.headers.get("Content-Length")
        if stated is not None and int(stated) > MAX_BYTES:
            raise ValueError("Fuente excede el máximo permitido")
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Respuesta supera límite de bytes")
    if git_blob_sha1(content) != SOURCE_BLOB_SHA1:
        raise ValueError("La fuente cambió: SHA-1 Git no coincide con la versión auditada")
    return content


def cargar_y_validar(content: bytes) -> list[dict]:
    """Valida TODO train; marca x=[] explícitamente como registro no utilizable.

    MultiCite original contiene filas reales con contexto vacío. No se mezclan
    con casos anotables ni se silencian: el perfil reporta cada exclusión.
    Cualquier otra estructura desconocida sigue provocando un error.
    """
    try:
        rows = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("MultiCite train no es JSON UTF-8 válido") from exc
    if not isinstance(rows, list) or not rows:
        raise ValueError("MultiCite train debe ser una lista no vacía")
    ids = set()
    parsed = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict) or not all(k in row for k in ("id", "x", "y")):
            raise ValueError(f"Fila {idx}: esquema inesperado")
        rid = row["id"]
        x, y = row["x"], row["y"]
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError(f"Fila {idx}: ID ausente o repetido")
        ids.add(rid)
        if isinstance(x, str):
            texto = x
        elif isinstance(x, list) and all(isinstance(part, str) for part in x):
            texto = " ".join(x)
        else:
            raise ValueError(f"Fila {idx}: contexto tiene esquema desconocido")
        if not isinstance(y, str):
            raise ValueError(f"Fila {idx}: etiqueta no textual")
        etiquetas = y.split()
        if not etiquetas or len(etiquetas) != len(set(etiquetas)) or not set(etiquetas) <= LABELS:
            raise ValueError(f"Fila {idx}: etiquetas no válidas en clasificación MultiCite")
        estado = "utilizable" if texto.strip() else "excluido_contexto_vacio"
        parsed.append({
            "id": rid, "context": texto, "labels": etiquetas,
            "estado_contexto": estado, "fila_original": idx,
        })
    return parsed


def perfil_muestra(rows: list[dict], *, muestra: int = 30, semilla: int = 42) -> dict:
    """Cobertura 1/categoría primero; resto aleatorio. NO extrapolar frecuencias."""
    if not 1 <= muestra <= 30:
        raise ValueError("Muestra solicitada debe estar entre 1 y 30")
    if not rows:
        raise ValueError("No hay registros")
    label_counts = Counter(l for row in rows for l in row["labels"])
    excluidos = [r for r in rows if r["estado_contexto"] == "excluido_contexto_vacio"]
    utilizables = [r for r in rows if r["estado_contexto"] == "utilizable"]
    if not utilizables:
        raise ValueError("No existen contextos utilizables en train")
    # IDs y orden deterministas, no el orden del archivo original.
    ordered = sorted(utilizables, key=lambda x: x["id"])
    rng = random.Random(semilla)
    idxs = list(range(len(ordered)))
    rng.shuffle(idxs)
    selected = []
    selected_ids = set()
    for label in sorted(label_counts):
        if len(selected) >= muestra:
            break
        for i in idxs:
            row = ordered[i]
            if label in row["labels"] and row["id"] not in selected_ids:
                selected.append(row)
                selected_ids.add(row["id"])
                break
    for i in idxs:
        if len(selected) >= min(muestra, len(ordered)):
            break
        row = ordered[i]
        if row["id"] not in selected_ids:
            selected.append(row)
            selected_ids.add(row["id"])
    return {
        "tipo": "perfil_exploratorio_multicite_train_sin_homologacion",
        "fuente": SOURCE_URL,
        "fuente_blob_git_sha1": SOURCE_BLOB_SHA1,
        "particion_fuente": "train",
        "filas_train": len(rows),
        "filas_train_utilizables": len(utilizables),
        "filas_excluidas_contexto_vacio": len(excluidos),
        "exclusiones_contexto_vacio": [
            {"fila_original": r["fila_original"], "external_id": r["id"],
             "motivo": "x_vacio_o_solo_espacios"}
            for r in excluidos
        ],
        "codigos_externos_observados": dict(sorted(label_counts.items())),
        "codigos_externos_en_filas_utilizables": dict(sorted(
            Counter(l for r in utilizables for l in r["labels"]).items()
        )),
        "filas_con_multiples_etiquetas": sum(len(r["labels"]) > 1 for r in rows),
        "ids_que_parecen_acl_anthology": sum(bool(ACL_ID.fullmatch(r["id"])) for r in rows),
        "ids_comparados_por_igualdad_con_acl200": False,
        "muestra": len(selected),
        "semilla": semilla,
        "metodo_muestra": "cobertura_de_clases_primero_y_relleno_aleatorio_no_representativo",
        "muestra_local": [
            {"external_id": r["id"], "external_labels": r["labels"],
             "context_preview": r["context"][:250], "context_chars": len(r["context"])}
            for r in selected
        ],
        "clases_internas_validadas": 0,
        "equivalencias_externas_aprobadas": 0,
        "advertencia": (
            "Muestra local para inspección, no importación. MultiCite es "
            "multietiqueta, sin TARGETCIT ACL-200 verificado ni cotejo de citante/citado."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Autoriza una descarga de train ~1.67MB")
    parser.add_argument("--input", type=Path, help="Leer train.json ya descargado; sin usar red")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.execute and args.input:
        parser.error("Elegir --input (sin red) O --execute (con red), no ambos")
    if not 1 <= args.sample <= 30:
        parser.error("Solo se permiten muestras de 1 a 30 registros")
    if not args.execute and args.input is None:
        print("=== S2.5.b | PLAN SIN RED ===")
        print("Fuente:", SOURCE_URL)
        print("Archivo fuente bytes (Git):", SOURCE_SIZE)
        print("Split fuente: train, nunca dev/test")
        print("Licencia declarada: CC BY-NC 2.0 (uso académico no comercial; revisar condiciones)")
        print("Muestra máxima: 30, clase primero; NO representativa")
        print("Modo seguro: 0 descargas, 0 archivos escritos")
        print("Usa --execute para una única descarga controlada y revisión local")
        return 0
    try:
        contenido = (descargar_train() if args.execute else args.input.read_bytes())
        if len(contenido) > MAX_BYTES:
            raise ValueError("Archivo fuente demasiado grande")
        if git_blob_sha1(contenido) != SOURCE_BLOB_SHA1:
            raise ValueError("SHA Git diferente; comprobar versión de origen")
        rows = cargar_y_validar(contenido)
        resumen = perfil_muestra(rows, muestra=args.sample, semilla=args.seed)
        resumen["fuente_sha256"] = hashlib.sha256(contenido).hexdigest()
        args.out.mkdir(parents=True, exist_ok=True)
        ruta = args.out / "perfil_multicite_train.json"
        # Nunca se guarda texto externo como un archivo versionado en Git:
        # los ejemplos se almacenan en artifacts/ (ignorado por Git).
        ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("=== S2.5.b | PERFIL EXTERNO SIN FUSIÓN ===")
        print("Filas fuente:", resumen["filas_train"])
        print("Filas utilizables:", resumen["filas_train_utilizables"])
        print("Exclusiones por contexto vacío:", resumen["filas_excluidas_contexto_vacio"])
        print("Etiquetas observadas (todas las filas):", resumen["codigos_externos_observados"])
        print("Filas multilabel:", resumen["filas_con_multiples_etiquetas"])
        print("IDs con formato ACL Anthology:", resumen["ids_que_parecen_acl_anthology"])
        print("Muestra local:", resumen["muestra"])
        print("Reporte:", ruta)
        print("Homologaciones y etiquetas humanas validadas: 0")
    except (OSError, ValueError, urllib.error.URLError) as exc:
        parser.exit(2, f"S2.5.b falló sin fusionar registros: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
