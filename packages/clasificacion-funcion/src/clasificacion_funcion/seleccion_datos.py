"""Seleccion de datos limpios para los experimentos del issue #104 (dominio puro, solo stdlib).

Construye el pool P (citas con etiqueta de calidad conocida y sin fuga posible hacia el Test
Gold), la validacion fija V y las variantes de entrenamiento D1..D6. No lee archivos: recibe
`Fuentes` ya cargadas (la lectura vive en `adaptador_proyecto_grado`)."""
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import dominio

ABSTENCIONES = ("Ambiguo", "No evaluable")
# Los citantes de 2014 (split `val`) y 2015 (split `test`) alimentan el Test Gold: 1.299 de los
# 2.700 casos de TG2700 son de 2014. Se excluyen ambos anios, tambien lo aun no seleccionado.
ANIOS_EXCLUIDOS = (2014, 2015)
SEMILLA_V = 2026
TAMANO_V = 2300
N_PARTICIONES = 300
TOPE_CLASE = 2000
VARIANTES = ("qlora_p50", "qlora_p80", "jurado", "hibrido", "natural", "haiku_solo")
# Jerarquia de calidad de la etiqueta (menor = mejor). Fijada a priori.
NIVELES = {1: "jurado_3de3", 2: "haiku", 3: "jurado_2de3_coincide_qlora", 4: "qlora_p>=0.9",
           5: "jurado_2de3", 6: "qlora_p>=0.5"}


@dataclass
class Fuentes:
    """Todo lo que la seleccion necesita, indexado por context_id."""
    qlora: dict[str, dict]       # {"label", "p", "dist"}
    jurado: dict[str, dict]      # {"voto", "acuerdo", "qlora"}
    haiku: dict[str, str]        # etiqueta de Haiku (clase o abstencion)
    haiku_train: set[str]
    haiku_val: set[str]          # dev_haiku: casos que el QLoRA nunca vio
    gpt: dict[str, str]
    contextos: dict[str, dict]   # {"citing_id", "refid", "masked_text"}
    ids_gold: set[str]           # manifiesto v2 + TG2700 (nunca entran ni sus citantes)
    ids_excluidos: set[str] = field(default_factory=set)  # taller + piloto
    anios_excluidos: tuple[int, ...] = ANIOS_EXCLUIDOS


def anio_de(cid: str) -> int:
    """Anio del citante a partir del context_id (`P15-1102_...` -> 2015)."""
    aa = int(cid[1:3])
    return 2000 + aa if aa <= 30 else 1900 + aa


def _sha_texto(texto: str) -> str:
    return hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()


def _clase(etiqueta: str | None) -> str | None:
    """Etiqueta canonica de una de las 9 clases, o None si es abstencion/desconocida."""
    indice = dominio.normalizar_etiqueta(etiqueta) if etiqueta else None
    return None if indice is None else dominio.CATEGORIAS[indice]


def _voto(etiqueta: str | None) -> str | None:
    """Voto del jurado: `SIN_CONSENSO` (u otra marca no taxonomica) cuenta como sin voto."""
    try:
        return _clase(etiqueta)
    except ValueError:
        return None


def dist9(dist: list[float]) -> list[float]:
    """`dist` del QLoRA (9 clases + Ambiguo + No evaluable) renormalizada sin abstenciones."""
    base = dist[:dominio.N_CLASES]
    total = sum(base)
    return [x / total for x in base] if total > 0 else [1 / dominio.N_CLASES] * dominio.N_CLASES


def nivel_etiqueta(fila: dict) -> tuple[str | None, int | None]:
    """(etiqueta, nivel) de mejor calidad disponible segun `NIVELES`, o (None, None)."""
    j, h, q = fila.get("jurado"), fila.get("haiku"), fila.get("qlora")
    voto = _voto(j["voto"]) if j else None
    if voto and j["acuerdo"] >= 3:
        return voto, 1
    if h:
        return h, 2
    ql = _clase(q["label"]) if q else None
    if voto and j["acuerdo"] >= 2 and ql == voto:
        return voto, 3
    if ql and q["p"] >= 0.9:
        return ql, 4
    if voto and j["acuerdo"] >= 2:
        return voto, 5
    if ql and q["p"] >= 0.5:
        return ql, 6
    return None, None


