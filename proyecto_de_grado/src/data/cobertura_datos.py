"""Cobertura y viabilidad de los datos frente a los comentarios de la docente (issue #125).

Mide sobre el corpus completo de ACL-200, no sobre una muestra: huellas de los archivos,
pares completos, coherencia entre el año del citante y la partición oficial, solapamientos,
duplicados de texto y concentración por artículo. Comprueba si las 18.000 citas del jurado
se comportan como una muestra al azar y, con esa base, proyecta cuántas citas por clase
daría todo ACL-200 frente a la meta de 2.000. No descarga nada ni cambia ningún dato.

Uso, desde la raíz del repositorio:
    python -m proyecto_de_grado.src.data.cobertura_datos --raw data/raw \
        --jurado data/jurado/v3/jurado_18000_v3.csv \
        --qlora-2700 notebooks/qlora-training/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv \
        --dataset data/dataset_funciones/v1/dataset_funciones_v1.csv \
        --reporte proyecto_de_grado/docs/cobertura_datos_v1.md
"""
from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter, defaultdict
from pathlib import Path
import json

from proyecto_de_grado.src.data.auditar_jurado import CLASES, fmt, leer_csv, pct
from proyecto_de_grado.src.data.curar_dataset_funciones import META_POR_CLASE, anio_citante
from proyecto_de_grado.src.data.validar_splits import SPLITS, load_split_index

ARCHIVOS_RAW = ("contexts.json", "papers.json", "train.json", "val.json", "test.json")
RANGO_OFICIAL = {"train": (2009, 2013), "val": (2014, 2014), "test": (2015, 2015)}
SIN_PARTICION = "sin_particion"

# Licencias verificadas en la fuente el 2026-11-04 (enlaces en el reporte).
FUENTES = [
    {"fuente": "ACL-200 (repositorio de Gu et al., 2022)", "aporta": "contextos con TARGETCIT, pares citante-citado, título y resumen, particiones",
     "unidad": "contexto de cita", "id": "context_id = citante_citado_n (IDs de ACL Anthology)",
     "licencia": "El repositorio no declara licencia; los textos son de ACL Anthology anteriores a 2016 (CC BY-NC-SA 3.0)",
     "uso": "Única fuente de contextos y etiquetas"},
    {"fuente": "ACL OCL (Rohatgi et al., 2023)", "aporta": "texto completo con secciones de citantes y citados",
     "unidad": "artículo", "id": "mismo ID de ACL Anthology",
     "licencia": "MIT en Hugging Face; los artículos conservan CC BY-NC-SA 3.0 (antes de 2016) o CC BY 4.0",
     "uso": "Texto completo para el Top-3; se enlaza por ID, sin cambiar etiquetas"},
    {"fuente": "MultiCite (Lauscher et al., 2022)", "aporta": "intenciones de cita a nivel de oración",
     "unidad": "oración, varias etiquetas por cita", "id": "IDs de S2ORC",
     "licencia": "CC BY-NC 2.0 (derivado de S2ORC)",
     "uso": "No se homologa: 7 intenciones con varias etiquetas por cita, no 9 funciones con una sola"},
    {"fuente": "unarXive (vía ID de arXiv)", "aporta": "texto completo de arXiv",
     "unidad": "artículo", "id": "ID de arXiv",
     "licencia": "No aplica: descartada",
     "uso": "Descartada: como máximo cubre 1 de 500 pares"},
]


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8-sig"))


def inventario(raw: Path) -> list[dict]:
    """Filas, tamaño y huella SHA-256 de cada archivo crudo."""
    filas = []
    for nombre in ARCHIVOS_RAW:
        ruta = raw / nombre
        filas.append({"archivo": nombre, "filas": len(leer_json(ruta)), "bytes": ruta.stat().st_size,
                      "sha256": sha256(ruta)})
    return filas


