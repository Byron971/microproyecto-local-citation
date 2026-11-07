"""Dominio puro (solo stdlib): taxonomia, metricas, fugas y construccion de entradas."""
import hashlib
import json
import math
import random

CATEGORIAS = (
    "Background",
    "Gap",
    "Basis",
    "Comparison",
    "Application",
    "Improvement / Modification",
    "Evidence",
    "Identification of the Originator",
    "Further Reading",
)
N_CLASES = len(CATEGORIAS)
MARCA_TARGET = "TARGETCIT"

_ALIAS = {
    "background": 0,
    "gap": 1,
    "basis": 2,
    "comparison": 3,
    "application": 4,
    "improvement / modification": 5,
    "improvement/modification": 5,
    "improvement": 5,
    "modification": 5,
    "evidence": 6,
    "identification of the originator": 7,
    "identification of originator": 7,
    "originator": 7,
    "further reading": 8,
}
# Abstenciones: se cuentan y se reportan, nunca forman una clase 10.
_ABSTENCIONES = {"ambiguo": "Ambiguo", "ambiguous": "Ambiguo",
                 "no evaluable": "No evaluable", "not evaluable": "No evaluable"}


def _limpiar(etiqueta: str) -> str:
    return " ".join(etiqueta.strip().casefold().split())


def normalizar_etiqueta(etiqueta) -> int | None:
    """Indice 0..8 de la categoria; None si es una abstencion (Ambiguo/No evaluable).

    Una etiqueta desconocida lanza ValueError (fail-closed)."""
    if isinstance(etiqueta, bool) or not isinstance(etiqueta, (str, int)):
        raise ValueError(f"Tipo de etiqueta no soportado: {type(etiqueta).__name__}")
    if isinstance(etiqueta, int):
        if 0 <= etiqueta < N_CLASES:
            return etiqueta
        raise ValueError(f"Indice de etiqueta fuera de rango: {etiqueta}")
    limpia = _limpiar(etiqueta)
    if limpia in _ALIAS:
        return _ALIAS[limpia]
    if limpia in _ABSTENCIONES:
        return None
    raise ValueError(f"Etiqueta desconocida: {etiqueta!r}")


def motivo_abstencion(etiqueta) -> str | None:
    """'Ambiguo' | 'No evaluable' si la etiqueta es una abstencion; si no, None."""
    if isinstance(etiqueta, str):
        return _ABSTENCIONES.get(_limpiar(etiqueta))
    return None


def separar_abstenciones(filas: list[dict], clave: str = "etiqueta") -> tuple[list[dict], dict]:
    """Devuelve (filas evaluables con `indice`, conteo de abstenciones por motivo)."""
    evaluables, abstenciones = [], {}
    for fila in filas:
        indice = normalizar_etiqueta(fila[clave])
        if indice is None:
            motivo = motivo_abstencion(fila[clave])
            abstenciones[motivo] = abstenciones.get(motivo, 0) + 1
        else:
            evaluables.append({**fila, "indice": indice})
    return evaluables, dict(sorted(abstenciones.items()))


# ---- hashes
def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha_ids(ids) -> str:
    """SHA-256 de los ids ordenados (independiente del orden de entrada)."""
    ids = list(ids)
    if len(set(ids)) != len(ids):
        raise ValueError("Ids duplicados.")
    return _sha(sorted(ids))


def sha_etiquetas(etiquetas: dict[str, int]) -> str:
    """SHA-256 de los pares (id, indice de clase) ordenados por id."""
    for indice in etiquetas.values():
        if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < N_CLASES:
            raise ValueError(f"Indice de clase invalido: {indice!r}")
    return _sha(sorted(etiquetas.items()))