# ------------------------------------------------------------------ pool
def construir_pool(f: Fuentes) -> tuple[list[dict], dict]:
    """Pool limpio P: una fila por cita con todas las etiquetas y su (etiqueta, nivel).

    Excluye: anios 2014/2015, ids de gold/taller/piloto, citantes de gold, citas cuyo texto
    coincide con el de una del gold y citas donde alguna fuente se abstiene."""
    citantes_gold = {f.contextos[c]["citing_id"] for c in f.ids_gold if c in f.contextos}
    sha_gold = {_sha_texto(f.contextos[c]["masked_text"]) for c in f.ids_gold if c in f.contextos}
    vetados = f.ids_gold | f.ids_excluidos
    descartes: Counter = Counter()
    pool = []
    for cid in sorted(set(f.qlora) | set(f.haiku)):
        ctx = f.contextos.get(cid)
        if ctx is None:
            descartes["sin_contexto"] += 1
        elif anio_de(cid) in f.anios_excluidos:
            descartes["anio_excluido"] += 1
        elif cid in vetados:
            descartes["id_vetado"] += 1
        elif ctx["citing_id"] in citantes_gold:
            descartes["citante_gold"] += 1
        elif _sha_texto(ctx["masked_text"]) in sha_gold:
            descartes["texto_gold"] += 1
        elif cid in f.haiku and _clase(f.haiku[cid]) is None:
            descartes["haiku_abstiene"] += 1
        elif cid in f.qlora and _clase(f.qlora[cid]["label"]) is None:
            descartes["qlora_abstiene"] += 1
        else:
            fila = {"context_id": cid, "citing_id": ctx["citing_id"], "cited_id": ctx["refid"],
                    "anio": anio_de(cid), "qlora": f.qlora.get(cid), "jurado": f.jurado.get(cid),
                    "haiku": _clase(f.haiku.get(cid)), "gpt": _clase(f.gpt.get(cid))}
            fila["etiqueta"], fila["nivel"] = nivel_etiqueta(fila)
            if fila["etiqueta"] is None:
                descartes["sin_etiqueta_confiable"] += 1
            else:
                pool.append(fila)
    return pool, {"pool": len(pool), "descartes": dict(descartes)}


# ------------------------------------------------------------------ validacion fija V
def _puntaje(conteo_v: Counter, total_clase: Counter, fraccion: float) -> float:
    """Desviacion relativa maxima de la fraccion de cada clase en V frente a la objetivo."""
    return max(abs(conteo_v[c] / n - fraccion) / fraccion for c, n in total_clase.items())


def dividir_validacion(pool: list[dict], forzar_citantes: set[str], semilla: int = SEMILLA_V,
                       tamano: int = TAMANO_V, n_particiones: int = N_PARTICIONES) -> set[str]:
    """Citantes de V (~`tamano` citas): agrupado por citante, estratificado por clase, mejor de N particiones."""
    por_citante: dict[str, list[dict]] = defaultdict(list)
    for fila in pool:
        por_citante[fila["citing_id"]].append(fila)
    forzados = sorted(c for c in forzar_citantes if c in por_citante)
    libres = sorted(c for c in por_citante if c not in set(forzados))
    meta = tamano
    fraccion = tamano / len(pool)
    total_clase = Counter(fila["etiqueta"] for fila in pool)
    mejor, mejor_puntaje = None, math.inf
    for i in range(n_particiones):
        rng = random.Random(semilla * 100_003 + i)
        orden = libres[:]
        rng.shuffle(orden)
        elegidos, conteo, n = set(forzados), Counter(), 0
        for c in forzados:
            conteo.update(f["etiqueta"] for f in por_citante[c])
            n += len(por_citante[c])
        for c in orden:
            if n >= meta:
                break
            elegidos.add(c)
            conteo.update(f["etiqueta"] for f in por_citante[c])
            n += len(por_citante[c])
        puntaje = _puntaje(conteo, total_clase, fraccion)
        if puntaje < mejor_puntaje:
            mejor, mejor_puntaje = elegidos, puntaje
    return mejor


