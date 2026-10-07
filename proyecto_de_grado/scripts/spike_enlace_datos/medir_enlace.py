"""Prueba de viabilidad (spike): ¿cuántos pares de ACL-200 se pueden resolver con texto completo?

La propuesta V3 dice que ACL-200 se enlazará con unarXive "por identificador de arXiv", pero
los IDs de ACL-200 son de ACL Anthology (P15-2138), no de arXiv. Este script mide, sobre una
muestra aleatoria de contextos, qué tan bien funciona cada una de las dos rutas posibles:

  Ruta A: texto completo desde ACL OCL (el corpus de ACL Anthology ya procesado con GROBID,
          que usa el MISMO identificador que ACL-200, así que el enlace es directo).
  Ruta B: texto completo desde unarXive, que exige que el artículo tenga ID de arXiv. Como
          unarXive son 105 GB en un solo tar, aquí se mide la condición NECESARIA (tener ID de
          arXiv según Semantic Scholar): es una cota superior de lo que unarXive podría cubrir.

Uso:
  python medir_enlace.py --acl200 <carpeta con contexts.json y papers.json> --cache <carpeta> --out <carpeta>
"""

# --- Librerías: solo estándar, para que corra en cualquier venv sin instalar nada ---
import argparse  # lee los argumentos de la línea de comandos
import json  # lee los JSON de ACL-200 y de ACL OCL
import random  # toma la muestra aleatoria reproducible
import re  # expresiones regulares para normalizar texto y leer el año del ID
import time  # pausas entre reintentos cuando una API responde 429
import unicodedata  # convierte ligaduras de PDF ("ﬁ") a letras normales ("fi")
import urllib.error  # captura los errores HTTP (404 = no existe, 429 = límite de peticiones)
import urllib.request  # hace las peticiones HTTP sin depender de requests
from collections import Counter  # cuenta frecuencias para los resúmenes
from concurrent.futures import ThreadPoolExecutor  # descarga varios JSON en paralelo
from pathlib import Path  # manejo de rutas que funciona igual en Windows y Linux
from statistics import median  # mediana de palabras y de chunks por artículo

# URL de cada artículo en ACL OCL; el patrón sale del árbol del repo en HuggingFace:
# Base_JSON/prefixP/json/P15/P15-2138.json  (letra del volumen, luego letra+año, luego el ID)
OCL_URL = "https://huggingface.co/datasets/WINGNUS/ACL-OCL/resolve/main/Base_JSON/prefix{L}/json/{L}{YY}/{ID}.json"
# Endpoint por lote de Semantic Scholar: acepta hasta 500 IDs por petición con el prefijo "ACL:"
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=externalIds,year"


def anio_desde_id(acl_id):
    """Deduce el año del ID antiguo de ACL Anthology: P15-2138 -> 2015, W95-0110 -> 1995."""
    m = re.match(r"^[A-Z](\d{2})-\d{4}$", acl_id)  # letra + 2 dígitos de año + guion + 4 dígitos
    if not m:
        return None  # formato distinto (no debería pasar en ACL-200, pero no se asume)
    yy = int(m.group(1))
    return 1900 + yy if yy > 50 else 2000 + yy  # ACL empieza en los 60s, así que >50 es siglo XX


def normalizar(texto):
    """Minúsculas, sin ligaduras, solo letras y números: así el texto de dos extracciones de PDF
    distintas (la de ACL-200 y la de GROBID) se puede comparar aunque difieran en puntuación."""
    texto = unicodedata.normalize("NFKC", texto).lower()  # "ﬁ" -> "fi", y todo a minúsculas
    texto = re.sub(r"-\s+", "", texto)  # une palabras cortadas por guion al final de línea
    texto = re.sub(r"[^a-z0-9]+", " ", texto)  # todo lo que no sea letra o número pasa a espacio
    return texto.strip()


def descargar_ocl(acl_id, cache_dir):
    """Devuelve el JSON de ACL OCL de un artículo, o None si no existe. Guarda en caché en disco
    para que volver a correr el script no repita las descargas."""
    destino = cache_dir / f"{acl_id}.json"
    ausente = cache_dir / f"{acl_id}.404"  # marca de "ya se buscó y no existe"
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    if ausente.exists():
        return None
    url = OCL_URL.format(L=acl_id[0], YY=acl_id[1:3], ID=acl_id)
    for intento in range(5):  # reintenta ante límites de peticiones o fallos de red transitorios
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                datos = r.read().decode("utf-8")
            destino.write_text(datos, encoding="utf-8")
            return json.loads(datos)
        except urllib.error.HTTPError as e:
            if e.code == 404:  # el artículo no está en ACL OCL: es un resultado, no un error
                ausente.write_text("", encoding="utf-8")
                return None
            time.sleep(5 * (intento + 1))  # 429 o 5xx: espera cada vez más y vuelve a intentar
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {acl_id} tras 5 intentos")  # fallo real: se reporta


