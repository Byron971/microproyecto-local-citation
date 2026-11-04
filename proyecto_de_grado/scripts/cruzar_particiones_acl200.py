# Cruza el jurado de 18.000 citas y las hojas del Test Gold con las particiones oficiales de ACL-200.
# Uso: python proyecto_de_grado/scripts/cruzar_particiones_acl200.py data/raw jurado_18000_v3.csv [clave_coordinador_v2.csv] [entrenamiento_2700.csv]
# Solo imprime conteos; no muestra etiquetas, así que no rompe la anotación a ciegas.
import csv, json, sys
from collections import Counter
raw = sys.argv[1]
split = {}                                                     # context_id -> partición oficial
for n in ("train", "val", "test"):
    for r in json.load(open(f"{raw}/{n}.json", encoding="utf-8")):
        split[r["context_id"]] = n
ctx = json.load(open(f"{raw}/contexts.json", encoding="utf-8"))
def oficial(cid):
    return split.get(cid, "sin_particion" if cid in ctx else "no_esta_en_ACL200")
def leer(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))
citante = lambda cid: cid.rsplit("_", 2)[0]                    # el context_id es citante_citado_n
# 1. el jurado: partición por año del citante (columna particion) frente a la oficial
jurado = leer(sys.argv[2])
print("jurado:", len(jurado), "citas")
for (anio, ofi), k in sorted(Counter((r["particion"], oficial(r["context_id"])) for r in jurado).items()):
    print(f"  por año {anio:14s} oficial {ofi:18s} {k:6d}")
# 2. las hojas repartidas: cada grupo debe estar completo en su partición y sin repetidos
if len(sys.argv) > 3:
    clave = leer(sys.argv[3])
    for g, t in sorted({(r["grupo"], r["tanda"]) for r in clave}):
        ids = [r["context_id"] for r in clave if r["grupo"] == g and r["tanda"] == t]
        print(f"{g} {t}: {len(ids)} citas, {len(set(ids))} únicas,", dict(Counter(oficial(c) for c in ids)))
# 3. fuga: artículos citantes del Test Gold que también están en el entrenamiento del QLoRA
if len(sys.argv) > 4:
    ent = {r["context_id"] for r in leer(sys.argv[4])}
    gold = {r["context_id"] for r in clave if r["grupo"] == "testgold"}
    print("entrenamiento QLoRA:", len(ent), "citas,", dict(Counter(oficial(c) for c in ent)))
    print("citantes compartidos Test Gold / entrenamiento:", len({citante(c) for c in gold} & {citante(c) for c in ent}))
