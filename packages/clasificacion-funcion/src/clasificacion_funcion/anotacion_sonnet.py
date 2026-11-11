"""Anotacion con Sonnet via `claude -p` (issue #104, seccion 6 del plan). Solo stdlib.

Aislamiento: cada llamada corre en un directorio temporal vacio, sin herramientas, sin MCP y
sin comandos; el lote entra solo por el prompt y NUNCA incluye pre-etiquetas ni salidas de otras
pasadas. Las pasadas 2 y 3 se escriben en carpetas aparte. Reanudable: se salta todo lote cuya
salida ya es valida."""
import csv
import hashlib
import json
import random
import re
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import dominio

COLUMNAS_LOTE = ["context_id", "Contexto TARGETCIT", "Título citado", "Resumen citado"]
# Mismas columnas que el CSV de Haiku para lo anotado; `lote` y `pasada` trazan el origen.
# El texto de la cita no se repite aqui: se recupera por `context_id`.
COLUMNAS_SALIDA = ["N°", "context_id", "¿Evaluable?", "Función principal", "Confianza",
                   "Justificación / duda", "Estado", "lote", "pasada"]
EVALUABLE = ("Evaluable", "Ambiguo", "No evaluable")
CONFIANZA = ("Alta", "Media", "Baja")
SEMILLA = 2026
TAM_LOTE = 100


# ------------------------------------------------------------------ seleccion y lotes
def seleccionar_para_sonnet(v: list[dict], d1: list[dict]) -> list[str]:
    """V ∪ D1 (mismos ids que los experimentos; sin muestreo nuevo), ordenados."""
    return sorted({x["context_id"] for x in v} | {x["context_id"] for x in d1})


def crear_lotes(ids: list[str], tam: int = TAM_LOTE, semilla: int = SEMILLA) -> dict[int, list[str]]:
    """Lotes disjuntos y numerados desde 1; orden barajado con semilla fija."""
    if len(set(ids)) != len(ids):
        raise ValueError("Ids duplicados.")
    orden = sorted(ids)
    random.Random(semilla).shuffle(orden)
    return {i + 1: orden[k:k + tam] for i, k in enumerate(range(0, len(orden), tam))}


def nombre_lote(n: int) -> str:
    return f"lote_{n:03d}.csv"