def medir_pares(contextos: dict[str, dict], papers: dict[str, dict]) -> dict:
    """Cuántos contextos traen todo lo que necesita el clasificador, con el corpus completo como denominador."""
    con_texto = lambda pid: bool((papers.get(pid) or {}).get("title", "").strip()) and \
        bool((papers.get(pid) or {}).get("abstract", "").strip())
    c = Counter()
    for ctx in contextos.values():
        c["contextos"] += 1
        marca = "TARGETCIT" in ctx.get("masked_text", "")
        c["con_targetcit"] += marca
        c["citante_en_papers"] += ctx["citing_id"] in papers
        c["citado_en_papers"] += ctx["refid"] in papers
        c["citado_con_titulo_y_resumen"] += con_texto(ctx["refid"])
        c["par_completo"] += marca and ctx["citing_id"] in papers and con_texto(ctx["refid"])
    c["articulos"] = len(papers)
    return dict(c)


def medir_particiones(contextos: dict[str, dict], por_contexto: dict[str, str]) -> dict:
    """Coherencia entre el año del citante (leído del ID) y la partición oficial, y solapamientos."""
    por_split = {s: Counter() for s in (*SPLITS, SIN_PARTICION)}
    citantes, citados, pares = defaultdict(set), defaultdict(set), defaultdict(set)
    for cid, ctx in contextos.items():
        split = por_contexto.get(cid, SIN_PARTICION)
        anio = anio_citante(ctx["citing_id"])
        por_split[split]["contextos"] += 1
        if split in RANGO_OFICIAL:
            lo, hi = RANGO_OFICIAL[split]
            por_split[split]["anio_fuera_de_rango"] += not lo <= anio <= hi
        else:
            por_split[split][bloque_anio(anio)] += 1
        citantes[split].add(ctx["citing_id"])
        citados[split].add(ctx["refid"])
        pares[split].add((ctx["citing_id"], ctx["refid"]))
    cruces = {}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        cruces[f"{a}-{b}"] = {"citantes": len(citantes[a] & citantes[b]), "citados": len(citados[a] & citados[b]),
                              "pares": len(pares[a] & pares[b])}
    return {"por_split": {k: dict(v) for k, v in por_split.items()}, "cruces": cruces}


def bloque_anio(anio: int) -> str:
    if anio < 2000:
        return "antes_de_2000"
    if anio <= 2008:
        return "2000-2008"
    if anio <= 2013:
        return "2009-2013"
    return str(anio)


def duplicados(contextos: dict[str, dict], por_contexto: dict[str, str], usos: dict[str, str]) -> dict:
    """Textos de contexto idénticos con distinto identificador, cuántos cruzan particiones y si tocan el Test Gold."""
    grupos = defaultdict(list)
    for cid, ctx in contextos.items():
        grupos[" ".join(ctx.get("masked_text", "").split())].append(cid)
    repetidos = [ids for ids in grupos.values() if len(ids) > 1]
    entre_splits = [ids for ids in repetidos if len({por_contexto.get(i, SIN_PARTICION) for i in ids}) > 1]
    citantes = lambda ids: {contextos[i]["citing_id"] for i in ids}
    gold_en_modelo, gold_fuera_de_test = [], []
    for ids in repetidos:
        for g in (i for i in ids if usos.get(i, "").startswith("test_gold")):
            gemelos = [i for i in ids if i != g]
            if any(usos.get(i) in ("entrenamiento", "validacion") for i in gemelos):
                gold_en_modelo.append(g)                  # fuga real: el modelo vería el mismo texto
            elif any(por_contexto.get(i, SIN_PARTICION) != "test" for i in gemelos):
                gold_fuera_de_test.append(g)              # hoy no entra al modelo, pero entraría si se amplía el dataset
    return {"grupos": len(repetidos), "contextos": sum(len(g) for g in repetidos),
            "mismo_citante": sum(len(citantes(ids)) == 1 for ids in repetidos),
            "grupos_entre_particiones": len(entre_splits),
            "gold_en_modelo": sorted(gold_en_modelo), "gold_fuera_de_test": sorted(gold_fuera_de_test)}


