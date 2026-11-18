"""Muestras aleatorias de etiquetas de Haiku, Sonnet y Opus para revisión humana.

Haiku y Sonnet: 20 citas cada uno, cubriendo las 9 funciones (2 por clase) y completando
al azar. Solo toma citas marcadas como Evaluable.

Opus: 100 citas. Incluye siempre las 11 discrepancias del test gold en que Opus no coincidió
con ninguno de los dos anotadores humanos (origen «desacuerdo humano») y completa con citas
al azar de anotado_opus.csv (origen «aleatoria»).

Nunca sobrescribe un CSV existente (puede tener revisiones hechas) salvo con --sobrescribir.

    python scripts/muestrear_revision_etiquetas.py [--semilla 42] [--sobrescribir]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
HAIKU_CSV = REPO / "notebooks/qlora-training/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv"
SONNET_CSV = REPO / "proyecto_de_grado/anotacion/sonnet/etiquetas_sonnet.csv"
OPUS_CSV = REPO / "proyecto_de_grado/anotacion/test_gold_final/anotado_opus.csv"
OPUS_DISCREPANCIA_CSV = REPO / "proyecto_de_grado/anotacion/test_gold_final/discrepancia_opus.csv"
CONTEXTS = REPO / "data/raw/contexts.json"
PAPERS = REPO / "data/raw/papers.json"
SALIDA = REPO / "proyecto_de_grado/anotacion/revision_etiquetas_llm"

TOTAL = 20
POR_CLASE = 2
TOTAL_OPUS = 100
DESACUERDO = "desacuerdo humano"
ALEATORIA = "aleatoria"
COLUMNAS = ["context_id", "Contexto TARGETCIT", "Título citado", "Resumen citado",
            "Función principal", "Confianza", "Justificación / duda", "comentarios humanos"]
COLUMNAS_OPUS = COLUMNAS + ["origen", "¿Evaluable?", "anotador_A", "etiqueta_A",
                            "anotador_B", "etiqueta_B"]


def agregar_textos(df):
    """La salida de Sonnet no trae el texto: se toma de ACL-200 (contexts.json y papers.json)."""
    contextos = json.loads(CONTEXTS.read_text(encoding="utf-8"))
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))
    citado = df["context_id"].map(lambda c: papers.get(contextos[c]["refid"], {}))
    df["Contexto TARGETCIT"] = df["context_id"].map(lambda c: contextos[c]["masked_text"].strip())
    df["Título citado"] = citado.map(lambda p: p.get("title", ""))
    df["Resumen citado"] = citado.map(lambda p: p.get("abstract", ""))
    return df


def muestrear(df, semilla):
    df = df[df["¿Evaluable?"] == "Evaluable"]
    por_clase = pd.concat([g.sample(min(POR_CLASE, len(g)), random_state=semilla)
                           for _, g in df.groupby("Función principal")])
    resto = df.drop(por_clase.index).sample(TOTAL - len(por_clase), random_state=semilla)
    muestra = pd.concat([por_clase, resto]).sample(frac=1, random_state=semilla)
    muestra["comentarios humanos"] = ""
    return muestra[COLUMNAS]


def muestrear_opus(semilla):
    """Las discrepancias sin acuerdo de Opus más citas al azar hasta completar TOTAL_OPUS."""
    discrepancias = pd.read_csv(OPUS_DISCREPANCIA_CSV, dtype=str, keep_default_na=False,
                                encoding="utf-8-sig")
    sin_acuerdo = discrepancias[discrepancias["acuerdo_opus"] == "Ninguno"].rename(columns={
        "etiqueta_opus": "Función principal", "opus_confianza": "Confianza",
        "opus_justificacion": "Justificación / duda", "opus_evaluable": "¿Evaluable?"})
    sin_acuerdo["origen"] = DESACUERDO

    anotado = pd.read_csv(OPUS_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    anotado = anotado[~anotado["context_id"].isin(sin_acuerdo["context_id"])]
    aleatorias = anotado.sample(TOTAL_OPUS - len(sin_acuerdo), random_state=semilla).rename(
        columns={"Función principal (una)": "Función principal"})
    aleatorias["origen"] = ALEATORIA

    muestra = pd.concat([sin_acuerdo, aleatorias], ignore_index=True).fillna("")
    muestra = agregar_textos(muestra).sample(frac=1, random_state=semilla)
    muestra["comentarios humanos"] = ""
    return muestra[COLUMNAS_OPUS]


def guardar(muestra, ruta, sobrescribir):
    if ruta.exists() and not sobrescribir:
        print(f"{ruta.relative_to(REPO)}: ya existe, se omite (usa --sobrescribir)")
        return
    muestra.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"{ruta.relative_to(REPO)}: {len(muestra)} citas, "
          f"{muestra['Función principal'].nunique()} clases")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--sobrescribir", action="store_true",
                        help="Reemplaza los CSV existentes (borra sus revisiones)")
    args = parser.parse_args()

    haiku = pd.read_csv(HAIKU_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    sonnet = pd.read_csv(SONNET_CSV, dtype=str, keep_default_na=False)

    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, df in [("haiku", haiku), ("sonnet", agregar_textos(sonnet))]:
        guardar(muestrear(df, args.semilla), SALIDA / f"revision_{nombre}_{TOTAL}.csv",
                args.sobrescribir)
    guardar(muestrear_opus(args.semilla), SALIDA / f"revision_opus_{TOTAL_OPUS}.csv",
            args.sobrescribir)


if __name__ == "__main__":
    main()