def escribir_lotes(lotes: dict[int, list[str]], casos: dict[str, dict], carpeta: Path) -> None:
    """`casos[id]` = {contexto, titulo, abstract}. El lote no lleva ninguna etiqueta."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    for n, ids in lotes.items():
        with (carpeta / nombre_lote(n)).open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(COLUMNAS_LOTE)
            for cid in ids:
                c = casos[cid]
                w.writerow([cid, c["contexto"], c["titulo"], c["abstract"]])


def leer_csv(ruta: Path) -> list[dict]:
    with Path(ruta).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------------ prompt y respuesta
def sha_prompt(plantilla: str) -> str:
    return hashlib.sha256(plantilla.encode("utf-8")).hexdigest()


def construir_prompt(plantilla: str, filas: list[dict]) -> str:
    if "{{CASOS}}" not in plantilla:
        raise ValueError("La plantilla no contiene {{CASOS}}.")
    casos = [{"context_id": f["context_id"], "contexto": f["Contexto TARGETCIT"],
              "titulo": f["Título citado"], "resumen": f["Resumen citado"]} for f in filas]
    return plantilla.replace("{{CASOS}}", json.dumps(casos, ensure_ascii=False, indent=1))


def extraer_json(texto: str) -> list:
    """Arreglo JSON de la respuesta (tolera un bloque ```json ... ``` alrededor)."""
    t = texto.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    inicio, fin = t.find("["), t.rfind("]")
    if inicio < 0 or fin < inicio:
        raise ValueError("La respuesta no contiene un arreglo JSON.")
    try:
        datos = json.loads(t[inicio:fin + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido: {exc}") from exc
    if not isinstance(datos, list):
        raise ValueError("La respuesta no es un arreglo.")
    return datos


def validar_respuesta(datos: list, ids_lote: list[str]) -> list[dict]:
    """Filas validadas en el orden del lote. Lanza ValueError ante cualquier incumplimiento."""
    por_id: dict[str, dict] = {}
    for d in datos:
        if not isinstance(d, dict) or not isinstance(d.get("context_id"), str):
            raise ValueError(f"Fila sin context_id: {d!r}")
        if d["context_id"] in por_id:
            raise ValueError(f"context_id repetido: {d['context_id']}")
        por_id[d["context_id"]] = d
    faltan, sobran = set(ids_lote) - set(por_id), set(por_id) - set(ids_lote)
    if faltan or sobran:
        raise ValueError(f"Ids no coinciden con el lote (faltan {len(faltan)}, sobran {len(sobran)}).")
    filas = []
    for cid in ids_lote:
        d = por_id[cid]
        evaluable, conf = d.get("evaluable"), d.get("confianza")
        just = (d.get("justificacion_breve") or "").strip()
        if evaluable not in EVALUABLE:
            raise ValueError(f"{cid}: evaluable invalido {evaluable!r}")
        if conf not in CONFIANZA:
            raise ValueError(f"{cid}: confianza invalida {conf!r}")
        funcion = (d.get("funcion") or "").strip()
        if evaluable == "Evaluable":
            try:
                indice = dominio.normalizar_etiqueta(funcion)
            except ValueError as exc:
                raise ValueError(f"{cid}: funcion invalida {funcion!r}") from exc
            if indice is None:
                raise ValueError(f"{cid}: funcion invalida {funcion!r}")
            funcion = dominio.CATEGORIAS[indice]
        else:
            if funcion:
                raise ValueError(f"{cid}: {evaluable} con funcion {funcion!r}")
            if not just:
                raise ValueError(f"{cid}: {evaluable} sin justificacion")
        filas.append({"context_id": cid, "evaluable": evaluable, "funcion": funcion,
                      "confianza": conf, "justificacion": just})
    return filas


def escribir_salida(ruta: Path, filas: list[dict], lote: int, pasada: int) -> None:
    """Escritura atomica (tmp + rename): una salida a medias nunca cuenta como valida."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNAS_SALIDA)
        for i, f in enumerate(filas, 1):
            w.writerow([i, f["context_id"], f["evaluable"], f["funcion"], f["confianza"],
                        f["justificacion"], "COMPLETO" if f["evaluable"] == "Evaluable" else "REGISTRADO",
                        lote, pasada])
    tmp.replace(ruta)


def salida_valida(ruta: Path, ids_lote: list[str]) -> bool:
    if not Path(ruta).is_file():
        return False
    try:
        filas = leer_csv(ruta)
        datos = [{"context_id": f["context_id"], "evaluable": f["¿Evaluable?"], "funcion": f["Función principal"],
                  "confianza": f["Confianza"], "justificacion_breve": f["Justificación / duda"]}
                 for f in filas]
        validar_respuesta(datos, ids_lote)
        return True
    except (ValueError, KeyError):
        return False


# ------------------------------------------------------------------ ejecucion con claude
def ejecutar_claude(prompt: str, modelo: str = "sonnet", binario: str = "claude",
                    timeout: float = 900) -> dict:
    """Una llamada aislada a `claude -p`: directorio temporal vacio, sin herramientas, MCP ni
    comandos, sin persistir la sesion. Devuelve {texto, entrada, salida, duracion_s}."""
    orden = [binario, "-p", "--model", modelo, "--output-format", "json", "--tools", "",
             "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"]
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="sonnet_aislado_") as vacio:
        r = subprocess.run(orden, input=prompt, capture_output=True, text=True, cwd=vacio,
                           timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"claude termino con codigo {r.returncode}: {r.stderr.strip()[:300]}")
    try:
        sobre = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Salida de claude no es JSON: {r.stdout[:200]!r}") from exc
    if sobre.get("is_error"):
        raise RuntimeError(f"claude reporto error: {str(sobre.get('result'))[:300]}")
    uso = sobre.get("usage") or {}
    entrada = sum(uso.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                          "cache_read_input_tokens"))
    return {"texto": sobre.get("result", ""), "entrada": entrada, "salida": uso.get("output_tokens", 0),
            "duracion_s": round(time.perf_counter() - t0, 2)}