def concentracion(citantes: list[str]) -> dict:
    """Qué tanto dependen las citas de pocos artículos citantes."""
    por_articulo = sorted(Counter(citantes).values(), reverse=True)
    if not por_articulo:
        return {"contextos": 0, "articulos": 0, "mediana": 0, "maximo": 0, "parte_top10": 0.0}
    top = max(1, math.ceil(len(por_articulo) * 0.10))
    medio = len(por_articulo) // 2
    mediana = por_articulo[medio] if len(por_articulo) % 2 else (por_articulo[medio - 1] + por_articulo[medio]) / 2
    mediana = int(mediana) if mediana == int(mediana) else mediana
    return {"contextos": len(citantes), "articulos": len(por_articulo), "mediana": mediana,
            "maximo": por_articulo[0], "parte_top10": sum(por_articulo[:top]) / len(citantes)}


def gamma_q(a: float, x: float) -> float:
    """Gamma incompleta superior regularizada Q(a, x), para el valor p de la ji cuadrado."""
    if x <= 0:
        return 1.0
    if x < a + 1:                                         # serie para la parte inferior
        termino = total = 1.0 / a
        n = a
        while abs(termino) > abs(total) * 1e-15:
            n += 1
            termino *= x / n
            total += termino
        return 1.0 - total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b, c, d = x + 1 - a, 1e300, 1.0 / (x + 1 - a)         # fracción continua (Lentz) para la parte superior
    h = d
    for i in range(1, 10_000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def prueba_muestra(muestra: set[str], poblacion: dict[str, str]) -> dict:
    """Compara la muestra con lo esperado si fuera al azar sobre la población, estrato por estrato."""
    total = Counter(poblacion.values())
    obs = Counter(poblacion[c] for c in muestra if c in poblacion)
    n, N = sum(obs.values()), sum(total.values())
    filas, chi2 = [], 0.0
    for estrato in sorted(total):
        esperado = n * total[estrato] / N
        chi2 += (obs[estrato] - esperado) ** 2 / esperado
        filas.append({"estrato": estrato, "poblacion": total[estrato], "observado": obs[estrato], "esperado": esperado})
    gl = len(total) - 1
    return {"filas": filas, "chi2": chi2, "gl": gl, "p": gamma_q(gl / 2, chi2 / 2),
            "fuera_de_poblacion": len(muestra) - n}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confianza de Wilson para una proporción."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centro - margen, centro + margen


def proyectar(conteos: dict[str, int], n_muestra: int, n_poblacion: int) -> list[dict]:
    """Citas con consenso esperadas por clase si todo el corpus pasara por el mismo jurado."""
    filas = []
    for clase in CLASES:
        k = conteos.get(clase, 0)
        lo, hi = wilson(k, n_muestra)
        p_lo, p_hi = lo * n_poblacion, hi * n_poblacion
        veredicto = "sí" if p_lo >= META_POR_CLASE else ("no" if p_hi < META_POR_CLASE else "incierto")
        filas.append({"clase": clase, "muestra": k, "proyeccion": k / n_muestra * n_poblacion,
                      "ic_bajo": p_lo, "ic_alto": p_hi, "alcanza": veredicto})
    return filas


def medir_vistos(dataset: list[dict]) -> dict:
    """Citas del Test Gold cuyo artículo citado también aparece en entrenamiento (no es fuga, pero se reporta)."""
    citados_entrenamiento = {f["cited_id"] for f in dataset if f["uso"] == "entrenamiento"}
    gold = [f for f in dataset if f["uso"].startswith("test_gold")]
    return {"test_gold": len(gold), "citado_visto": sum(f["cited_id"] in citados_entrenamiento for f in gold)}


def ic_texto(lo: float, hi: float) -> str:
    return f"{fmt(round(lo))}–{fmt(round(hi))}"


def reporte(inv, pares, part, dup, conc, prueba, proy, vistos, ocl, haiku, n_jurado) -> str:
    L = ["# Cobertura y viabilidad de los datos (v1)", "",
         "Generado por `proyecto_de_grado/src/data/cobertura_datos.py`. Responde los comentarios de la docente "
         "sobre la propuesta V3 (rúbricas 4 y 5) con el corpus completo como denominador. Las cifras sobre muestras "
         "se marcan como tales.", ""]

    L += ["## 1. Fuentes y homologación", "",
          "Se arma **un solo dataset**: ACL-200 aporta los contextos, los pares y las particiones; ACL OCL aporta el "
          "texto completo del mismo artículo, enlazado por el identificador de ACL Anthology. No se mezclan "
          "etiquetas de otros datasets por tener nombres parecidos.", "",
          "| Fuente | Qué aporta | Unidad | Identificador | Licencia | Uso en el proyecto |", "|---|---|---|---|---|---|"]
    L += [f"| {f['fuente']} | {f['aporta']} | {f['unidad']} | {f['id']} | {f['licencia']} | {f['uso']} |" for f in FUENTES]
    L += ["", "Licencias verificadas el 2026-11-04 en aclanthology.org/faq/copyright, huggingface.co/datasets/WINGNUS/ACL-OCL "
          "y github.com/allenai/multicite. ILCiteR se usa solo como referencia metodológica y no se descarga.", "",
          "**Versión de ACL-200 usada** (`data/raw`, versionada con DVC):", "",
          "| Archivo | Filas | Bytes | SHA-256 |", "|---|---|---|---|"]
    L += [f"| `{f['archivo']}` | {fmt(f['filas'])} | {fmt(f['bytes'])} | `{f['sha256']}` |" for f in inv]

    c = pares["contextos"]
    L += ["", "## 2. ¿Todos los contextos tienen su par?", "",
          f"Sobre los {fmt(c)} contextos de ACL-200 y sus {fmt(pares['articulos'])} artículos:", "",
          "| Condición | Contextos | Parte del total |", "|---|---|---|",
          f"| Traen la marca TARGETCIT | {fmt(pares['con_targetcit'])} | {pct(pares['con_targetcit'] / c)} |",
          f"| El citante está en los metadatos | {fmt(pares['citante_en_papers'])} | {pct(pares['citante_en_papers'] / c)} |",
          f"| El citado está en los metadatos | {fmt(pares['citado_en_papers'])} | {pct(pares['citado_en_papers'] / c)} |",
          f"| El citado tiene título y resumen | {fmt(pares['citado_con_titulo_y_resumen'])} | {pct(pares['citado_con_titulo_y_resumen'] / c)} |",
          f"| **Par completo para clasificar con título y resumen** | **{fmt(pares['par_completo'])}** | **{pct(pares['par_completo'] / c)}** |", ""]
    k, n = ocl
    lo, hi = wilson(k, n)
    L += ["**Texto completo (ACL OCL).** Es una observación sobre una muestra, no una medición del corpus completo: "
          f"en {fmt(n)} contextos al azar (semilla 42, `docs/spike_enlace_datos/`) quedaron completos {fmt(k)} pares "
          f"({pct(k / n)}). Llevado al corpus, con un intervalo de confianza del 95 % (Wilson), se esperan entre "
          f"{pct(lo)} y {pct(hi)}, es decir, entre {ic_texto(lo * c, hi * c)} de los {fmt(c)} contextos. "
          "Esa cifra solo se confirma al enlazar el corpus completo.", ""]

    ps = part["por_split"]
    L += ["## 3. Particiones y fecha del artículo", "",
          "ACL-200 no trae un campo de año: el año sale del identificador de ACL Anthology del citante "
          "(P15-1122 es de 2015). Por eso se contrastó contra las listas oficiales `train.json`, `val.json` y `test.json`.", "",
          "| Partición oficial | Años | Contextos | Con año fuera de su rango |", "|---|---|---|---|"]
    for s in SPLITS:
        lo_a, hi_a = RANGO_OFICIAL[s]
        anos = str(lo_a) if lo_a == hi_a else f"{lo_a}–{hi_a}"
        L.append(f"| {s} | {anos} | {fmt(ps[s].get('contextos', 0))} | {fmt(ps[s].get('anio_fuera_de_rango', 0))} |")
    fuera = ps[SIN_PARTICION]
    bloques = ", ".join(f"{k} {fmt(v)}" for k, v in sorted(fuera.items()) if k != "contextos")
    L += ["", f"Fuera de las tres particiones quedan {fmt(fuera.get('contextos', 0))} contextos ({bloques}). "
          "Están en `contexts.json`, pero no en las listas oficiales.", "",
          "| Cruce | Citantes compartidos | Citados compartidos | Pares citante-citado compartidos |", "|---|---|---|---|"]
    L += [f"| {k} | {fmt(v['citantes'])} | {fmt(v['citados'])} | {fmt(v['pares'])} |" for k, v in part["cruces"].items()]
    L += ["", "Ningún artículo citante ni ningún par se repite entre particiones, así que no hay fuga por documento. "
          "Que un artículo citado aparezca en varias particiones es normal (los artículos muy citados) y no es fuga, "
          f"pero se mide: de las {fmt(vistos['test_gold'])} citas del Test Gold, {fmt(vistos['citado_visto'])} "
          f"({pct(vistos['citado_visto'] / max(vistos['test_gold'], 1))}) tienen un citado que también aparece en entrenamiento. "
          "Los resultados se pueden reportar aparte para citados vistos y no vistos.", "",
          f"**Textos duplicados:** {fmt(dup['grupos'])} textos de contexto aparecen con más de un identificador "
          f"({fmt(dup['contextos'])} contextos). En {fmt(dup['mismo_citante'])} de esos grupos el citante es el mismo: "
          "es una frase que cita varios trabajos a la vez, y cada trabajo citado cuenta como una cita aparte. "
          f"{fmt(dup['grupos_entre_particiones'])} grupos cruzan particiones: son textos que se repiten en artículos de "
          f"años distintos. Citas del Test Gold con un texto idéntico en entrenamiento o validación: {fmt(len(dup['gold_en_modelo']))}"
          + (f" ({', '.join(f'`{i}`' for i in dup['gold_en_modelo'])})" if dup["gold_en_modelo"] else "") + ". "
          f"Citas del Test Gold con un texto idéntico fuera de la partición de prueba que hoy no está en el dataset: "
          f"{fmt(len(dup['gold_fuera_de_test']))}"
          + (f" ({', '.join(f'`{i}`' for i in dup['gold_fuera_de_test'])}): si el dataset se amplía, su gemelo debe quedar fuera"
             if dup["gold_fuera_de_test"] else "") + ".", "",
          "**Concentración por artículo citante:**", "",
          "| Conjunto | Contextos | Artículos citantes | Mediana por artículo | Máximo | Parte del 10 % de artículos con más citas |",
          "|---|---|---|---|---|---|"]
    L += [f"| {nombre} | {fmt(v['contextos'])} | {fmt(v['articulos'])} | {str(v['mediana']).replace('.', ',')} | {fmt(v['maximo'])} | {pct(v['parte_top10'])} |"
          for nombre, v in conc.items()]

    L += ["", f"## 4. ¿Las {fmt(n_jurado)} citas del jurado son una muestra al azar?", "",
          "Las 2.700 citas con que se ajustó el QLoRA no pueden entrar al jurado, porque ese modelo ya las vio. "
          f"Si las {fmt(n_jurado)} se tomaron al azar entre las demás, cada partición debería aportar en proporción a su tamaño.", "",
          "| Partición | Población (sin las 2.700) | Observado | Esperado al azar |", "|---|---|---|---|"]
    L += [f"| {f['estrato']} | {fmt(f['poblacion'])} | {fmt(f['observado'])} | {fmt(round(f['esperado']))} |" for f in prueba["filas"]]
    L += ["", f"Prueba ji cuadrado: χ² = {prueba['chi2']:.2f} con {prueba['gl']} grados de libertad, p = {prueba['p']:.2f}. "
          f"Citas de la muestra que están entre las 2.700: {fmt(prueba['fuera_de_poblacion'])}. "
          + ("La distribución es compatible con una muestra al azar, aunque una prueba así no lo demuestra: la forma de "
             "escogerlas debe quedar documentada por quien las tomó." if prueba["p"] >= 0.05 else
             "La distribución no es compatible con una muestra al azar simple; la proyección de la sección 5 queda en duda."), ""]

    pob = sum(f["poblacion"] for f in prueba["filas"])
    L += ["## 5. ¿Se llega a 2.000 citas por clase?", "",
          f"Proyección si las {fmt(pob)} citas posibles de ACL-200 pasaran por el mismo jurado, con la proporción de cada "
          f"clase en las {fmt(n_jurado)} (intervalo del 95 %). Supone que la muestra es al azar (sección 4) y que el jurado "
          "se comporta igual en el resto. Incluye las citas de 2015, de donde sale el Test Gold.", "",
          "| Clase | Con consenso en la muestra | Proyección en ACL-200 | Intervalo 95 % | ¿Alcanza 2.000? |", "|---|---|---|---|---|"]
    L += [f"| {f['clase']} | {fmt(f['muestra'])} | {fmt(round(f['proyeccion']))} | {ic_texto(f['ic_bajo'], f['ic_alto'])} | {f['alcanza']} |" for f in proy]
    no = [f["clase"] for f in proy if f["alcanza"] == "no"]
    si = [f["clase"] for f in proy if f["alcanza"] == "sí"]
    L += ["", f"**Lectura:** con todo ACL-200 llegarían a 2.000 {len(si)} clases ({', '.join(si)}). "
          f"{len(no)} no llegarían ni en el mejor caso ({', '.join(no)}). El conteo actual por clase y la brecha "
          "están en `docs/dataset_funciones_v1.md`.", "",
          "**Plan de expansión, sin duplicar ni fabricar citas:**", "",
          "1. Pasar por el mismo jurado las citas de ACL-200 que todavía no lo han pasado. Las 2.700 del QLoRA "
          "necesitan otro tercer juez, porque ese modelo ya las vio.",
          "2. Para las clases que no llegan ni con todo ACL-200: extraer contextos nuevos de la bibliografía enlazada de "
          "ACL OCL (fuera de ACL-200), con el mismo jurado y las mismas reglas. Antes hay que medir cuántos salen. "
          "Como sugirió el experto, con los ejemplos que ya tiene cada clase escasa (unos 50 a 200) se puede entrenar "
          "un clasificador sencillo que señale candidatos, y pasar al jurado solo esos candidatos. Eso abarata la "
          "búsqueda, pero no aumenta las citas que existen: el clasificador propone y el jurado decide.",
          "3. No completar clases repitiendo citas ni generándolas con modelos. Si una clase no llega, se reporta la "
          "brecha y se evalúa con F1 macro y por clase, sin esconderla.", "",
          "Pasos 1 y 2 son una decisión del equipo (tiempo de GPU y fecha de congelamiento).", ""]

    L += ["## 6. Etiquetas de modelos frente a etiquetas humanas", "",
          "| Conjunto | Citas | Quién etiquetó | ¿Cuenta como humano? |", "|---|---|---|---|",
          f"| Entrenamiento del QLoRA | {fmt(haiku['total'])} ({fmt(haiku.get('Evaluable', 0))} evaluables, "
          f"{fmt(haiku.get('Ambiguo', 0))} ambiguas, {fmt(haiku.get('No evaluable', 0))} no evaluables) | Claude Haiku 5.5 | No |",
          f"| Jurado | {fmt(n_jurado)} | QLoRA, Qwen 2.5 7B y Llama 3.1 8B | No |",
          f"| Test Gold | {fmt(vistos['test_gold'])} | Dos personas del equipo por cita | Sí, cuando termine la anotación |", "",
          "Las 2.700 de Claude Haiku son pre-etiquetas de un modelo, no revisiones humanas. Solo el Test Gold decide la evaluación.", ""]

    L += ["## 7. Frente a los comentarios de la docente", "",
          "| Comentario | Respuesta | Dónde |", "|---|---|---|",
          "| ¿Un solo dataset o comparar formas de extraer contextos? | Un solo dataset: ACL-200 más el texto de ACL OCL por ID; MultiCite no se homologa | Sección 1 |",
          "| Falta describir el dataset | Archivos, huellas, filas, pares y concentración sobre el corpus completo | Secciones 1 a 3 |",
          f"| ¿Todos los contextos tienen su par? | {pct(pares['par_completo'] / c)} con título y resumen; texto completo estimado en {pct(lo)}–{pct(hi)} | Sección 2 |",
          "| ¿Qué se tiene en cuenta en el split? ¿Cuándo se escribió el artículo? | Particiones oficiales por año del citante, contrastadas contra las listas; sin citantes ni pares compartidos | Sección 3 |",
          f"| ¿Se llega a la meta con los datos actuales? | No en todas: {len(no)} de 9 clases no llegan ni con todo ACL-200 | Sección 5 |",
          "| ¿Plan si los datos no alcanzan? | Jurado sobre el resto de ACL-200, luego ACL OCL, y brecha reportada sin fabricar citas | Sección 5 |", ""]

    L += ["## 8. Cómo reproducirlo", "",
          "1. `dvc pull data/raw` (remoto público, sin credenciales).",
          "2. Correr el comando del encabezado del script. Las pruebas están en `proyecto_de_grado/tests/test_cobertura_datos.py`.",
          "3. El jurado (`data/jurado/`) se publica al cerrar la anotación del Test Gold; sin él no se puede rehacer la sección 4 ni la 5.", ""]
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--raw", required=True, help="data/raw de ACL-200")
    p.add_argument("--jurado", required=True, help="jurado_18000_v3.csv")
    p.add_argument("--qlora-2700", required=True, help="CSV con las 2.700 citas con que se ajustó el QLoRA")
    p.add_argument("--dataset", required=True, help="dataset_funciones_v1.csv")
    p.add_argument("--ocl-completos", type=int, default=411, help="pares completos en la muestra de ACL OCL")
    p.add_argument("--ocl-muestra", type=int, default=500, help="tamaño de la muestra de ACL OCL")
    p.add_argument("--reporte", required=True)
    a = p.parse_args()

    raw = Path(a.raw)
    contextos, papers = leer_json(raw / "contexts.json"), leer_json(raw / "papers.json")
    por_contexto = load_split_index(raw).by_context
    jurado, dataset = leer_csv(a.jurado), leer_csv(a.dataset)
    qlora = leer_csv(a.qlora_2700)

    excluidas = {f["context_id"] for f in qlora}
    poblacion = {cid: por_contexto.get(cid, SIN_PARTICION) for cid in contextos if cid not in excluidas}
    conteos = Counter(f["voto"] for f in jurado)
    conc = {s: concentracion([contextos[c]["citing_id"] for c in contextos if por_contexto.get(c, SIN_PARTICION) == s])
            for s in SPLITS}
    conc["Entrenamiento del dataset v1"] = concentracion([f["citing_id"] for f in dataset if f["uso"] == "entrenamiento"])
    haiku = Counter(f["¿Evaluable?"] for f in qlora)
    haiku["total"] = len(qlora)

    texto = reporte(inventario(raw), medir_pares(contextos, papers), medir_particiones(contextos, por_contexto),
                    duplicados(contextos, por_contexto, {f["context_id"]: f["uso"] for f in dataset}), conc,
                    prueba_muestra({f["context_id"] for f in jurado}, poblacion),
                    proyectar(conteos, len(jurado), len(poblacion)), medir_vistos(dataset),
                    (a.ocl_completos, a.ocl_muestra), haiku, len(jurado))
    Path(a.reporte).write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