def contar_chunks(parrafos):
    """Aplica la regla de la propuesta: chunks de máximo 2 párrafos o 300 palabras, sin cruzar
    un cambio de sección. Devuelve cuántos chunks salen y cuántos párrafos exceden 300 palabras
    por sí solos (esos habría que partirlos por oración)."""
    chunks, gigantes = 0, 0
    actual_parrafos, actual_palabras, seccion_actual = 0, 0, None
    for p in parrafos:
        n = len(p["text"].split())
        if n > 300:
            gigantes += 1
        # se cierra el chunk en curso si cambia la sección, ya tiene 2 párrafos o se pasaría de 300
        if actual_parrafos and (p["section"] != seccion_actual or actual_parrafos == 2 or actual_palabras + n > 300):
            chunks += 1
            actual_parrafos, actual_palabras = 0, 0
        actual_parrafos += 1
        actual_palabras += n
        seccion_actual = p["section"]
    if actual_parrafos:
        chunks += 1  # el último chunk abierto también cuenta
    return chunks, gigantes


def perfil_texto_completo(doc):
    """Resume si el texto completo de un artículo sirve para la Fase 2 (recuperación de chunks)."""
    parrafos = doc["pdf_parse"]["body_text"]
    palabras = sum(len(p["text"].split()) for p in parrafos)
    secciones = {p["section"].strip().lower() for p in parrafos if p["section"].strip()}
    con_seccion = sum(1 for p in parrafos if p["section"].strip())
    chunks, gigantes = contar_chunks(parrafos)
    return {
        "parrafos": len(parrafos),
        "palabras": palabras,
        "secciones_distintas": len(secciones),
        "pct_parrafos_con_seccion": con_seccion / len(parrafos) if parrafos else 0.0,
        "chunks": chunks,
        "parrafos_gigantes": gigantes,
        # "usable": hay cuerpo real (no solo abstract) y al menos 3 secciones para registrar la sección del chunk
        "usable": palabras >= 500 and len(secciones) >= 3,
    }


def ubicar_contexto(masked_text, citante):
    """Busca el contexto truncado de ACL-200 dentro del texto completo del artículo citante.
    Si se encuentra, se puede reconstruir hasta el límite de oración (lo que pide la propuesta)."""
    # se parte por los marcadores para no crear frases que crucen una cita enmascarada
    segmentos = re.split(r"TARGETCIT|OTHERCIT", masked_text)
    palabras_ctx = []
    for i, seg in enumerate(segmentos):
        ws = normalizar(seg).split()
        if i == 0:
            ws = ws[1:]  # la primera palabra suele venir cortada por la ventana fija de ACL-200
        if i == len(segmentos) - 1:
            ws = ws[:-1]  # la última también
        palabras_ctx.append(ws)
    # "shingles": secuencias de 6 palabras seguidas; se busca cuántas aparecen tal cual en el citante
    shingles = [" ".join(ws[j:j + 6]) for ws in palabras_ctx for j in range(0, max(len(ws) - 5, 0), 3)]
    if not shingles:
        return None  # contexto demasiado fragmentado para buscarlo
    mejor = (0.0, None)
    for idx, p in enumerate(citante["pdf_parse"]["body_text"]):
        cuerpo = " " + normalizar(p["text"]) + " "
        tasa = sum(1 for s in shingles if f" {s} " in cuerpo) / len(shingles)
        if tasa > mejor[0]:
            mejor = (tasa, idx)
    # umbral: al menos la mitad de los shingles en un mismo párrafo = el contexto está ahí
    return mejor if mejor[0] >= 0.5 else None


def titulo_en_bibliografia(titulo_citado, citante):
    """¿El título del artículo citado aparece en la bibliografía que GROBID extrajo del citante?
    Si sí, el par citante–citado se puede reconstruir desde ACL OCL sin depender de ACL-200."""
    objetivo = set(normalizar(titulo_citado).split())
    if not objetivo:
        return False
    for bib in citante["pdf_parse"]["bib_entries"].values():
        candidato = set(normalizar(bib.get("title") or "").split())
        if candidato and len(objetivo & candidato) / len(objetivo | candidato) >= 0.8:  # similitud de Jaccard
            return True
    return False


