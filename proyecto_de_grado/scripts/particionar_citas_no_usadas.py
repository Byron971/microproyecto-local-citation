"""Particiona las citas no utilizadas en subconjuntos disjuntos para clasificarlas con el QLoRA.

Universo: data/raw/contexts.json (+ títulos/resúmenes de data/raw/papers.json).
Se excluyen (por context_id):
  - las 18.000 ya clasificadas (incluyen el test gold de 2.700),
  - las 2.700 de entrenamiento,
  - los casos del taller.
El resto se baraja con semilla fija y se reparte en K = ceil(N / MAX_POR_SUBCONJUNTO) subconjuntos
de tamaño casi igual (todos <= MAX_POR_SUBCONJUNTO).

Cada subconjunto se escribe con las mismas columnas que ANOTACION_18000_CITAS_REALES.csv, de modo que
en finetune_qlora_citas.ipynb basta con apuntar TARGET_CSV (y OUT_CSV / RUN_JSONL) al subconjunto.

Uso (requiere data/raw/ descargado con DVC):
    python proyecto_de_grado/scripts/particionar_citas_no_usadas.py [--max 10000] [--seed 42]
"""
import argparse
import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # raíz del repositorio

QLORA = ROOT / "notebooks" / "qlora-training"
RAW = ROOT / "data" / "raw"      # se obtiene con DVC
OUT = QLORA / "subconjuntos_qlora"
YA_CLASIFICADAS = QLORA / "ANOTACION_18000_CITAS_REALES.csv"
ENTRENAMIENTO = QLORA / "ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv"
TALLER = ROOT / "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt"
COLS = ["N°", "context_id", "Contexto TARGETCIT", "Título citado", "Resumen citado",
        "¿Evaluable?", "Función principal", "Confianza", "Justificación / duda", "Estado"]


def ids_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return {r["context_id"] for r in csv.DictReader(f)}


def ids_txt(p):
    return {l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=10000, help="máximo de citas por subconjunto")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    contexts = json.load(open(RAW / "contexts.json", encoding="utf-8"))
    papers = json.load(open(RAW / "papers.json", encoding="utf-8"))

    excluidas = {
        "ya clasificadas (18.000)": ids_csv(YA_CLASIFICADAS),
        "entrenamiento (2.700)": ids_csv(ENTRENAMIENTO),
        "taller": ids_txt(TALLER),
    }
    usadas = set().union(*excluidas.values())
    for k, v in excluidas.items():
        print(f"{k}: {len(v)} (presentes en el universo: {len(v & contexts.keys())})")

    pool = sorted(set(contexts) - usadas)  # sorted -> reproducible
    print(f"universo: {len(contexts)} | usadas (unión): {len(usadas & contexts.keys())} | sin usar: {len(pool)}")
    random.Random(a.seed).shuffle(pool)

    k = math.ceil(len(pool) / a.max)
    base, extra = divmod(len(pool), k)
    OUT.mkdir(parents=True, exist_ok=True)
    manifiesto, ini = [], 0
    for i in range(1, k + 1):
        n = base + (1 if i <= extra else 0)
        ids = pool[ini:ini + n]
        ini += n
        nombre = f"CITAS_NO_USADAS_{i:02d}.csv"
        with open(OUT / nombre, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            for j, cid in enumerate(ids, 1):
                cited = cid.rsplit("_", 2)[1]
                p = papers.get(cited, {})
                w.writerow([j, cid, contexts[cid]["masked_text"], (p.get("title") or "").strip(),
                            (p.get("abstract") or "").strip(), "", "", "", "", ""])
        manifiesto.append((nombre, len(ids)))
        print(f"{nombre}: {len(ids)} citas")

    assert ini == len(pool) and sum(n for _, n in manifiesto) == len(pool)
    with open(OUT / "MANIFIESTO_SUBCONJUNTOS.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "n_citas"])
        w.writerows(manifiesto)


if __name__ == "__main__":
    main()