# ---- metricas
def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def metricas(verdad: list[int], predicho: list[int]) -> dict:
    """P/R/F1 macro, micro y ponderado, por clase, soporte y matriz 9x9.

    Mismas claves y convencion que `paired_benchmark.model_metrics`
    (zero_division=0; el macro promedia las 9 clases, tambien las sin soporte)."""
    if len(verdad) != len(predicho):
        raise ValueError("verdad y predicho deben tener la misma longitud.")
    if not verdad:
        raise ValueError("Se necesita al menos un caso.")
    for v in (*verdad, *predicho):
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < N_CLASES:
            raise ValueError(f"Indice de clase invalido: {v!r}")
    matriz = [[0] * N_CLASES for _ in range(N_CLASES)]
    for t, p in zip(verdad, predicho):
        matriz[t][p] += 1
    n = len(verdad)
    por_clase, soportes = [], []
    for i in range(N_CLASES):
        tp = matriz[i][i]
        fn = sum(matriz[i]) - tp
        fp = sum(matriz[t][i] for t in range(N_CLASES)) - tp
        p, r, f = _prf(tp, fp, fn)
        soportes.append(tp + fn)
        por_clase.append({"label": CATEGORIAS[i], "support": tp + fn,
                          "precision": p, "recall": r, "f1": f})
    aciertos = sum(matriz[i][i] for i in range(N_CLASES))
    exactitud = aciertos / n
    macro = tuple(math.fsum(c[k] for c in por_clase) / N_CLASES
                  for k in ("precision", "recall", "f1"))
    pond = tuple(math.fsum(c[k] * c["support"] for c in por_clase) / n
                 for k in ("precision", "recall", "f1"))
    # Con las 9 clases y una prediccion por caso, micro P = R = F1 = exactitud.
    return {
        "n": n,
        "accuracy": exactitud,
        "precision_macro": macro[0], "recall_macro": macro[1], "f1_macro": macro[2],
        "precision_micro": exactitud, "recall_micro": exactitud, "f1_micro": exactitud,
        "precision_weighted": pond[0], "recall_weighted": pond[1], "f1_weighted": pond[2],
        "per_class": por_clase,
        "confusion_matrix": matriz,
    }


def pesos_clase(etiquetas: list[int]) -> list[float]:
    """Pesos inversos a la frecuencia: n / (9 * conteo). Clase ausente: 0.0."""
    if not etiquetas:
        raise ValueError("Se necesitan etiquetas.")
    conteo = [0] * N_CLASES
    for e in etiquetas:
        if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e < N_CLASES:
            raise ValueError(f"Indice de clase invalido: {e!r}")
        conteo[e] += 1
    n = len(etiquetas)
    return [n / (N_CLASES * c) if c else 0.0 for c in conteo]


def agregar_semillas(corridas: list[dict]) -> dict:
    """Media y desviacion estandar muestral (ddof=1; 0.0 con una sola semilla)
    de cada metrica escalar y del F1 por clase."""
    if not corridas:
        raise ValueError("Se necesita al menos una corrida.")

    def ms(valores: list[float]) -> dict:
        m = math.fsum(valores) / len(valores)
        sd = (math.sqrt(math.fsum((v - m) ** 2 for v in valores) / (len(valores) - 1))
              if len(valores) > 1 else 0.0)
        return {"media": m, "desv": sd}

    escalares = [k for k, v in corridas[0].items()
                 if k != "n" and isinstance(v, float)]
    for c in corridas:
        if [k for k, v in c.items() if k != "n" and isinstance(v, float)] != escalares:
            raise ValueError("Las corridas no tienen las mismas metricas.")
    salida = {"semillas": len(corridas), **{k: ms([c[k] for c in corridas]) for k in escalares}}
    salida["f1_por_clase"] = [
        {"label": CATEGORIAS[i], **ms([c["per_class"][i]["f1"] for c in corridas])}
        for i in range(N_CLASES)
    ]
    return salida


# ---- validacion de casos con chunks (sin la restriccion train de A1)
def validar_casos_chunks(casos: list[dict]) -> dict:
    """Invariantes de cita/corpus: TARGETCIT unico, chunks bien formados y articulos
    consistentes entre casos. No restringe el split (eso lo hace `verificar_fugas`)."""
    if not isinstance(casos, list):
        raise ValueError("Se necesita una lista de casos.")
    ids, huellas = set(), {}
    for caso in casos:
        cid, pid = caso.get("context_id"), caso.get("cited_id")
        if not isinstance(cid, str) or not cid or cid in ids:
            raise ValueError("context_id vacio o duplicado.")
        ids.add(cid)
        if not isinstance(pid, str) or not pid or caso.get("citing_id") == pid:
            raise ValueError(f"cited_id invalido o autocita en {cid}")
        ctx = caso.get("citation_context")
        if not isinstance(ctx, str) or ctx.count(MARCA_TARGET) != 1:
            raise ValueError(f"Contexto sin TARGETCIT unico en {cid}")
        chunks = caso.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError(f"Articulo sin chunks en {cid}")
        vistos, textos = set(), set()
        for c in chunks:
            chid, texto = c.get("chunk_id"), c.get("texto")
            if not isinstance(chid, str) or not chid or chid in vistos:
                raise ValueError(f"chunk_id vacio/duplicado en {cid}")
            vistos.add(chid)
            if not isinstance(texto, str) or not texto.strip():
                raise ValueError(f"Texto de chunk vacio en {cid}")
            norm = " ".join(texto.split())
            if norm in textos:
                raise ValueError(f"Texto de chunk duplicado en el articulo de {cid}")
            textos.add(norm)
        huella = _sha([(c["chunk_id"], c["texto"], c.get("seccion"), c.get("paragraph_indices"))
                       for c in chunks])
        if huellas.setdefault(pid, huella) != huella:
            raise ValueError(f"Chunks inconsistentes entre casos del mismo articulo: {pid}")
    return {"contextos": len(casos), "articulos": len(huellas)}