# ------------------------------------------------------------------ variantes
def _clave_calidad(fila: dict) -> tuple:
    q = fila["qlora"]
    return (fila["nivel"], -(q["p"] if q else 0.0), fila["context_id"])


def _por_clase(filas: list[dict], clave, tope: int) -> list[dict]:
    grupos: dict[str, list[dict]] = defaultdict(list)
    for fila in filas:
        grupos[fila["etiqueta_entrenamiento"]].append(fila)
    return [f for c in sorted(grupos) for f in sorted(grupos[c], key=clave)[:tope]]


def _con_etiqueta(fila: dict, etiqueta: str, fuente: str) -> dict:
    return {**fila, "etiqueta_entrenamiento": etiqueta, "fuente": fuente}


def _filas_haiku(train: list[dict], f: Fuentes) -> list[dict]:
    return [_con_etiqueta(x, x["haiku"], "haiku") for x in train
            if x["context_id"] in f.haiku_train and x["haiku"]]


def construir_variantes(pool: list[dict], ids_v: set[str], f: Fuentes, tope: int = TOPE_CLASE,
                        semilla: int = SEMILLA_V) -> dict[str, list[dict]]:
    """D1..D6. Todas excluyen V (ya hecho en `train`) y los ids de Haiku val (dev_haiku)."""
    train = [x for x in pool if x["context_id"] not in ids_v and x["context_id"] not in f.haiku_val]
    haiku = _filas_haiku(train, f)
    ids_haiku = {x["context_id"] for x in haiku}
    sin_haiku = [x for x in train if x["context_id"] not in ids_haiku]

    def con_qlora(umbral: float) -> list[dict]:
        return [_con_etiqueta(x, _clase(x["qlora"]["label"]), "qlora") for x in sin_haiku
                if x["qlora"] and x["qlora"]["p"] >= umbral]

    def completar(base: list[dict], cand: list[dict], clave) -> list[dict]:
        cuenta = Counter(x["etiqueta_entrenamiento"] for x in base)
        extra = _por_clase(cand, clave, tope)
        salida = list(base)
        for x in extra:
            if cuenta[x["etiqueta_entrenamiento"]] < tope:
                salida.append(x)
                cuenta[x["etiqueta_entrenamiento"]] += 1
        return salida

    por_p = lambda x: (-x["qlora"]["p"], x["context_id"])
    d1 = completar(haiku, con_qlora(0.5), por_p)
    d2 = completar(haiku, con_qlora(0.8), por_p)
    jur = [_con_etiqueta(x, _voto(x["jurado"]["voto"]), "jurado") for x in sin_haiku
           if x["jurado"] and x["jurado"]["acuerdo"] >= 2 and _voto(x["jurado"]["voto"])]
    d3 = completar(haiku, jur, lambda x: (-x["jurado"]["acuerdo"],
                                          _voto(x["jurado"]["voto"]) != _clase(x["qlora"]["label"])
                                          if x["qlora"] else True,
                                          -(x["qlora"]["p"] if x["qlora"] else 0), x["context_id"]))
    hib = [_con_etiqueta(x, x["etiqueta"], f"nivel{x['nivel']}") for x in sin_haiku]
    d4 = completar(haiku, hib, _clave_calidad)
    rng = random.Random(semilla)
    candidatos = sorted(con_qlora(0.5), key=lambda x: x["context_id"])
    rng.shuffle(candidatos)
    d5 = haiku + candidatos[:max(0, len(d1) - len(haiku))]
    return {"qlora_p50": d1, "qlora_p80": d2, "jurado": d3, "hibrido": d4, "natural": d5,
            "haiku_solo": haiku}