def consultar_s2(ids, cache_file):
    """Traduce IDs de ACL a IDs de arXiv con la API por lote de Semantic Scholar.
    Sin llave de API el límite es compartido y responde 429 a menudo, así que reintenta con espera."""
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    pendientes = [i for i in ids if i not in cache]
    for k in range(0, len(pendientes), 500):  # la API acepta hasta 500 IDs por petición
        lote = pendientes[k:k + 500]
        cuerpo = json.dumps({"ids": [f"ACL:{i}" for i in lote]}).encode("utf-8")
        for intento in range(8):
            try:
                req = urllib.request.Request(S2_BATCH_URL, data=cuerpo, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    respuesta = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 and e.code < 500:
                    raise  # un error que no es de límite ni de servidor no se arregla esperando
                time.sleep(10 * (intento + 1))  # 10 s, 20 s, 30 s... hasta que haya cupo
        else:
            raise RuntimeError("Semantic Scholar siguió respondiendo 429 tras 8 intentos")
        # la respuesta viene alineada con la lista enviada; None = el artículo no está en S2
        for acl_id, item in zip(lote, respuesta):
            ext = (item or {}).get("externalIds") or {}
            cache[acl_id] = {"en_s2": item is not None, "arxiv": ext.get("ArXiv")}
        cache_file.write_text(json.dumps(cache, indent=1), encoding="utf-8")  # guarda avance
    return cache


def pct(n, d):
    """Porcentaje con un decimal, protegido contra división por cero."""
    return f"{100 * n / d:.1f} %" if d else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acl200", required=True, type=Path)
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n", type=int, default=500)  # 500 contextos: margen de error de ±4,4 pp al 95 %
    ap.add_argument("--seed", type=int, default=42)  # semilla fija: la misma muestra en cada corrida
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)

    # --- 1. Muestra aleatoria reproducible de contextos de ACL-200 ---
    contextos = json.loads((args.acl200 / "contexts.json").read_text(encoding="utf-8"))
    papers = json.loads((args.acl200 / "papers.json").read_text(encoding="utf-8"))
    claves = sorted(contextos)  # se ordena antes de muestrear para que el resultado no dependa del orden del JSON
    muestra = [contextos[k] for k in random.Random(args.seed).sample(claves, args.n)]
    ids = sorted({c["citing_id"] for c in muestra} | {c["refid"] for c in muestra})
    print(f"Muestra: {len(muestra)} contextos, {len(ids)} artículos únicos (citantes + citados)")

    # --- 2. Ruta A: descargar el texto completo de ACL OCL para cada artículo de la muestra ---
    with ThreadPoolExecutor(max_workers=6) as ex:  # 6 en paralelo: rápido sin saturar HuggingFace
        docs = dict(zip(ids, ex.map(lambda i: descargar_ocl(i, args.cache), ids)))
    perfiles = {i: perfil_texto_completo(d) for i, d in docs.items() if d is not None}

    # --- 3. Ruta B: ¿cuáles tienen ID de arXiv? (condición necesaria para estar en unarXive) ---
    s2 = consultar_s2(ids, args.out / "s2_arxiv_ids.json")

    # --- 4. Evaluar cada contexto de la muestra por ambas rutas ---
    filas = []
    for c in muestra:
        cit, ref = c["citing_id"], c["refid"]
        doc_cit = docs.get(cit)
        fila = {
            "context_id": c["context_id"],
            "anio_citado": anio_desde_id(ref),
            # Ruta A
            "A_citado_en_ocl": ref in perfiles,
            "A_citado_usable": perfiles.get(ref, {}).get("usable", False),
            "A_citante_en_ocl": cit in perfiles,
            "A_contexto_ubicado": bool(doc_cit and ubicar_contexto(c["masked_text"], doc_cit)),
            "A_titulo_en_bib": bool(doc_cit and titulo_en_bibliografia(papers.get(ref, {}).get("title", ""), doc_cit)),
            # Ruta B
            "B_citado_arxiv": bool(s2.get(ref, {}).get("arxiv")),
            "B_citante_arxiv": bool(s2.get(cit, {}).get("arxiv")),
        }
        # par resuelto de punta a punta: el citado tiene texto útil para chunks Y el contexto se
        # puede reconstruir desde el citante (las dos cosas que la propuesta necesita del texto completo)
        fila["A_par_completo"] = fila["A_citado_usable"] and fila["A_contexto_ubicado"]
        fila["B_par_completo_cota"] = fila["B_citado_arxiv"] and fila["B_citante_arxiv"]
        filas.append(fila)
    (args.out / "resultados_por_contexto.jsonl").write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in filas), encoding="utf-8")

    # --- 5. Resumen legible ---
    n = len(filas)
    tot = lambda k: sum(1 for f in filas if f[k])  # cuántas filas cumplen la condición k
    citados_unicos = sorted({c["refid"] for c in muestra})
    perf_citados = [perfiles[i] for i in citados_unicos if i in perfiles]
    lineas = [
        f"# Resultados del spike de enlace de datos (n = {n} contextos, semilla {args.seed})",
        "",
        "## Ruta A: ACL OCL (mismo ID que ACL-200)",
        f"- Citado presente en ACL OCL: {tot('A_citado_en_ocl')} ({pct(tot('A_citado_en_ocl'), n)})",
        f"- Citado con texto usable para chunks (>= 500 palabras y >= 3 secciones): {tot('A_citado_usable')} ({pct(tot('A_citado_usable'), n)})",
        f"- Citante presente en ACL OCL: {tot('A_citante_en_ocl')} ({pct(tot('A_citante_en_ocl'), n)})",
        f"- Contexto truncado ubicado en el texto del citante (reconstruible a oración completa): {tot('A_contexto_ubicado')} ({pct(tot('A_contexto_ubicado'), n)})",
        f"- Título del citado encontrado en la bibliografía del citante: {tot('A_titulo_en_bib')} ({pct(tot('A_titulo_en_bib'), n)})",
        f"- **Par completo (citado usable + contexto reconstruible): {tot('A_par_completo')} ({pct(tot('A_par_completo'), n)})**",
        "",
        "## Ruta B: unarXive vía ID de arXiv (cota superior)",
        f"- Citado con ID de arXiv: {tot('B_citado_arxiv')} ({pct(tot('B_citado_arxiv'), n)})",
        f"- Citante con ID de arXiv: {tot('B_citante_arxiv')} ({pct(tot('B_citante_arxiv'), n)})",
        f"- **Par con ambos en arXiv (máximo que unarXive podría cubrir): {tot('B_par_completo_cota')} ({pct(tot('B_par_completo_cota'), n)})**",
        f"- Artículos de la muestra que Semantic Scholar sí reconoce: {sum(1 for i in ids if s2.get(i, {}).get('en_s2'))} de {len(ids)}",
        "",
        "## Calidad del texto completo de los citados en ACL OCL",
        f"- Citados únicos con texto: {len(perf_citados)} de {len(citados_unicos)}",
    ]
    if perf_citados:
        lineas += [
            f"- Mediana de palabras del cuerpo: {median(p['palabras'] for p in perf_citados):.0f}",
            f"- Mediana de secciones distintas: {median(p['secciones_distintas'] for p in perf_citados):.0f}",
            f"- Mediana de chunks por artículo (regla 2 párrafos / 300 palabras): {median(p['chunks'] for p in perf_citados):.0f}",
            f"- Mediana del % de párrafos con sección asignada: {100 * median(p['pct_parrafos_con_seccion'] for p in perf_citados):.0f} %",
            f"- Artículos con al menos un párrafo de más de 300 palabras: {sum(1 for p in perf_citados if p['parrafos_gigantes'])}",
        ]
    # desglose por año del citado: muestra si la cobertura cae en los artículos más antiguos
    lineas += ["", "## Desglose por año del artículo citado", "",
               "| Año del citado | Contextos | A: par completo | B: par en arXiv |", "|---|---:|---:|---:|"]
    for etiqueta, cond in [("< 2000", lambda y: y < 2000), ("2000-2009", lambda y: 2000 <= y < 2010),
                           ("2010-2014", lambda y: 2010 <= y < 2015), (">= 2015", lambda y: y >= 2015)]:
        grupo = [f for f in filas if f["anio_citado"] and cond(f["anio_citado"])]
        a = sum(1 for f in grupo if f["A_par_completo"])
        b = sum(1 for f in grupo if f["B_par_completo_cota"])
        lineas.append(f"| {etiqueta} | {len(grupo)} | {pct(a, len(grupo))} | {pct(b, len(grupo))} |")
    resumen = "\n".join(lineas) + "\n"
    (args.out / "resumen.md").write_text(resumen, encoding="utf-8")
    print(resumen)


if __name__ == "__main__":
    main()