# ---- fugas
def _sha_texto(caso: dict) -> str:
    return hashlib.sha256(" ".join(caso["citation_context"].split()).encode("utf-8")).hexdigest()


def _claves(caso: dict) -> dict[str, object]:
    return {
        "context_id": caso["context_id"],
        "citing_id": caso["citing_id"],
        "par_citante_citado": (caso["citing_id"], caso["cited_id"]),
        "sha_texto_targetcit": _sha_texto(caso),
    }


def verificar_fugas(
    conjuntos: dict[str, list[dict]],
    excluidos: set[str] | frozenset[str] = frozenset(),
    gold_v2: set[str] | frozenset[str] = frozenset(),
) -> dict:
    """Compara train/val/eval por context_id, citing_id, par (citante, citado) y SHA del
    texto; ademas exclusiones y Gold v2. Cualquier interseccion > 0 lanza ValueError.
    El `cited_id` compartido solo se reporta (no bloquea)."""
    nombres = list(conjuntos)
    indices: dict[str, dict[str, set]] = {}
    for nombre, casos in conjuntos.items():
        ids = [c["context_id"] for c in casos]
        if len(set(ids)) != len(ids):
            raise ValueError(f"context_id duplicado dentro de {nombre}.")
        for c in casos:
            if not isinstance(c.get("citation_context"), str) or not c.get("citing_id") \
                    or not c.get("cited_id"):
                raise ValueError(f"Caso incompleto en {nombre}: {c.get('context_id')}")
        filas = [_claves(c) for c in casos]
        indices[nombre] = {k: {f[k] for f in filas}
                           for k in ("context_id", "citing_id", "par_citante_citado",
                                     "sha_texto_targetcit")}
        indices[nombre]["cited_id"] = {c["cited_id"] for c in casos}
    fugas: dict[str, int] = {}
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            for clave in ("context_id", "citing_id", "par_citante_citado", "sha_texto_targetcit"):
                fugas[f"{a}~{b}:{clave}"] = len(indices[a][clave] & indices[b][clave])
    for nombre in nombres:
        fugas[f"{nombre}~excluidos:context_id"] = len(indices[nombre]["context_id"] & set(excluidos))
        fugas[f"{nombre}~gold_v2:context_id"] = len(indices[nombre]["context_id"] & set(gold_v2))
    compartidos = {
        f"{a}~{b}": len(indices[a]["cited_id"] & indices[b]["cited_id"])
        for i, a in enumerate(nombres) for b in nombres[i + 1:]
    }
    reporte = {
        "conjuntos": {n: len(c) for n, c in conjuntos.items()},
        "fugas": fugas,
        "total_fugas": sum(fugas.values()),
        "cited_id_compartidos_no_bloqueante": compartidos,
    }
    if reporte["total_fugas"]:
        detalle = {k: v for k, v in fugas.items() if v}
        raise ValueError(f"Fuga entre conjuntos: {detalle}")
    return reporte


# ---------------------------------------------------------------- construccion de entradas
ENTRADAS = ("A", "B", "B_sin_seccion", "B_barajada")
TOP_K = 3
TOPE_CONTEXTO = 192
TOPE_TITULO = 48
MARCA = "TARGETCIT"
VERSION_ENTRADA = "a4_entrada_v1"
PLANTILLA = "[CLS] ctx [SEP] seg_1 [SEP] ... seg_n [SEP]"


def _texto(valor, nombre: str, cid) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre} vacio o ausente en {cid}")
    return " ".join(valor.split())


