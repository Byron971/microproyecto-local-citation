"""Construye el Test Gold (2.700 casos) para anotación humana.

Reglas (ver propuesta, sección 4, y decisiones del proyecto de grado):
- Solo artículos citantes de 2014 y 2015 (los de 2009-2013 se usaron para entrenar el QLoRA).
- Se excluyen los casos del taller de práctica (ids_excluir_test_gold.txt).
- Aislamiento por documento: ningún par citante-citado ni citante de las 2.700 anotaciones de
  entrenamiento. Además se prefieren artículos citados que no aparecen en entrenamiento.
- Muestreo estratificado por la pre-etiqueta del QLoRA solo para asegurar casos de las clases raras.
  La pre-etiqueta NO se entrega a los anotadores (va en el manifiesto).

Uso (la ejecución desde cualquier directorio es válida):
    python proyecto_de_grado/scripts/construir_test_gold.py
"""
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # raíz del repositorio

SEED = 42
N_TOTAL = 2700
QLORA = ROOT / "notebooks" / "qlora-training"
OUT = ROOT / "proyecto_de_grado/anotacion/test_gold"
PRE = QLORA / "ANOTACION_18000_CITAS_REALES_QLORA.csv"
TRAIN = QLORA / "ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv"
EXCL = ROOT / "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt"
RARE = ["Further Reading", "Identification of the Originator", "Improvement / Modification", "Basis", "Gap"]
CLUSTERS = ["Evidence", "Comparison", "Application", "Background"]


def read(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))


def parts(cid):
    citing, cited, _ = cid.rsplit("_", 2)
    return citing, cited


rows = read(PRE)
train_ids = {r["context_id"] for r in read(TRAIN)}
train_citing = {parts(c)[0] for c in train_ids}
train_cited = {parts(c)[1] for c in train_ids}
train_pairs = {parts(c) for c in train_ids}
excl = {l.strip() for l in open(EXCL, encoding="utf-8") if l.strip() and not l.startswith("#")}

pool = []
for r in rows:
    cid = r["context_id"]
    citing, cited = parts(cid)
    if cid[1:3] not in ("14", "15") or cid in excl:
        continue
    if citing in train_citing or (citing, cited) in train_pairs:
        continue
    r["_label"] = r["Función principal"] or "Sin clasificar"
    r["_cited_overlap"] = cited in train_cited
    pool.append(r)

by = defaultdict(list)
for r in pool:
    by[r["_label"]].append(r)
rng = random.Random(SEED)
for v in by.values():
    rng.shuffle(v)
    v.sort(key=lambda r: r["_cited_overlap"])  # primero los citados disjuntos (orden estable)

quota = {k: len(by[k]) for k in RARE + ["Sin clasificar", "Evidence"]}
rest = N_TOTAL - sum(quota.values())
tot = sum(len(by[k]) for k in CLUSTERS if k != "Evidence")
for k in ("Comparison", "Application", "Background"):
    quota[k] = round(rest * len(by[k]) / tot)
quota["Background"] += N_TOTAL - sum(quota.values())

chosen = [r for k, q in quota.items() for r in by[k][:q]]
assert len(chosen) == N_TOTAL and len({r["context_id"] for r in chosen}) == N_TOTAL
rng.shuffle(chosen)

OUT.mkdir(parents=True, exist_ok=True)
cols = ["N°", "context_id", "Contexto TARGETCIT", "Título citado", "Resumen citado",
        "¿Evaluable?", "Función principal", "Confianza", "Justificación / duda", "Estado"]
with open(OUT / "TEST_GOLD_2700_PARA_ANOTAR.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for i, r in enumerate(chosen, 1):
        w.writerow([i, r["context_id"], r["Contexto TARGETCIT"], r["Título citado"], r["Resumen citado"],
                    "", "", "", "", ""])
with open(OUT / "TEST_GOLD_2700_MANIFIESTO.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["N°", "context_id", "anio_citante", "prelabel_qlora", "citado_en_entrenamiento"])
    for i, r in enumerate(chosen, 1):
        w.writerow([i, r["context_id"], "20" + r["context_id"][1:3], r["_label"], int(r["_cited_overlap"])])

print("pool elegible:", len(pool))
print("por año:", Counter(r["context_id"][1:3] for r in chosen))
print("por pre-etiqueta:", Counter(r["_label"] for r in chosen).most_common())
print("citados que también están en entrenamiento:", sum(r["_cited_overlap"] for r in chosen))
