import pytest

from clasificacion_funcion import dominio, servicio
from recuperacion_densa.cache_embeddings import CacheMemoria

from chunks_falsos import (CodificadorFalso, crear_integrar, fragmentar_falso, parrafos,
                           preparar_cache)
from fuentes_falsas import FuentesFalsas

CITADOS = ["A", "B", "C", "D", "E", "F", "G", "H"]
PAPERS = {c: {"title": f"Titulo {c}", "abstract": f"Resumen {c}"} for c in CITADOS}


def top3_filas(casos_por_conjunto):
    """Top-3 como lo lee `agrupar_top3` desde top3_*.csv."""
    salida = {}
    for n, casos in casos_por_conjunto.items():
        res = servicio.recuperar_top3(casos, CodificadorFalso(), CacheMemoria())["top3"] if casos else {}
        filas = [{"context_id": ctx, "posicion": str(r["posicion"]), "cited_id": r["cited_id"],
                  "chunk_id": r["chunk_id"], "seccion": r["seccion"],
                  "perfil_seccion": "method"} for ctx, top in res.items() for r in top]
        salida[n] = servicio.agrupar_top3(filas)
    return salida


def armar(tmp_path, n_parrafos=4, ausentes=(), papers=PAPERS, mutar_top3=None):
    f = FuentesFalsas()
    conjuntos = servicio.cargar_conjuntos(f)["conjuntos"]
    cache = tmp_path / "ocl"
    preparar_cache(cache, CITADOS, ausentes=ausentes)
    integrar = crear_integrar({c: parrafos(c, n=n_parrafos) for c in CITADOS})
    casos, excl = servicio.construir_casos_split(conjuntos, f.ctx, {c: {} for c in CITADOS},
                                                 cache, integrar, fragmentar_falso)
    top3 = top3_filas(casos)
    if mutar_top3:
        mutar_top3(top3)
    return servicio.interseccion(conjuntos, casos, excl, top3, papers), conjuntos


def ids(res, n):
    return [e["context_id"] for e in res["entradas"][n]]


def test_interseccion_basica(tmp_path):
    res, _ = armar(tmp_path)
    assert ids(res, "train") == ["t1", "t2", "t4"] and ids(res, "eval_2015") == ["e1", "e3"]
    e = res["entradas"]["eval_2015"][0]
    assert e["titulo"] == "Titulo A" and e["abstract"] == "Resumen A" and e["indice"] == 2
    assert [c["chunk_id"] for c in e["top3"]] and all(c["texto"] and c["perfil"] for c in e["top3"])
    assert len(e["top3"]) == 3


def test_a_y_b_usan_exactamente_los_mismos_ids_y_construyen(tmp_path):
    res, _ = armar(tmp_path)
    for n, entradas in res["entradas"].items():
        for e in entradas:
            for tipo in ("A", "B", "B_sin_seccion"):
                assert dominio.construir_segmentos(e, tipo)
    assert servicio.huella_entradas(res["entradas"]["train"], "A") != \
        servicio.huella_entradas(res["entradas"]["train"], "B")
    assert servicio.huella_entradas(res["entradas"]["train"], "B") == \
        servicio.huella_entradas(list(reversed(res["entradas"]["train"])), "B")


def test_excluidos_por_motivo_y_clase(tmp_path):
    res, _ = armar(tmp_path, ausentes=("G",))
    excl = {(e["conjunto"], e["context_id"]): e for e in res["excluidos"]}
    assert excl[("gold_v2", "e5")]["motivo"] == "sin_descargar" and excl[("gold_v2", "e5")]["etiqueta"] == ""
    resumen = res["resumen"]["gold_v2"]
    assert resumen["candidatos"] == 3 and resumen["interseccion"] == 2
    assert resumen["cobertura_pct"] == pytest.approx(66.67)
    assert resumen["excluidos_por_motivo"] == {"sin_descargar": 1}


def test_excluidos_etiquetados_declaran_clase(tmp_path):
    res, _ = armar(tmp_path, ausentes=("A",))
    e = {(x["conjunto"], x["context_id"]): x for x in res["excluidos"]}[("train", "t1")]
    assert e["etiqueta"] == "Background"
    r = res["resumen"]["train"]
    assert r["por_clase_candidatos"]["Background"] == 1 and r["por_clase_interseccion"]["Background"] == 0
    assert r["por_clase_excluidos"]["Background"] == 1
    assert sum(r["por_clase_candidatos"].values()) == r["candidatos"] == 3


def test_menos_de_3_chunks_se_excluye(tmp_path):
    res, _ = armar(tmp_path, n_parrafos=2)
    assert ids(res, "train") == [] and ids(res, "eval_2015") == []
    assert {e["motivo"] for e in res["excluidos"]} == {"menos_de_3_chunks"}


def test_sin_titulo_o_abstract(tmp_path):
    papers = {**PAPERS, "A": {"title": "T", "abstract": "  "}}
    res, _ = armar(tmp_path, papers=papers)
    motivos = {(e["conjunto"], e["context_id"]): e["motivo"] for e in res["excluidos"]}
    assert motivos[("train", "t1")] == "sin_titulo_abstract" and "t2" in ids(res, "train")


def test_sin_top3_y_chunk_ajeno(tmp_path):
    def quitar(top3):
        top3["train"].pop("t1")
        top3["train"]["t2"][0]["chunk_id"] = "p99999"
    res, _ = armar(tmp_path, mutar_top3=quitar)
    motivos = {e["context_id"]: e["motivo"] for e in res["excluidos"] if e["conjunto"] == "train"}
    assert motivos == {"t1": "sin_top3", "t2": "chunk_ajeno"}


def test_contexto_sin_chunks_ni_motivo_es_error(tmp_path):
    f = FuentesFalsas()
    conjuntos = servicio.cargar_conjuntos(f)["conjuntos"]
    with pytest.raises(ValueError, match="sin chunks ni motivo"):
        servicio.interseccion(conjuntos, {n: [] for n in conjuntos}, [], {}, PAPERS)


def test_agrupar_top3_valida_posiciones():
    fila = lambda p: {"context_id": "x", "posicion": str(p), "chunk_id": "c", "cited_id": "A"}  # noqa: E731
    assert [r["posicion"] for r in servicio.agrupar_top3([fila(2), fila(1)])["x"]] == [1, 2]
    with pytest.raises(ValueError):
        servicio.agrupar_top3([fila(1), fila(3)])
