"""Controles de fuga y casos de la Entrada B sobre los datos del issue #104 (dominio puro, stdlib).

Con Entrada B el input lleva chunks del texto completo del articulo citado. Si ese articulo es a
su vez un citante de V o del Gold, sus chunks contienen frases de citas de V/Gold: contaminan la
seleccion (early stopping) o la evaluacion. Estas funciones detectan y cierran esas fugas; el
notebook 06 solo las orquesta. Todas fallan cerrado (`ValueError`) cuando una regla se rompe."""
import hashlib
import re
from collections import Counter, defaultdict

from . import dominio, seleccion_datos

K_SHINGLE = 8
UMBRAL_SOLAPE = 0.5
_MARCADORES = re.compile(r"\b(?:TARGETCIT|OTHERCIT)\b")
_PALABRAS = re.compile(r"[a-z0-9]+")
# Cotas del histograma de solapes (inferior excluida, superior incluida; el 0 va aparte).
_COTAS = (0.1, 0.2, 0.3, 0.4, 0.5)


# ---------------------------------------------------------------- L2 / L3: citados que son citantes
def citantes_gold(f: seleccion_datos.Fuentes) -> set[str]:
    """Articulos citantes de las citas del Gold v2 y de TG2700 (`f.ids_gold`)."""
    return {f.contextos[c]["citing_id"] for c in f.ids_gold if c in f.contextos}


def citantes_evaluacion(f: seleccion_datos.Fuentes, v: list[dict]) -> set[str]:
    """Citantes de V, del Gold v2, de TG2700 y de las citas excluidas (taller/piloto/calibracion).

    Un entrenamiento cuyo citado es uno de ellos metería en su input texto de esos citantes."""
    ids = {x["citing_id"] for x in v} | citantes_gold(f)
    ids |= {f.contextos[c]["citing_id"] for c in f.ids_excluidos if c in f.contextos}
    return ids


def _citado(fila: dict, contextos: dict) -> str:
    ctx = contextos.get(fila["context_id"])
    if not isinstance(ctx, dict):
        raise ValueError(f"Contexto ausente del indice: {fila['context_id']}")
    return ctx["refid"]


def excluir_citas_a_citantes(filas: list[dict], contextos: dict,
                             citantes: set[str]) -> tuple[list[dict], dict[str, int]]:
    """L2: quita las filas cuyo `cited_id` esta en `citantes`. Devuelve (filas, conteo por clase
    de lo quitado). Se aplica igual a las entradas A y B para que ambas usen las mismas citas."""
    limpias, quitadas = [], Counter()
    for x in filas:
        if _citado(x, contextos) in citantes:
            quitadas[x.get("etiqueta_entrenamiento", "sin_etiqueta")] += 1
        else:
            limpias.append(x)
    return limpias, dict(sorted(quitadas.items()))


def verificar_citados_v(v: list[dict], contextos: dict, citantes_prohibidos: set[str]) -> dict:
    """L3: ninguna cita de V puede citar un articulo que sea citante del Gold. Lanza ValueError."""
    malas = sorted(x["context_id"] for x in v if _citado(x, contextos) in citantes_prohibidos)
    if malas:
        raise ValueError(f"{len(malas)} citas de V citan un citante del Gold: {malas[:5]}")
    return {"citas_v_a_citantes_gold": 0, "citas_v": len(v)}


# ---------------------------------------------------------------- L4: solape de texto
def _hash(texto: str) -> int:
    return int.from_bytes(hashlib.blake2b(texto.encode("utf-8"), digest_size=8).digest(), "big")


def shingles(texto: str, k: int = K_SHINGLE) -> set[int]:
    """Hashes de los k-gramas de palabras (minusculas, solo alfanumericas). Los marcadores
    TARGETCIT/OTHERCIT cortan el texto: no se arman k-gramas que los crucen, porque en el articulo
    original ahi hay una referencia bibliografica real y no un hueco."""
    salida: set[int] = set()
    for segmento in _MARCADORES.split(texto):
        palabras = _PALABRAS.findall(segmento.lower())
        for i in range(len(palabras) - k + 1):
            salida.add(_hash(" ".join(palabras[i:i + k])))
    return salida


def _indice_invertido(contextos: dict[str, str], k: int) -> tuple[dict[int, list[str]], dict[str, int]]:
    indice: dict[int, list[str]] = defaultdict(list)
    tamanos = {}
    for cid, texto in contextos.items():
        s = shingles(texto, k)
        tamanos[cid] = len(s)
        for h in s:
            indice[h].append(cid)
    return indice, tamanos


def _cubeta(solape: float) -> str:
    if solape <= 0:
        return "0"
    previo = 0.0
    for cota in _COTAS:
        if solape <= cota:
            return f"({previo:g},{cota:g}]"
        previo = cota
    return f">{_COTAS[-1]:g}"