# ------------------------------------------------------------------ fugas
def _casos(filas: list[dict], f: Fuentes) -> list[dict]:
    return [{"context_id": x["context_id"], "citing_id": x["citing_id"], "cited_id": x["cited_id"],
             "citation_context": f.contextos[x["context_id"]]["masked_text"]} for x in filas]


def _casos_gold(f: Fuentes) -> list[dict]:
    return [{"context_id": c, "citing_id": f.contextos[c]["citing_id"],
             "cited_id": f.contextos[c]["refid"], "citation_context": f.contextos[c]["masked_text"]}
            for c in sorted(f.ids_gold) if c in f.contextos]


def depurar_texto_repetido(train: list[dict], v: list[dict], f: Fuentes) -> tuple[list[dict], int]:
    """Quita de `train` las citas cuyo texto aparece en V (la regla de fuga lo bloquea)."""
    vistos = {_sha_texto(f.contextos[x["context_id"]]["masked_text"]) for x in v}
    limpio = [x for x in train
              if _sha_texto(f.contextos[x["context_id"]]["masked_text"]) not in vistos]
    return limpio, len(train) - len(limpio)


def verificar(variantes: dict[str, list[dict]], v: list[dict], f: Fuentes) -> dict:
    """Falla cerrado: reutiliza `dominio.verificar_fugas` (id, citante, par, sha de texto) para
    train~V y para ambos~gold, y exige 0 citas de los anios excluidos."""
    gold = _casos_gold(f)
    reportes = {}
    for nombre, filas in variantes.items():
        train, val = _casos(filas, f), _casos(v, f)
        # texto/par/citante frente al gold (el gold se pasa como conjunto, no como lista de ids)
        r = dominio.verificar_fugas({"train": train, "val": val, "gold": gold})
        # ids frente a taller/piloto y gold
        r2 = dominio.verificar_fugas({"train": train, "val": val}, excluidos=f.ids_excluidos,
                                     gold_v2=f.ids_gold)
        reportes[nombre] = {"fugas": {**r["fugas"], **r2["fugas"]},
                            "total_fugas": r["total_fugas"] + r2["total_fugas"]}
    for nombre, filas in {**variantes, "val": v}.items():
        malas = [x["context_id"] for x in filas if anio_de(x["context_id"]) in f.anios_excluidos]
        if malas:
            raise ValueError(f"{nombre} contiene {len(malas)} citas de anios excluidos: {malas[:3]}")
    return {"anios_excluidos": list(f.anios_excluidos),
            "citas_de_anios_excluidos": 0,
            "total_fugas": sum(r["total_fugas"] for r in reportes.values()),
            "por_variante": {n: r["fugas"] for n, r in reportes.items()}}


# ------------------------------------------------------------------ orquestacion
def construir_todo(f: Fuentes, semilla: int = SEMILLA_V, tope: int = TOPE_CLASE,
                   tamano_v: int = TAMANO_V, n_particiones: int = N_PARTICIONES) -> dict:
    """Pool, V, variantes y reporte de fugas. Lanza ValueError si hay cualquier fuga."""
    pool, info_pool = construir_pool(f)
    # dev_haiku (val de Haiku, 405) y ref_gpt (147) quedan siempre dentro de V
    forzar = {x["citing_id"] for x in pool
              if x["context_id"] in f.haiku_val or x["context_id"] in f.gpt}
    citantes_v = dividir_validacion(pool, forzar, semilla, tamano_v, n_particiones)
    v = [x for x in pool if x["citing_id"] in citantes_v]
    v = [_con_etiqueta(x, x["etiqueta"], f"nivel{x['nivel']}") for x in v]
    ids_v = {x["context_id"] for x in v}
    variantes = construir_variantes(pool, ids_v, f, tope, semilla)
    descartados = {}
    for n, filas in variantes.items():
        variantes[n], descartados[n] = depurar_texto_repetido(filas, v, f)
    fugas = verificar(variantes, v, f)
    fugas["descartados_por_texto_repetido_con_v"] = descartados
    return {"pool": pool, "v": v, "variantes": variantes, "info_pool": info_pool, "fugas": fugas}


