# Arma la página de práctica: toma la metadata de cada caso (etiqueta, explicación),
# le agrega el texto real del contexto y el título del artículo citado desde ACL-200,
# y lo inyecta en la plantilla HTML.
import json, re, sys, html as H

raw, base = sys.argv[1], sys.argv[2]           # carpeta de ACL-200 y carpeta de trabajo
ctx = json.load(open(raw + "/contexts.json", encoding="utf-8"))
papers = json.load(open(raw + "/papers.json", encoding="utf-8"))
meta = json.load(open(base + "/items_meta.json", encoding="utf-8"))

def limpiar(t):
    t = t.replace("�", "").replace("&quot;", '"').replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()     # colapsa espacios y saltos de línea

tr = json.load(open(base + "/traducciones.json", encoding="utf-8"))   # traducción al español por caso

items, problemas = [], []
for m in meta:
    c = ctx[m["id"]]                            # contexto original con TARGETCIT / OTHERCIT
    p = papers.get(c["refid"], {})
    texto = limpiar(c["masked_text"])
    t = tr.get(m["id"])
    if not t:
        problemas.append((m["id"], "sin traducción")); continue
    # la señal debe existir literalmente en el texto para poder resaltarla (en inglés y en español)
    if m.get("sig") and m["sig"].lower() not in texto.lower():
        problemas.append((m["id"], m["sig"]))
    if t["sig"] and t["sig"].lower() not in t["es"].lower():
        problemas.append((m["id"], "es: " + t["sig"]))
    # la traducción debe conservar exactamente una cita objetivo
    if t["es"].count("TARGETCIT") != 1:
        problemas.append((m["id"], "TARGETCIT en es: %d" % t["es"].count("TARGETCIT")))
    items.append({**m, "text": texto, "title": limpiar(p.get("title", "")),
                  "es": t["es"], "sig_es": t["sig"], "title_es": t["t"]})

# --- ronda de calibración: casos nuevos, sin etiqueta de referencia ---
import random
cids = json.load(open(base + "/calib_ids.json", encoding="utf-8"))
ctr = json.load(open(base + "/calib_traducciones.json", encoding="utf-8"))
orden = cids["fijos"] + cids["azar"]
random.Random(19).shuffle(orden)               # mezcla fija: los casos con señal no quedan al principio
practica = {i["id"] for i in items}
calib = []
for cid in orden:
    if cid in practica:
        problemas.append((cid, "repetido con la práctica"))
    c = ctx[cid]; p = papers.get(c["refid"], {}); t = ctr.get(cid)
    if not t:
        problemas.append((cid, "calibración sin traducción")); continue
    texto = limpiar(c["masked_text"])
    if texto.count("TARGETCIT") != 1 or t["es"].count("TARGETCIT") != 1:
        problemas.append((cid, "TARGETCIT en calibración"))
    calib.append({"id": cid, "text": texto, "title": limpiar(p.get("title", "")), "es": t["es"], "title_es": t["t"]})

if problemas:
    print("PROBLEMAS:", problemas); sys.exit(1)

tpl = open(base + "/plantilla.html", encoding="utf-8").read()
js = lambda x: json.dumps(x, ensure_ascii=False).replace("</", "<\\/")   # evita cerrar el <script>
html = tpl.replace("/*__ITEMS__*/[]", js(items)).replace("/*__CALIB__*/[]", js(calib))
html = html.replace("/*__ACUERDO__*/", open(base + "/acuerdo.js", encoding="utf-8").read().split("if (typeof module")[0])
open(base + "/taller_anotacion.html", "w", encoding="utf-8").write(html)
print("práctica:", len(items), {n: sum(i["n"] == n for i in items) for n in (1, 2, 3)}, "| calibración:", len(calib))
