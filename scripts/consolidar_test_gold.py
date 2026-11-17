"""Unifica las anotaciones definitivas del test gold v2 en un solo CSV de etiquetas.

Lee concordancias, una_anotacion, discrepancia_opus y anotado_opus (disjuntos), valida que
cubran exactamente `ids_gold_v2()` y escribe test_gold_final.csv.

    python scripts/consolidar_test_gold.py [--carpeta test_gold_final_anotar]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages/clasificacion-funcion/src"))
sys.path.insert(0, str(REPO / "packages/auditoria-corpus/src"))
sys.path.insert(0, str(REPO / "packages/recuperacion-densa/src"))

from clasificacion_funcion import adaptador_proyecto_grado as ad  # noqa: E402
from clasificacion_funcion import dominio  # noqa: E402
from clasificacion_funcion import seleccion_datos as sd  # noqa: E402

CARPETA = REPO / "test_gold_final_anotar"
TOTAL_ESPERADO = 1533
NO_EVALUABLE = "No evaluable"
COLUMNAS = ["context_id", "etiqueta", "indice", "evaluable", "fuente", "opus_sin_acuerdo", "anotador",
            "confianza", "Tanda", "Contexto original (inglés)", "Título citado"]


def leer(carpeta, nombre):
    return pd.read_csv(carpeta / nombre, encoding="utf-8-sig")


def cargar_fuentes(carpeta):
    concordancias = leer(carpeta, "concordancias.csv")
    concordancias["etiqueta"] = concordancias["etiqueta_final"]
    concordancias["fuente"] = "concordancia"

    una = leer(carpeta, "una_anotacion.csv")
    una["etiqueta"] = una["etiqueta_unica"]
    una["anotador"] = una["anotador_con_etiqueta"]
    una["fuente"] = "una_anotacion"

    discrepancia = leer(carpeta, "discrepancia_opus.csv")
    discrepancia["etiqueta"] = discrepancia["etiqueta_opus"]
    discrepancia["opus_sin_acuerdo"] = discrepancia["acuerdo_opus"] == "Ninguno"
    discrepancia["confianza"] = discrepancia["opus_confianza"]
    discrepancia["fuente"] = "discrepancia_opus"

    opus = leer(carpeta, "anotado_opus.csv")
    opus["etiqueta"] = opus["¿Evaluable?"].where(opus["¿Evaluable?"] == NO_EVALUABLE,
                                                  opus["Función principal (una)"])
    opus["confianza"] = opus["Confianza"]
    opus["fuente"] = "solo_opus"
    return [concordancias, una, discrepancia, opus]


def consolidar(carpeta):
    partes = cargar_fuentes(carpeta)
    gold = pd.concat(partes, ignore_index=True)
    for columna in ("opus_sin_acuerdo", "anotador", "confianza"):
        if columna not in gold:
            gold[columna] = None
    gold["opus_sin_acuerdo"] = gold["opus_sin_acuerdo"].astype("boolean").fillna(False).astype(bool)
    gold["indice"] = [dominio.normalizar_etiqueta(e) for e in gold["etiqueta"]]
    gold["evaluable"] = gold["indice"].notna()
    gold["indice"] = gold["indice"].astype("Int64")
    return gold[COLUMNAS]


def validar(gold, partes_ids):
    ids = gold["context_id"]
    if not ids.is_unique:
        raise SystemExit(f"context_id repetidos: {ids[ids.duplicated()].tolist()[:5]}")
    acumulado = set()
    for nombre, conjunto in partes_ids.items():
        solapa = acumulado & conjunto
        if solapa:
            raise SystemExit(f"{nombre} solapa con otra fuente: {sorted(solapa)[:5]}")
        acumulado |= conjunto
    if len(gold) != TOTAL_ESPERADO:
        raise SystemExit(f"Se esperaban {TOTAL_ESPERADO} filas y hay {len(gold)}")
    esperados = set(ad.FuentesProyectoGrado().ids_gold_v2())
    if set(ids) != esperados:
        raise SystemExit(f"Distinto de ids_gold_v2(): faltan {len(esperados - set(ids))}, sobran {len(set(ids) - esperados)}")
    mal = gold[gold["evaluable"] & ~gold["indice"].between(0, dominio.N_CLASES - 1)]
    if len(mal):
        raise SystemExit(f"Etiquetas sin índice 0..8: {mal['etiqueta'].unique().tolist()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--carpeta", type=Path, default=CARPETA)
    args = parser.parse_args()

    partes = cargar_fuentes(args.carpeta)
    gold = consolidar(args.carpeta)
    validar(gold, {p["fuente"].iloc[0]: set(p["context_id"]) for p in partes})

    ruta = args.carpeta / "test_gold_final.csv"
    gold.to_csv(ruta, index=False, encoding="utf-8-sig")

    print(f"Filas: {len(gold)}  (validaciones OK)")
    print("\nPor fuente:")
    print(gold["fuente"].value_counts().to_string())
    print("\nDistribución de clases:")
    print(gold["etiqueta"].value_counts().to_string())
    print(f"\nAbstenciones: {int((~gold['evaluable']).sum())}")
    print(f"Opus sin acuerdo con ningún humano: {int(gold['opus_sin_acuerdo'].sum())}")
    print(f"\nEscrito: {ruta}\nsha256: {sd.sha_archivo(ruta)}")


if __name__ == "__main__":
    main()