def conteos(filas: list[dict], clave: str = "etiqueta_entrenamiento") -> dict[str, int]:
    c = Counter(x[clave] for x in filas)
    return {k: c.get(k, 0) for k in dominio.CATEGORIAS}


def sha_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def escribir_artefactos(res: dict, destino: Path, evidencias: Path,
                        insumos: dict[str, Path] | None = None) -> dict:
    """CSV por variante (+ V) en `destino` y `manifiesto_datos.json` en `evidencias`."""
    destino, evidencias = Path(destino), Path(evidencias)
    destino.mkdir(parents=True, exist_ok=True)
    evidencias.mkdir(parents=True, exist_ok=True)
    columnas = ["context_id", "citing_id", "etiqueta_entrenamiento", "fuente", "p", "nivel"]
    listas = {**res["variantes"], "validacion": res["v"]}
    shas = {}
    for nombre, filas in listas.items():
        ruta = destino / f"{nombre}.csv"
        with ruta.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(columnas)
            for x in filas:
                q = x["qlora"]
                w.writerow([x["context_id"], x["citing_id"], x["etiqueta_entrenamiento"],
                            x["fuente"], q["p"] if q else "", x["nivel"]])
        shas[nombre] = sha_archivo(ruta)
    manifiesto = {
        "semilla": SEMILLA_V, "tamano_v": TAMANO_V, "tope_por_clase": TOPE_CLASE,
        "niveles_calidad": NIVELES, "pool": res["info_pool"], "fugas": res["fugas"],
        "conteos": {n: conteos(filas) for n, filas in listas.items()},
        "n": {n: len(filas) for n, filas in listas.items()},
        "sha256_listas": shas,
        "sha256_ids": {n: dominio.sha_ids(sorted(x["context_id"] for x in filas))
                       for n, filas in listas.items()},
        "sha256_insumos": {k: sha_archivo(r) for k, r in (insumos or {}).items()},
    }
    (evidencias / "manifiesto_datos.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifiesto


# ------------------------------------------------------------------ auditoria de fuentes
def _etiquetas(f: Fuentes) -> dict[str, dict[str, str]]:
    def voto(r):
        return _voto(r["voto"])
    return {"qlora": {c: _clase(r["label"]) for c, r in f.qlora.items()},
            "jurado": {c: voto(r) for c, r in f.jurado.items()},
            "haiku": {c: _clase(e) for c, e in f.haiku.items()},
            "gpt": {c: _clase(e) for c, e in f.gpt.items()}}


def auditar_fuentes(f: Fuentes, cortes: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)) -> dict:
    """Acuerdo por pares entre QLoRA, jurado, Haiku y GPT en sus solapes (solo clases validas) y
    precision del QLoRA por tramo de `p` frente a Haiku y GPT."""
    et = _etiquetas(f)
    pares = {}
    nombres = list(et)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            comunes = [c for c in et[a].keys() & et[b].keys() if et[a][c] and et[b][c]]
            ok = sum(et[a][c] == et[b][c] for c in comunes)
            pares[f"{a}~{b}"] = {"n": len(comunes), "acuerdo": ok / len(comunes) if comunes else None}
    precision = {}
    for ref in ("haiku", "gpt"):
        for lo, hi in zip(cortes, (*cortes[1:], 1.0001)):
            comunes = [c for c in et["qlora"].keys() & et[ref].keys()
                       if et["qlora"][c] and et[ref][c] and lo <= f.qlora[c]["p"] < hi]
            ok = sum(et["qlora"][c] == et[ref][c] for c in comunes)
            precision[f"qlora_vs_{ref}_p[{lo},{min(hi, 1.0)})"] = {
                "n": len(comunes), "precision": ok / len(comunes) if comunes else None}
    return {"acuerdo_pares": pares, "precision_qlora_por_p": precision}