def solapes_texto(chunks_por_conjunto: dict[str, list[dict]], contextos_eval: dict[str, dict[str, str]],
                  umbral: float = UMBRAL_SOLAPE, k: int = K_SHINGLE) -> dict:
    """L4: que ningun chunk de un input contenga texto de un contexto de evaluacion.

    `chunks_por_conjunto` = {nombre: [{context_id, cited_id, chunk_id, texto}]}: SOLO los chunks que
    entran a los inputs (el mismo chunk repetido en varias citas se cuenta una vez).
    `contextos_eval` = {nombre: {context_id: masked_text}}. Cada conjunto de chunks se compara con
    todos los contextos de evaluacion de OTRO nombre (train vs V y Gold, V vs Gold). El solape de un
    chunk con un contexto es |shingles comunes| / min(|shingles chunk|, |shingles contexto|): un
    contexto corto copiado dentro de un parrafo largo da 1.0 aunque sea una fraccion del parrafo.
    Detecta el mismo articulo bajo otro ID (version de taller o de revista), que L2 no ve.

    Devuelve el reporte con `total_violaciones` (solapes >= `umbral`); ver `exigir_sin_solapes`."""
    indices = {n: _indice_invertido(c, k) for n, c in contextos_eval.items()}
    pares, total = {}, 0
    for nombre, chunks in chunks_por_conjunto.items():
        unicos = {(c["cited_id"], c["chunk_id"]): c for c in chunks}
        huellas = {clave: shingles(c["texto"], k) for clave, c in unicos.items()}  # una vez por chunk
        for objetivo, (indice, tamanos) in indices.items():
            if objetivo == nombre:
                continue
            cubetas: Counter = Counter()
            violaciones, maximo = [], 0.0
            for clave, c in unicos.items():
                s = huellas[clave]
                comunes: Counter = Counter()
                for h in s:
                    comunes.update(indice.get(h, ()))
                mejor, mejor_cid = 0.0, None
                for cid, n in comunes.items():
                    solape = n / min(len(s), tamanos[cid])
                    if solape > mejor:
                        mejor, mejor_cid = solape, cid
                cubetas[_cubeta(mejor)] += 1
                maximo = max(maximo, mejor)
                if mejor >= umbral:
                    violaciones.append({"context_id": c["context_id"], "cited_id": c["cited_id"],
                                        "chunk_id": c["chunk_id"], "contexto_eval": mejor_cid,
                                        "solape": round(mejor, 4)})
            total += len(violaciones)
            pares[f"{nombre}~{objetivo}"] = {
                "conjunto": nombre, "objetivo": objetivo, "chunks_unicos": len(unicos),
                "contextos": len(tamanos), "max_solape": round(maximo, 4),
                "histograma": dict(sorted(cubetas.items())), "violaciones": len(violaciones),
                "detalle": sorted(violaciones, key=lambda v: (-v["solape"], v["cited_id"], v["chunk_id"]))}
    return {"umbral": umbral, "k_shingle": k, "pares": pares, "total_violaciones": total}


def citados_con_solape(reporte: dict, conjunto: str) -> set[str]:
    """Articulos citados con algun chunk (de los del `conjunto`) que solapa >= umbral con un contexto
    de evaluacion. Casi siempre es el mismo articulo bajo otro ID (version de taller/revista) o texto
    reutilizado por los mismos autores: TODO ese citado es sospechoso, no solo el chunk detectado."""
    return {v["cited_id"] for r in reporte["pares"].values() if r["conjunto"] == conjunto
            for v in r["detalle"]}


def exigir_sin_solapes(reporte: dict) -> dict:
    """Falla cerrado si `solapes_texto` encontro algun chunk con solape >= umbral."""
    if reporte["total_violaciones"]:
        detalle = {p: r["violaciones"] for p, r in reporte["pares"].items() if r["violaciones"]}
        raise ValueError(f"Chunks con >= {reporte['umbral']:.0%} de shingles de un contexto de "
                         f"evaluacion: {detalle}")
    return reporte


# ---------------------------------------------------------------- casos y entradas B
def casos_para_chunks(filas: list[dict], contextos: dict) -> list[dict]:
    """Filas de datos -> casos con la forma de `servicio._caso` (la que consume
    `servicio.construir_casos_split`). `indice` solo si la fila trae etiqueta de entrenamiento."""
    casos = []
    for x in filas:
        ctx = contextos.get(x["context_id"])
        if not isinstance(ctx, dict):
            raise ValueError(f"Contexto ausente del indice: {x['context_id']}")
        caso = {"context_id": x["context_id"], "citing_id": ctx["citing_id"],
                "cited_id": ctx["refid"], "citation_context": ctx["masked_text"]}
        if x.get("etiqueta_entrenamiento") is not None:
            caso["indice"] = dominio.normalizar_etiqueta(x["etiqueta_entrenamiento"])
        casos.append(caso)
    return casos


def entradas_por_contexto(entradas: dict[str, list[dict]]) -> dict[str, dict]:
    """{context_id: entrada B} uniendo conjuntos (un mismo contexto puede estar en train_M y train_S).
    Un contexto repetido debe tener exactamente el mismo Top-3."""
    union: dict[str, dict] = {}
    for nombre, lista in entradas.items():
        for e in lista:
            previa = union.setdefault(e["context_id"], e)
            if previa is not e and [c["chunk_id"] for c in previa["top3"]] != \
                    [c["chunk_id"] for c in e["top3"]]:
                raise ValueError(f"Top-3 distinto para {e['context_id']} entre conjuntos ({nombre}).")
    return union


def verificar_mismos_ids(nombre: str, casos_a: list[dict], casos_b: list[dict]) -> str:
    """L5: las entradas A y B de un conjunto cubren exactamente los mismos context_id.
    Devuelve el sha de los ids; lanza ValueError si difieren."""
    sha_a = dominio.sha_ids(c["context_id"] for c in casos_a)
    sha_b = dominio.sha_ids(c["context_id"] for c in casos_b)
    if sha_a != sha_b:
        diferencia = {c["context_id"] for c in casos_a} ^ {c["context_id"] for c in casos_b}
        raise ValueError(f"Los ids de A y B difieren en {nombre}: {len(diferencia)} casos, "
                         f"p. ej. {sorted(diferencia)[:3]}")
    return sha_a
