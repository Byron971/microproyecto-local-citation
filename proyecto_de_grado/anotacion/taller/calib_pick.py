# Elige los casos de calibración: 18 fijados a mano (con palabras señal) + 18 aleatorios de ACL-200,
# excluyendo los 41 de práctica y los 20 del piloto.
import json, sys, random, re
raw, base = sys.argv[1], sys.argv[2]
ctx = json.load(open(raw + "/contexts.json", encoding="utf-8"))
papers = json.load(open(raw + "/papers.json", encoding="utf-8"))
practica = {m["id"] for m in json.load(open(base + "/items_meta.json", encoding="utf-8"))}
piloto = {l.split(",")[0] for l in open(sys.argv[3], encoding="utf-8").read().splitlines()[1:] if l}
fijos = ["K15-1029_P96-1025_0","W05-0638_W04-3212_0","P13-1137_W12-1642_0","P14-1066_D13-1176_0",
 "J13-3003_W09-2413_0","W15-2212_S14-2082_2","E06-1040_E06-1045_0","N01-1003_W98-1415_1",
 "D14-1101_E14-4030_0","D13-1129_P08-1068_1","D15-1104_N03-1028_0","P13-1009_N12-1049_5",
 "S07-1072_P97-1023_0","W14-1005_W11-2126_1","E14-1037_D11-1140_1","E12-1050_P07-1096_1",
 "W11-0507_N09-1041_0","Q15-1006_N07-1055_0"]
excl = practica | piloto | set(fijos)
def limpio(t):
    t = t.replace("�", "")
    # descarta fragmentos con mucho ruido: pocas letras, muchos números (tablas) o varias TARGETCIT
    letras = sum(ch.isalpha() for ch in t) / max(len(t), 1)
    nums = len(re.findall(r"\d", t)) / max(len(t), 1)
    return t.count("TARGETCIT") == 1 and letras > 0.72 and nums < 0.04
random.seed(2026)
ids = [i for i in ctx if i not in excl and limpio(ctx[i]["masked_text"])]
aleat = random.sample(ids, 18)
out = open(base + "/calib_textos.txt", "w", encoding="utf-8")
for tipo, lista in (("fijo", fijos), ("azar", aleat)):
    for i in lista:
        c = ctx[i]; p = papers.get(c["refid"], {})
        out.write(f"== {i} | {tipo}\n{re.sub(r'\s+',' ',c['masked_text'].replace(chr(0xfffd),'')).strip()}\nTITLE: {p.get('title','').replace(chr(10),' ')}\n\n")
json.dump({"fijos": fijos, "azar": aleat}, open(base + "/calib_ids.json", "w"), indent=1)
print(len(fijos), len(aleat), "excluidos:", len(excl))
