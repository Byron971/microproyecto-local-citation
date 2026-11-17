"""Consolida la anotación a ciegas de Opus sobre las discrepancias del test gold v3.

Lee los output.json de cada lote (carpeta_lotes/pXX/output.json), valida que estén
completos y en el formato pedido, y los cruza con discrepancias.csv. La columna
«acuerdo_opus» dice con qué anotador humano coincide Opus, o «Ninguno».

    python scripts/consolidar_discrepancia_opus.py CARPETA_LOTES [--carpeta test_gold_final_anotar]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CARPETA = REPO / "test_gold_final_anotar"

EVALUABLE = {"Evaluable", "Ambiguo", "No evaluable"}
FUNCIONES = {"Background", "Gap", "Basis", "Comparison", "Application",
             "Improvement / Modification", "Evidence", "Identification of the Originator",
             "Further Reading"}
CONFIANZA = {"Alta", "Media", "Baja", ""}
NO_EVALUABLE = "No evaluable"
MAX_PALABRAS = 30

RENOMBRE = {"evaluable": "opus_evaluable", "funcion": "opus_funcion",
            "confianza": "opus_confianza", "justificacion": "opus_justificacion",
            "estado": "opus_estado"}


def validar(fila, lote):
    """Lista de problemas de formato de una anotación de Opus."""
    cid = fila.get("context_id")
    problemas = []
    if fila.get("evaluable") not in EVALUABLE:
        problemas.append(f"{lote} {cid}: evaluable={fila.get('evaluable')!r}")
    if fila.get("evaluable") != NO_EVALUABLE and fila.get("funcion") not in FUNCIONES:
        problemas.append(f"{lote} {cid}: funcion={fila.get('funcion')!r}")
    if fila.get("evaluable") == NO_EVALUABLE and fila.get("funcion"):
        problemas.append(f"{lote} {cid}: función no vacía en No evaluable")
    if (fila.get("confianza") or "") not in CONFIANZA:
        problemas.append(f"{lote} {cid}: confianza={fila.get('confianza')!r}")
    palabras = len((fila.get("justificacion") or "").split())
    if not palabras or palabras > MAX_PALABRAS:
        problemas.append(f"{lote} {cid}: justificación con {palabras} palabras")
    return problemas


def leer_lotes(carpeta_lotes):
    filas, problemas = [], []
    for lote in sorted(p for p in carpeta_lotes.iterdir() if p.is_dir()):
        salida = lote / "output.json"
        if not salida.exists():
            problemas.append(f"{lote.name}: sin output.json")
            continue
        esperados = [r["context_id"] for r in json.loads((lote / "input.json").read_text("utf-8"))]
        try:
            resultado = json.loads(salida.read_text("utf-8"))
        except json.JSONDecodeError as error:
            problemas.append(f"{lote.name}: JSON inválido ({error})")
            continue
        if [r.get("context_id") for r in resultado] != esperados:
            problemas.append(f"{lote.name}: los context_id no coinciden con input.json")
        for fila in resultado:
            problemas += validar(fila, lote.name)
            filas.append({**fila, "lote": lote.name})
    return pd.DataFrame(filas), problemas


def etiqueta_opus(fila):
    return NO_EVALUABLE if fila["opus_evaluable"] == NO_EVALUABLE else fila["opus_funcion"]


def acuerdo(fila):
    if fila["etiqueta_opus"] == fila["etiqueta_A"]:
        return fila["anotador_A"]
    if fila["etiqueta_opus"] == fila["etiqueta_B"]:
        return fila["anotador_B"]
    return "Ninguno"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("carpeta_lotes", type=Path, help="Carpeta con los lotes pXX/")
    parser.add_argument("--carpeta", type=Path, default=CARPETA,
                        help="Carpeta con discrepancias.csv y donde se escribe la salida")
    args = parser.parse_args()

    opus, problemas = leer_lotes(args.carpeta_lotes)
    print(f"Anotaciones de Opus: {len(opus)}  problemas de formato: {len(problemas)}")
    for problema in problemas:
        print("  -", problema)
    if problemas:
        raise SystemExit("Corrige los lotes antes de consolidar.")

    discrepancias = pd.read_csv(args.carpeta / "discrepancias.csv")
    opus = opus.rename(columns=RENOMBRE)
    opus["etiqueta_opus"] = opus.apply(etiqueta_opus, axis=1)
    final = discrepancias.merge(opus, on="context_id", how="left", validate="1:1")
    faltan = final["etiqueta_opus"].isna().sum()
    if faltan:
        raise SystemExit(f"{faltan} discrepancias sin anotación de Opus.")
    final.insert(1, "acuerdo_opus", final.apply(acuerdo, axis=1))

    columnas = ["context_id", "acuerdo_opus", "etiqueta_opus", "anotador_A", "etiqueta_A",
                "anotador_B", "etiqueta_B", "opus_evaluable", "opus_confianza",
                "opus_justificacion", "opus_estado", "discrepancia", "Tanda",
                "Contexto original (inglés)", "Título citado", "lote"]
    final = final[columnas + [c for c in final.columns if c not in columnas]]
    ruta = args.carpeta / "discrepancia_opus.csv"
    final.to_csv(ruta, index=False, encoding="utf-8-sig")

    total = len(final)
    ninguno = (final["acuerdo_opus"] == "Ninguno").sum()
    print("\nResumen")
    print(f"  Discrepancias anotadas por Opus: {total}")
    print(f"  Opus coincide con algún humano:  {total - ninguno} ({(total - ninguno) / total:.1%})")
    print(f"  Opus no coincide con ninguno:    {ninguno} ({ninguno / total:.1%})")
    print("\nCoincidencias por anotador (veces que Opus le da la razón / discrepancias en que participa):")
    participa = pd.concat([final["anotador_A"], final["anotador_B"]]).value_counts()
    gana = final["acuerdo_opus"].value_counts()
    tabla = pd.DataFrame({"participa": participa, "opus_coincide": gana}).fillna(0).astype(int)
    print(tabla.sort_values("participa", ascending=False).to_string())
    print("\nConfianza de Opus según acuerdo:")
    print(pd.crosstab(final["acuerdo_opus"] == "Ninguno", final["opus_confianza"])
          .rename(index={True: "Ninguno", False: "Coincide"}).to_string())
    print(f"\nEscrito: {ruta}")


if __name__ == "__main__":
    main()