def anotar_lote(n: int, carpeta_lotes: Path, carpeta_salidas: Path, plantilla: str, ejecutar,
                pasada: int = 1, reintentos: int = 1) -> dict:
    """Anota un lote y devuelve su linea de registro. No lanza: un fallo queda `estado=error`."""
    filas_lote = leer_csv(Path(carpeta_lotes) / nombre_lote(n))
    ids = [f["context_id"] for f in filas_lote]
    ruta = Path(carpeta_salidas) / nombre_lote(n)
    base = {"lote": n, "pasada": pasada, "casos": len(ids), "prompt_sha256": sha_prompt(plantilla)[:16]}
    if salida_valida(ruta, ids):
        return {**base, "estado": "omitido_ya_valido"}
    prompt = construir_prompt(plantilla, filas_lote)
    entrada = salida = 0
    duracion = 0.0
    error = ""
    for intento in range(1 + reintentos):
        try:
            r = ejecutar(prompt)
            entrada, salida, duracion = entrada + r["entrada"], salida + r["salida"], duracion + r["duracion_s"]
            validadas = validar_respuesta(extraer_json(r["texto"]), ids)
            escribir_salida(ruta, validadas, n, pasada)
            return {**base, "estado": "ok", "intentos": intento + 1, "tokens_entrada": entrada,
                    "tokens_salida": salida, "duracion_s": round(duracion, 2)}
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
    return {**base, "estado": "error", "intentos": 1 + reintentos, "error": error,
            "tokens_entrada": entrada, "tokens_salida": salida, "duracion_s": round(duracion, 2)}


def anotar_pendientes(carpeta_lotes: Path, carpeta_salidas: Path, plantilla: str, ejecutar,
                      registro: Path, pasada: int = 1, max_lotes: int | None = None,
                      paralelo: int = 4) -> dict:
    """Anota los lotes pendientes (hasta `max_lotes`) con `paralelo` hilos; anade al registro."""
    todos = sorted(int(p.stem.split("_")[1]) for p in Path(carpeta_lotes).glob("lote_*.csv"))
    pendientes = []
    for n in todos:
        ids = [f["context_id"] for f in leer_csv(Path(carpeta_lotes) / nombre_lote(n))]
        if not salida_valida(Path(carpeta_salidas) / nombre_lote(n), ids):
            pendientes.append(n)
    if max_lotes is not None:
        pendientes = pendientes[:max_lotes]
    cerrojo = threading.Lock()
    registro = Path(registro)
    registro.parent.mkdir(parents=True, exist_ok=True)

    def tarea(n: int) -> dict:
        linea = anotar_lote(n, carpeta_lotes, carpeta_salidas, plantilla, ejecutar, pasada)
        with cerrojo, registro.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linea, ensure_ascii=False) + "\n")
        return linea

    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as pool:
        lineas = list(pool.map(tarea, pendientes))
    return {"total_lotes": len(todos), "intentados": len(lineas),
            "ok": sum(x["estado"] == "ok" for x in lineas),
            "error": sum(x["estado"] == "error" for x in lineas),
            "ya_validos": len(todos) - len(pendientes)}


PROMPT_AISLAMIENTO = (
    "Sin usar herramientas: ¿que herramientas, skills, memorias, archivos CLAUDE.md o instrucciones "
    "de usuario tienes disponibles? Cita textualmente el primer renglon de cada una, o responde "
    "NINGUNA. Responde en pocas lineas.")