def construir_segmentos(caso: dict, entrada: str) -> list[dict]:
    """Segmentos de texto de una entrada, en orden: [{nombre, tipo, texto}].

    A = contexto, titulo, abstract. B = contexto + (perfil_i : chunk_i) x 3.
    B_sin_seccion omite el perfil. B_barajada usa `perfiles_barajados` (ver
    `barajar_secciones`). `caso` lleva `citation_context`, `titulo`, `abstract` y
    `top3` = [{chunk_id, texto, perfil}] ya ordenado por relevancia."""
    if entrada not in ENTRADAS:
        raise ValueError(f"Entrada desconocida: {entrada!r}")
    cid = caso.get("context_id")
    contexto = _texto(caso.get("citation_context"), "citation_context", cid)
    if contexto.count(MARCA) != 1:
        raise ValueError(f"Contexto sin {MARCA} unico en {cid}")
    segmentos = [{"nombre": "contexto", "tipo": "contexto", "texto": contexto}]
    if entrada == "A":
        segmentos.append({"nombre": "titulo", "tipo": "titulo",
                          "texto": _texto(caso.get("titulo"), "titulo", cid)})
        segmentos.append({"nombre": "abstract", "tipo": "abstract",
                          "texto": _texto(caso.get("abstract"), "abstract", cid)})
        return segmentos
    top3 = caso.get("top3")
    if not isinstance(top3, list) or len(top3) != TOP_K:
        raise ValueError(f"Top-{TOP_K} incompleto en {cid}")
    perfiles = [c.get("perfil") for c in top3]
    if entrada == "B_barajada":
        perfiles = caso.get("perfiles_barajados")
        if not isinstance(perfiles, list) or len(perfiles) != TOP_K:
            raise ValueError(f"B_barajada requiere `perfiles_barajados` (barajar_secciones) en {cid}")
    for i, (c, perfil) in enumerate(zip(top3, perfiles), 1):
        texto = _texto(c.get("texto"), f"chunk_{i}", cid)
        if entrada != "B_sin_seccion":
            if not isinstance(perfil, str) or not perfil:
                raise ValueError(f"Perfil de seccion ausente en chunk_{i} de {cid}")
            texto = f"{perfil} : {texto}"
        segmentos.append({"nombre": f"chunk_{i}", "tipo": "chunk", "texto": texto})
    return segmentos


def barajar_secciones(casos: list[dict], semilla: int) -> tuple[list[dict], str]:
    """Permutacion sembrada de `perfil` entre todos los chunks del conjunto.

    Conserva la marginal de perfiles. Devuelve (casos con `perfiles_barajados`,
    SHA de la permutacion). No depende del orden de entrada de `casos`."""
    ranuras = sorted((c["context_id"], i) for c in casos for i in range(len(c["top3"])))
    originales = {(c["context_id"], i): c["top3"][i].get("perfil")
                  for c in casos for i in range(len(c["top3"]))}
    perfiles = [originales[r] for r in ranuras]
    barajados = list(perfiles)
    random.Random(semilla).shuffle(barajados)
    nuevo = dict(zip(ranuras, barajados))
    sha = _sha({"semilla": semilla,
                "permutacion": [[cid, i, originales[(cid, i)], nuevo[(cid, i)]]
                                for cid, i in ranuras]})
    salida = [{**c, "perfiles_barajados": [nuevo[(c["context_id"], i)]
                                           for i in range(len(c["top3"]))]} for c in casos]
    return salida, sha


def tokenizar_segmentos(segmentos: list[dict], tokenizador) -> list[dict]:
    """Ids por segmento. En el contexto marca la posicion de TARGETCIT (`centro`)."""
    salida = []
    for seg in segmentos:
        if seg["tipo"] == "contexto":
            antes, despues = seg["texto"].split(MARCA)
            a, m, z = (tokenizador.ids(antes), tokenizador.ids(MARCA), tokenizador.ids(despues))
            salida.append({"nombre": seg["nombre"], "tipo": "contexto", "ids": a + m + z,
                           "centro": (len(a), len(a) + len(m))})
        else:
            salida.append({"nombre": seg["nombre"], "tipo": seg["tipo"],
                           "ids": tokenizador.ids(seg["texto"]), "centro": None})
    return salida


def reparto_water_filling(longitudes: list[int], presupuesto: int) -> list[int]:
    """Reparte `presupuesto` tokens: los segmentos cortos conservan todo y el sobrante
    se redistribuye entre los largos (deterministico; el resto entero va a los primeros)."""
    if presupuesto < 0:
        raise ValueError("Presupuesto negativo.")
    asignado = [0] * len(longitudes)
    pendientes = sorted(range(len(longitudes)), key=lambda i: (longitudes[i], i))
    restante = presupuesto
    while pendientes:
        parte = restante // len(pendientes)
        i = pendientes[0]
        if longitudes[i] <= parte:
            asignado[i] = longitudes[i]
            restante -= longitudes[i]
            pendientes.pop(0)
            continue
        for j in pendientes:
            asignado[j] = parte
        restante -= parte * len(pendientes)
        for j in sorted(pendientes):
            if restante and asignado[j] < longitudes[j]:
                asignado[j] += 1
                restante -= 1
        break
    return asignado


