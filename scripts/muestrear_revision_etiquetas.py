"""Muestra aleatoria de 20 etiquetas de Haiku y 20 de Sonnet para revisión humana.

Cada muestra cubre las 9 funciones (2 por clase) y completa las 20 con citas al azar.
Solo toma citas marcadas como Evaluable. Agrega la columna vacía «comentarios humanos».

    python scripts/muestrear_revision_etiquetas.py [--semilla 42]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
HAIKU_CSV = REPO / "notebooks/qlora-training/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv"
SONNET_CSV = REPO / "proyecto_de_grado/anotacion/sonnet/etiquetas_sonnet.csv"
CONTEXTS = REPO / "data/raw/contexts.json"
PAPERS = REPO / "data/raw/papers.json"
SALIDA = REPO / "proyecto_de_grado/anotacion/revision_etiquetas_llm"

TOTAL = 20
POR_CLASE = 2
COLUMNAS = ["context_id", "Contexto TARGETCIT", "Título citado", "Resumen citado",
            "Función principal", "Confianza", "Justificación / duda", "comentarios humanos"]


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    haiku = pd.read_csv(HAIKU_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    sonnet = pd.read_csv(SONNET_CSV, dtype=str, keep_default_na=False)

    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, df in [("haiku", haiku), ("sonnet", agregar_textos(sonnet))]:
        muestra = muestrear(df, args.semilla)
        ruta = SALIDA / f"revision_{nombre}_20.csv"
        muestra.to_csv(ruta, index=False, encoding="utf-8-sig")
        print(f"{ruta.relative_to(REPO)}: {len(muestra)} citas, "
              f"{muestra['Función principal'].nunique()} clases")


if __name__ == "__main__":
    main()