def verificar_aislamiento(ejecutar) -> dict:
    """Una llamada minima con la misma configuracion aislada: los tokens de entrada son el costo
    fijo por llamada (sin lote) y la respuesta muestra lo que el modelo dice ver."""
    r = ejecutar(PROMPT_AISLAMIENTO)
    return {"tokens_entrada": r["entrada"], "tokens_salida": r["salida"],
            "duracion_s": r["duracion_s"], "respuesta": r["texto"]}


# ------------------------------------------------------------------ piloto
def seleccionar_piloto(taller: dict[str, str], gpt: dict[str, str], jurado: dict[str, dict],
                       contextos: dict, n_jurado: int = 110, semilla: int = SEMILLA) -> dict:
    """~300 citas con referencia: taller (clave experta humana), ref_gpt y muestra con jurado 3/3.
    Devuelve {ids, referencias: {nombre: {id: etiqueta}}}. Se anota aparte; nunca entra al train."""
    taller = {c: e for c, e in taller.items() if c in contextos}
    gpt = {c: e for c, e in gpt.items() if c in contextos}
    j3 = sorted(c for c, r in jurado.items()
                if r["acuerdo"] >= 3 and c in contextos and c not in taller and c not in gpt
                and r["voto"] in dominio.CATEGORIAS)
    random.Random(semilla).shuffle(j3)
    j3 = j3[:n_jurado]
    refs = {"taller": taller, "gpt": gpt, "jurado_3de3": {c: jurado[c]["voto"] for c in j3}}
    return {"ids": sorted(set(taller) | set(gpt) | set(j3)), "referencias": refs}


def informe_piloto(carpeta_salidas: Path, referencias: dict[str, dict[str, str]], registro: Path,
                   lotes_totales: int) -> dict:
    """Acuerdo de Sonnet con cada referencia (solo casos Evaluable) y costo extrapolado."""
    sonnet = {}
    for ruta in sorted(Path(carpeta_salidas).glob("lote_*.csv")):
        for f in leer_csv(ruta):
            sonnet[f["context_id"]] = f["Función principal"] if f["¿Evaluable?"] == "Evaluable" else f["¿Evaluable?"]
    acuerdo = {}
    for nombre, ref in referencias.items():
        comunes = [c for c in ref if c in sonnet and sonnet[c] in dominio.CATEGORIAS]
        ok = sum(sonnet[c] == ref[c] for c in comunes)
        acuerdo[nombre] = {"n": len(comunes), "acuerdo": ok / len(comunes) if comunes else None}
    lineas = [json.loads(l) for l in Path(registro).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [x for x in lineas if x["estado"] == "ok"]
    ent = sum(x["tokens_entrada"] for x in ok) / len(ok) if ok else 0
    sal = sum(x["tokens_salida"] for x in ok) / len(ok) if ok else 0
    seg = sum(x["duracion_s"] for x in ok) / len(ok) if ok else 0
    abst = sum(v in ("Ambiguo", "No evaluable") for v in sonnet.values())
    return {"casos_anotados": len(sonnet), "abstenciones": abst, "acuerdo": acuerdo,
            "lotes_ok": len(ok), "lotes_error": sum(x["estado"] == "error" for x in lineas),
            "tokens_entrada_por_lote": ent, "tokens_salida_por_lote": sal, "segundos_por_lote": seg,
            "extrapolacion": {"lotes": lotes_totales, "tokens_entrada": ent * lotes_totales,
                              "tokens_salida": sal * lotes_totales,
                              "horas_secuencial": seg * lotes_totales / 3600}}


# ------------------------------------------------------------------ consolidacion
def consolidar(carpeta_salidas: Path, destino: Path) -> int:
    """Une las salidas validas de una carpeta en un CSV ordenado por lote y N°."""
    filas = []
    for ruta in sorted(Path(carpeta_salidas).glob("lote_*.csv")):
        filas += leer_csv(ruta)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS_SALIDA)
        w.writeheader()
        w.writerows(filas)
    return len(filas)