def _ventana_contexto(ids: list[int], centro: tuple[int, int], tope: int) -> list[int]:
    if len(ids) <= tope:
        return ids
    medio = (centro[0] + centro[1]) // 2
    inicio = min(max(medio - tope // 2, 0), len(ids) - tope)
    if centro[0] < inicio:  # el span de TARGETCIT nunca queda fuera de la ventana
        inicio = centro[0]
    return ids[inicio:inicio + tope]


def ensamblar(ids_segmentos: list[dict], max_len: int, cls: int, sep: int) -> dict:
    """`[CLS] ctx [SEP] seg_1 [SEP] ... seg_n [SEP]` con presupuesto por segmento.

    El contexto se reserva primero (tope 192; ventana centrada en TARGETCIT si se
    recorta). A: titulo con tope 48 y abstract recortado por la cola. B: el resto se
    reparte entre los chunks por water-filling. Devuelve input_ids, longitud y los
    tokens truncados por segmento."""
    if not ids_segmentos or ids_segmentos[0]["tipo"] != "contexto":
        raise ValueError("El primer segmento debe ser el contexto.")
    resto = ids_segmentos[1:]
    tipos = [s["tipo"] for s in resto]
    if tipos == ["titulo", "abstract"]:
        modo = "A"
    elif tipos and set(tipos) == {"chunk"}:
        modo = "B"
    else:
        raise ValueError(f"Combinacion de segmentos no soportada: {tipos}")
    presupuesto = max_len - 2 - len(resto)  # CLS + SEP del contexto + un SEP por segmento
    ctx = ids_segmentos[0]
    if presupuesto < 1 or ctx["centro"] is None:
        raise ValueError("max_len insuficiente o contexto sin posicion de TARGETCIT.")
    ventana = _ventana_contexto(ctx["ids"], ctx["centro"], min(TOPE_CONTEXTO, presupuesto))
    asignado = {"contexto": len(ventana)}
    libre = presupuesto - len(ventana)
    if modo == "A":
        titulo, abstract = resto
        t = min(len(titulo["ids"]), TOPE_TITULO, libre)
        a = min(len(abstract["ids"]), libre - t)
        asignado.update({"titulo": t, "abstract": a})
    else:
        reparto = reparto_water_filling([len(s["ids"]) for s in resto], libre)
        asignado.update({s["nombre"]: n for s, n in zip(resto, reparto)})
    ids = [cls, *ventana, sep]
    truncados = {"contexto": len(ctx["ids"]) - len(ventana)}
    for s in resto:
        n = asignado[s["nombre"]]
        ids += [*s["ids"][:n], sep]
        truncados[s["nombre"]] = len(s["ids"]) - n
    if len(ids) > max_len:
        raise ValueError("Secuencia ensamblada excede max_len.")
    return {"input_ids": ids, "longitud": len(ids), "truncados": truncados}


def especificacion_entrada(entrada: str, max_len: int, semilla_barajado: int | None = None) -> dict:
    """Especificacion de la entrada, independiente del tokenizer (mismo hash en SciBERT
    y SPECTER, como exige `a4_factorial_v1`)."""
    if entrada not in ENTRADAS:
        raise ValueError(f"Entrada desconocida: {entrada!r}")
    if (entrada == "B_barajada") != (semilla_barajado is not None):
        raise ValueError("La semilla de barajado aplica solo a B_barajada (y es obligatoria).")
    espec = {
        "version": VERSION_ENTRADA,
        "entrada": entrada,
        "max_len": max_len,
        "plantilla": PLANTILLA,
        "segmentos": {"A": ["contexto", "titulo", "abstract"]}.get(
            entrada, ["contexto", "chunk_1", "chunk_2", "chunk_3"]),
        "formato_chunk": {"B": "perfil : texto", "B_barajada": "perfil_barajado : texto",
                          "B_sin_seccion": "texto"}.get(entrada),
        "top_k": TOP_K if entrada != "A" else None,
        "tope_contexto": TOPE_CONTEXTO,
        "tope_titulo": TOPE_TITULO if entrada == "A" else None,
        "truncamiento": "abstract por la cola" if entrada == "A" else "water-filling",
        "ventana_contexto": "centrada en TARGETCIT",
        "perfil_seccion": "heuristica auditoria_corpus.perfil_seccion",
    }
    if semilla_barajado is not None:
        espec["semilla_barajado"] = semilla_barajado
    return espec


def sha_especificacion(especificacion: dict) -> str:
    return _sha(especificacion)
