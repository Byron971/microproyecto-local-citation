# Recalcula desde ACL-200 todas las cifras que se citan en el informe de avance.
import json, re, sys, statistics
raw = sys.argv[1]
ctx = json.load(open(raw + "/contexts.json", encoding="utf-8"))
papers = json.load(open(raw + "/papers.json", encoding="utf-8"))
def year(pid):
    m = re.match(r"^[A-Z](\d{2})-", pid)
    if not m: return None
    yy = int(m.group(1)); return 1900 + yy if yy >= 79 else 2000 + yy
print("contextos:", len(ctx), "| artículos:", len(papers))
print("con TARGETCIT:", sum("TARGETCIT" in c["masked_text"] for c in ctx.values()))
sup = 0
for n in ("train", "val", "test"):
    d = json.load(open(f"{raw}/{n}.json", encoding="utf-8")); sup += len(d)
    ys = [year(ctx[r["context_id"]]["citing_id"]) for r in d]
    print(f"{n}: {len(d)} años citante {min(ys)}-{max(ys)}")
print("supervisados:", sup)
# artículos con cuerpo de texto en ACL-200 (solo título y resumen)
print("campos de papers:", sorted({k for p in papers.values() for k in p}))
# truncamiento de los contextos
t = [c["masked_text"].strip() for c in ctx.values()]
minus = sum(1 for x in t if x[:1].islower()) / len(t)
sinpunto = sum(1 for x in t if not x.endswith(".")) / len(t)
pal = [len(x.split()) for x in t]
q = statistics.quantiles(pal, n=10)
print(f"empiezan en minúscula: {minus:.1%} | no terminan en punto: {sinpunto:.1%} | palabras mediana {statistics.median(pal)} p10 {q[0]} p90 {q[-1]}")
# año de los citados
cy = [year(c["refid"]) for c in ctx.values()]; cy = [y for y in cy if y]
print(f"citados anteriores a 2015: {sum(y < 2015 for y in cy)/len(cy):.1%} | mediana año citado {statistics.median(cy)}")
print("extrapolación 82,2 %:", round(len(ctx) * 0.822))
# citados compartidos entre particiones
sets = {}
for n in ("train", "val", "test"):
    d = json.load(open(f"{raw}/{n}.json", encoding="utf-8"))
    sets[n] = ({ctx[r["context_id"]]["citing_id"] for r in d}, {ctx[r["context_id"]]["refid"] for r in d})
print("citantes compartidos train-test:", len(sets["train"][0] & sets["test"][0]), "| citados compartidos train-test:", len(sets["train"][1] & sets["test"][1]))
