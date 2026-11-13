"""Verifica que `etiquetas_sonnet.csv` sirva para entrenar (issue #104). Solo stdlib.

Cada comprobacion produce un hallazgo `error` (bloquea el uso en entrenamiento) o `aviso`
(revisar, no bloquea). No modifica nada: devuelve un informe."""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import anotacion_sonnet as an
from . import dominio, seleccion_datos

ID_CITA = re.compile(r"^[A-Z]\d{2}-\d{4}_[A-Z]\d{2}-\d{4}_\d+$")
MIN_SOPORTE_CLASE = 50
MAX_FRAC_BAJA = 0.05


class _Hallazgos:
    def __init__(self) -> None:
        self.errores: list[str] = []
        self.avisos: list[str] = []

    def error(self, msg: str) -> None:
        self.errores.append(msg)

    def aviso(self, msg: str) -> None:
        self.avisos.append(msg)


def _muestra(ids, n: int = 5) -> str:
    ids = sorted(ids)
    return f"{ids[:n]}{' ...' if len(ids) > n else ''} ({len(ids)})"


def _estructura(filas: list[dict], columnas: list[str], h: _Hallazgos) -> None:
    if columnas != an.COLUMNAS_SALIDA:
        h.error(f"Columnas {columnas} != esperadas {an.COLUMNAS_SALIDA}")
        return
    vacias = Counter(c for f in filas for c in ("context_id", "¿Evaluable?", "Confianza", "Estado", "lote", "pasada")
                     if not (f[c] or "").strip())
    if vacias:
        h.error(f"Campos obligatorios vacios: {dict(vacias)}")
    cuenta = Counter(f["context_id"] for f in filas)
    dup = [c for c, n in cuenta.items() if n > 1]
    if dup:
        h.error(f"context_id duplicados: {_muestra(dup)}")
    malos = [f["context_id"] for f in filas if not ID_CITA.match(f["context_id"])]
    if malos:
        h.error(f"context_id con formato inesperado: {_muestra(malos)}")
    if {f["pasada"] for f in filas} != {"1"}:
        h.error(f"`pasada` debe ser solo 1: {dict(Counter(f['pasada'] for f in filas))}")
    por_lote: dict[str, list[dict]] = defaultdict(list)
    for f in filas:
        por_lote[f["lote"]].append(f)
    for lote, fs in por_lote.items():
        if [f["N°"] for f in fs] != [str(i) for i in range(1, len(fs) + 1)]:
            h.error(f"lote {lote}: la numeracion N° no es 1..{len(fs)} en orden")
        if len(fs) > an.TAM_LOTE:
            h.error(f"lote {lote}: {len(fs)} filas > {an.TAM_LOTE}")


def _semantica(filas: list[dict], h: _Hallazgos) -> None:
    for campo, validos in (("¿Evaluable?", an.EVALUABLE), ("Confianza", an.CONFIANZA)):
        raros = Counter(f[campo] for f in filas if f[campo] not in validos)
        if raros:
            h.error(f"{campo} fuera de {validos}: {dict(raros)}")
    canon = set(dominio.CATEGORIAS)
    ev = [f for f in filas if f["¿Evaluable?"] == "Evaluable"]
    fuera = Counter(f["Función principal"] for f in ev if f["Función principal"] not in canon)
    if fuera:  # con alias el cargador igual normaliza; se avisa; si no normaliza es un error
        no_norm = {}
        for v, n in fuera.items():
            try:
                if dominio.normalizar_etiqueta(v) is None:
                    no_norm[v] = n
            except ValueError:
                no_norm[v] = n
        if no_norm:
            h.error(f"Evaluable con funcion que no es una de las 9 clases: {no_norm}")
        else:
            h.aviso(f"Evaluable con funcion no canonica (alias normalizable): {dict(fuera)}")
    con_funcion = [f["context_id"] for f in filas if f["¿Evaluable?"] != "Evaluable" and f["Función principal"].strip()]
    if con_funcion:
        h.error(f"Abstencion con funcion principal: {_muestra(con_funcion)}")
    sin_just = [f["context_id"] for f in filas
                if f["¿Evaluable?"] != "Evaluable" and not f["Justificación / duda"].strip()]
    if sin_just:
        h.error(f"Abstencion sin justificacion: {_muestra(sin_just)}")
    estado_mal = [f["context_id"] for f in filas
                  if f["Estado"] != ("COMPLETO" if f["¿Evaluable?"] == "Evaluable" else "REGISTRADO")]
    if estado_mal:
        h.error(f"`Estado` inconsistente con ¿Evaluable?: {_muestra(estado_mal)}")
    sin_just_ev = sum(1 for f in ev if not f["Justificación / duda"].strip())
    if sin_just_ev:
        h.aviso(f"{sin_just_ev} Evaluable sin justificacion")


