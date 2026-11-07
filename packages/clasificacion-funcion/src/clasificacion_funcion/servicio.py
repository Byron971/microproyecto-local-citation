"""Casos de uso: orquesta dominio y puertos (sin torch, sin red)."""
from . import dominio

FUENTES_ETIQUETAS = ("haiku", "jurado")
ESTADO = "provisional_etiquetas_haiku_no_gold_humano"
ANIO_EVAL = "2015"


def _caso(cid: str, contextos: dict, fila: dict | None = None) -> dict:
    ctx = contextos.get(cid)
    if not isinstance(ctx, dict):
        raise ValueError(f"Contexto ausente del indice: {cid}")
    caso = {"context_id": cid, "citing_id": ctx["citing_id"], "cited_id": ctx["refid"],
            "citation_context": ctx["masked_text"]}
    if fila is not None:
        caso.update({"titulo": fila["titulo"], "abstract": fila["abstract"],
                     "etiqueta": fila["etiqueta"]})
    return caso


def _evaluables(filas: list[dict], conjunto: str) -> tuple[list[dict], list[dict]]:
    """(filas evaluables con `indice`, abstenciones [{conjunto, context_id, motivo}])."""
    evaluables, abstenciones = [], []
    for fila in filas:
        indice = dominio.normalizar_etiqueta(fila["etiqueta"])
        if indice is None:
            abstenciones.append({"conjunto": conjunto, "context_id": fila["context_id"],
                                 "motivo": dominio.motivo_abstencion(fila["etiqueta"])})
        else:
            evaluables.append({**fila, "indice": indice})
    return evaluables, abstenciones


def _unicos(filas: list[dict], nombre: str) -> None:
    ids = [f["context_id"] for f in filas]
    if len(set(ids)) != len(ids):
        raise ValueError(f"context_id duplicado en {nombre}.")


def cargar_conjuntos(fuentes, fuente_etiquetas: str = "haiku", limite: int | None = None) -> dict:
    """Construye train/val/eval_2015 (etiquetados) y Gold v2 (ciego) y verifica fugas.

    - train/val: Haiku Evaluable con el split agrupado por citante (qlora_split_v2).
    - eval_2015 (PROVISIONAL): Test Gold 2700 de 2015, Evaluable, sin exclusiones,
      con pertenencia al split `test` comprobada.
    - gold_v2: IDs ciegos (sin etiquetas)."""
    if fuente_etiquetas not in FUENTES_ETIQUETAS:
        raise ValueError(f"Fuente de etiquetas desconocida: {fuente_etiquetas!r}")
    if fuente_etiquetas == "jurado":
        raise NotImplementedError("Etiquetas del Jurado no disponibles (DVC sin descargar).")
    if limite is not None and limite < 1:
        raise ValueError("--limite debe ser positivo.")
    por_split, contextos = fuentes.indice()
    excluidos = set(fuentes.exclusiones())

    # ---- train / val
    haiku = fuentes.filas_haiku()
    _unicos(haiku, "Haiku")
    pertenece = fuentes.split_entrenamiento()
    ids_split = {n: set(pertenece[n]) for n in ("train", "val")}
    if ids_split["train"] & ids_split["val"]:
        raise ValueError("El split de entrenamiento comparte contextos entre train y val.")
    por_id = {f["context_id"]: f for f in haiku}
    if set(por_id) != ids_split["train"] | ids_split["val"]:
        raise ValueError("Las filas Haiku no coinciden con el split train/val.")
    abstenciones, conjuntos, etiquetados = [], {}, {}
    for nombre in ("train", "val"):
        filas = [por_id[c] for c in pertenece[nombre]]
        for f in filas:
            if por_split.get(f["context_id"]) != "train":
                raise ValueError(f"{f['context_id']} no pertenece al split train de ACL-200.")
        evaluables, abst = _evaluables(filas, nombre)
        abstenciones += abst
        etiquetados[nombre] = evaluables
    # ---- eval provisional
    test_gold = fuentes.filas_test_gold()
    _unicos(test_gold, "Test Gold")
    excluidos_prep = []
    candidatos = []
    for f in test_gold:
        if f["anio_citante"] != ANIO_EVAL:
            continue
        if por_split.get(f["context_id"]) != "test":
            raise ValueError(f"{f['context_id']} (2015) no pertenece al split test de ACL-200.")
        if f["context_id"] in excluidos:
            excluidos_prep.append({"conjunto": "eval_2015", "context_id": f["context_id"],
                                   "motivo": "excluido_test_gold"})
            continue
        candidatos.append(f)
    evaluables, abst = _evaluables(candidatos, "eval_2015")
    abstenciones += abst
    etiquetados["eval_2015"] = evaluables
    # ---- gold v2 ciego
    ids_gold = fuentes.ids_gold_v2()
    if len(set(ids_gold)) != len(ids_gold) or not ids_gold:
        raise ValueError("IDs del Gold v2 vacios o duplicados.")
    for cid in ids_gold:
        if por_split.get(cid) != "test":
            raise ValueError(f"{cid} (Gold v2) no pertenece al split test de ACL-200.")

    for nombre, filas in etiquetados.items():
        filas.sort(key=lambda f: f["context_id"])
        conjuntos[nombre] = [{**_caso(f["context_id"], contextos, f), "indice": f["indice"]}
                             for f in (filas[:limite] if limite else filas)]
    gold = sorted(ids_gold)
    conjuntos["gold_v2"] = [_caso(c, contextos) for c in (gold[:limite] if limite else gold)]

    # ---- fugas (el Gold v2 solapa con eval_2015 por construccion: ambos son test 2015)
    principal = dominio.verificar_fugas(
        {n: conjuntos[n] for n in ("train", "val", "eval_2015")}, excluidos)
    con_gold = dominio.verificar_fugas(
        {n: conjuntos[n] for n in ("train", "val", "gold_v2")}, excluidos)
    fugas = {"principal": principal, "gold_v2": con_gold,
             "total_fugas": principal["total_fugas"] + con_gold["total_fugas"]}
    citados = sorted({c["cited_id"] for casos in conjuntos.values() for c in casos})
    return {"conjuntos": conjuntos, "abstenciones": abstenciones, "excluidos": excluidos_prep,
            "fugas": fugas, "citados_requeridos": citados, "fuente_etiquetas": fuente_etiquetas,
            "estado": ESTADO}