def _distribucion(filas: list[dict], h: _Hallazgos) -> dict:
    ev = [f for f in filas if f["¿Evaluable?"] == "Evaluable" and f["Función principal"] in set(dominio.CATEGORIAS)]
    por_clase = Counter(f["Función principal"] for f in ev)
    conf = Counter(f["Confianza"] for f in filas)
    for clase in dominio.CATEGORIAS:
        if por_clase[clase] == 0:
            h.error(f"Clase sin ningun ejemplo: {clase}")
        elif por_clase[clase] < MIN_SOPORTE_CLASE:
            h.aviso(f"Clase con poco soporte ({por_clase[clase]}): {clase}")
    if filas and conf["Baja"] / len(filas) > MAX_FRAC_BAJA:
        h.aviso(f"{conf['Baja'] / len(filas):.1%} de confianza Baja (> {MAX_FRAC_BAJA:.0%})")
    return {"filas": len(filas), "usables_entrenamiento": len(ev),
            "abstenciones": len(filas) - len(ev),
            "por_clase": {c: por_clase[c] for c in dominio.CATEGORIAS}, "confianza": dict(conf),
            "confianza_por_clase": {c: dict(Counter(f["Confianza"] for f in ev if f["Función principal"] == c))
                                    for c in dominio.CATEGORIAS}}


def _cobertura(filas: list[dict], manifiesto: dict | None, carpeta_lotes: Path | None, h: _Hallazgos) -> dict:
    info: dict = {}
    ids = [f["context_id"] for f in filas]
    if manifiesto:
        info["ids_esperados"] = manifiesto["ids"]
        if len(ids) != manifiesto["ids"]:
            h.error(f"{len(ids)} filas != {manifiesto['ids']} ids en manifiesto_lotes.json")
        sha = dominio.sha_ids(sorted(ids))
        info["sha256_ids_coincide"] = sha == manifiesto["sha256_ids"]
        if not info["sha256_ids_coincide"]:
            h.error("El conjunto de ids no coincide con sha256_ids de manifiesto_lotes.json")
    if carpeta_lotes and Path(carpeta_lotes).is_dir():
        esperado: dict[str, list[str]] = {}
        for ruta in sorted(Path(carpeta_lotes).glob("lote_*.csv")):
            esperado[str(int(ruta.stem.split("_")[1]))] = [r["context_id"] for r in an.leer_csv(ruta)]
        real: dict[str, list[str]] = defaultdict(list)
        for f in filas:
            real[f["lote"]].append(f["context_id"])
        distintos = [n for n in esperado if real.get(n) != esperado[n]]
        sobran = [n for n in real if n not in esperado]
        info["lotes"] = {"esperados": len(esperado), "con_salida": len(real), "distintos": len(distintos)}
        if distintos or sobran:
            h.error(f"Lotes cuyo orden/ids no coincide con la entrada: {sorted(distintos, key=int)[:10]} "
                    f"(sin lote de entrada: {sorted(sobran)[:5]})")
    return info


def _fugas_y_calidad(filas: list[dict], f: seleccion_datos.Fuentes, papers: dict, h: _Hallazgos) -> dict:
    ids = {x["context_id"] for x in filas}
    sin_ctx = [c for c in ids if c not in f.contextos]
    if sin_ctx:
        h.error(f"Ids sin contexto en el corpus: {_muestra(sin_ctx)}")
    vetados = [c for c in ids if c in f.ids_gold or c in f.ids_excluidos]
    if vetados:
        h.error(f"Ids de gold/taller/piloto: {_muestra(vetados)}")
    anios = [c for c in ids if seleccion_datos.anio_de(c) in f.anios_excluidos]
    if anios:
        h.error(f"Ids de anios excluidos {f.anios_excluidos}: {_muestra(anios)}")
    citantes_gold = {f.contextos[c]["citing_id"] for c in f.ids_gold if c in f.contextos}
    de_gold = [c for c in ids if c in f.contextos and f.contextos[c]["citing_id"] in citantes_gold]
    if de_gold:
        h.error(f"Citas de citantes del gold: {_muestra(de_gold)}")
    sin_ta = 0
    for c in ids & f.contextos.keys():
        p = papers.get(f.contextos[c]["refid"]) or {}
        if not (p.get("title") or "").strip() or not (p.get("abstract") or "").strip():
            sin_ta += 1
    if sin_ta:
        h.aviso(f"{sin_ta} citas sin titulo/abstract del citado (la entrada A las omite)")
    return {"sin_contexto": len(sin_ctx), "vetados": len(vetados), "anios_excluidos": len(anios),
            "citantes_gold": len(de_gold), "sin_titulo_abstract": sin_ta}


def verificar(ruta: Path, manifiesto: dict | None = None, carpeta_lotes: Path | None = None,
              fuentes: seleccion_datos.Fuentes | None = None, papers: dict | None = None) -> dict:
    """Informe `{apto, errores, avisos, resumen}`. `apto` = sin errores."""
    h = _Hallazgos()
    ruta = Path(ruta)
    if not ruta.is_file():
        return {"apto": False, "errores": [f"No existe {ruta}"], "avisos": [], "resumen": {}}
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        lector = csv.DictReader(fh)
        columnas, filas = list(lector.fieldnames or []), list(lector)
    resumen: dict = {"archivo": str(ruta), "sha256": seleccion_datos.sha_archivo(ruta)}
    _estructura(filas, columnas, h)
    if columnas == an.COLUMNAS_SALIDA:
        _semantica(filas, h)
        resumen["distribucion"] = _distribucion(filas, h)
        resumen["cobertura"] = _cobertura(filas, manifiesto, carpeta_lotes, h)
        if fuentes is not None:
            resumen["fugas_y_calidad"] = _fugas_y_calidad(filas, fuentes, papers or {}, h)
    return {"apto": not h.errores, "errores": h.errores, "avisos": h.avisos, "resumen": resumen}
