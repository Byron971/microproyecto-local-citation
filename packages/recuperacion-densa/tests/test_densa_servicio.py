import json

import pytest

pytest.importorskip("recuperacion_densa")
ad = pytest.importorskip("recuperacion_densa.adaptador_proyecto_grado")

from recuperacion_densa import dominio, servicio  # noqa: E402
from recuperacion_densa.cache_embeddings import CacheDisco, CacheMemoria  # noqa: E402


class Indice:
    def __init__(self, by_context, contexts):
        self.by_context, self.contexts = by_context, contexts


def doc(pid, parrafos):
    return {"paper_id": pid, "title": pid, "pdf_parse": {"body_text": [
        {"text": t, "section": s} for t, s in parrafos]}}


class Falso:
    """Codificador determinista (bolsa de palabras hash) que cuenta llamadas."""
    model_id, revision = "falso", "r0"

    def __init__(self):
        self.llamadas: list[list[str]] = []

    def encode(self, textos):
        self.llamadas.append(list(textos))
        out = []
        for t in textos:
            v = [0.01] * 16
            for w in t.lower().split():
                v[sum(map(ord, w)) % 16] += 1.0
            out.append(tuple(v))
        return out

    def info(self):
        return {"dispositivo": "falso"}


@pytest.fixture
def entorno(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    w = lambda n, d: (cache / f"{n}.json").write_text(json.dumps(d), encoding="utf-8")  # noqa: E731
    w("A1", doc("A1", [("neural parsing models", "Intro"), ("graph methods for syntax", "Methods"),
                       ("evaluation on treebank data", "Results"), ("related work on parsing", "Related Work")]))
    w("B1", doc("B1", [("speech corpus annotation", "Intro"), ("acoustic features", "Methods")]))
    w("BAD", doc("OTRO", [("a b", "S")]))
    contexts, by, papers = {}, {}, {}
    casos = [("c1", "train", "A1", "we use parsing TARGETCIT models"),
             ("c2", "train", "A1", "TARGETCIT treebank evaluation"),
             ("c3", "train", "A1", "syntax graph TARGETCIT"),
             ("c4", "train", "B1", "acoustic TARGETCIT speech"),
             ("c5", "val", "A1", "TARGETCIT"), ("c6", "train", "B1", "TARGETCIT zzz"),
             ("c7", "train", "BAD", "TARGETCIT"), ("c8", "train", "SIN", "TARGETCIT"),
             ("c9", "train", "A1", "excluido TARGETCIT")]
    for cid, split, cited, txt in casos:
        contexts[cid] = {"refid": cited, "citing_id": "C-" + cid, "masked_text": txt}
        by[cid] = split
        papers[cited] = {"title": "T " + cited, "abstract": ""}
    return Indice(by, contexts), papers, cache


def casos_de(entorno, **kw):
    ind, papers, cache = entorno
    return servicio.construir_casos(ind, papers, cache, ad.integrar, ad.fragmentar,
                                    kw.pop("excluidos", {"c9"}), **kw)


def correr(casos, enc=None, cache=None, **kw):
    return servicio.evaluar(casos, enc or Falso(), ad.lexico, cache, _reloj(),
                            ad.perfil_seccion, **kw)


def _reloj():
    t = [0.0]

    def r():
        t[0] += 0.001
        return t[0]
    return r


# ---------------------------------------------------------------- construir_casos
def test_construir_casos_multicontexto_solo_train(entorno):
    casos, meta = casos_de(entorno)
    assert [c["context_id"] for c in casos] == ["c1", "c2", "c3", "c4", "c6"]
    assert meta["tipo"] == "muestra_desarrollo_train_no_gold"
    assert meta["variante"] == "multicontexto_por_citado"
    assert meta["total"] == 5 and meta["articulos"] == 2
    assert meta["motivos_no_seleccion"] == {"ValueError": 1, "excluido": 1, "sin_cache_citado": 1}
    # mismos chunks (identicos) para los contextos de un mismo citado
    assert casos[0]["chunks"] == casos[1]["chunks"] == casos[2]["chunks"]
    assert all(len(c["sha256_ocl_citado"]) == 64 for c in casos)


def test_construir_casos_memoiza_por_citado(entorno):
    ind, papers, cache = entorno
    n = []

    def frag(p):
        n.append(1)
        return ad.fragmentar(p)

    servicio.construir_casos(ind, papers, cache, ad.integrar, frag, {"c9"})
    assert len(n) == 2  # A1 y B1, no uno por contexto


def test_construir_casos_limite(entorno):
    casos, _ = casos_de(entorno, limite=2)
    assert len(casos) == 2
    with pytest.raises(ValueError):
        casos_de(entorno, limite=0)


def test_leer_casos_acepta_esquema(entorno, tmp_path):
    casos, meta = casos_de(entorno)
    p = tmp_path / "casos.json"
    p.write_text(json.dumps(servicio.exportar_casos(casos, meta)), encoding="utf-8")
    doc_, _ = ad.leer_casos_s22(p)
    assert len(doc_["casos"]) == 5


# ---------------------------------------------------------------- evaluar
def test_cada_articulo_se_codifica_una_vez(entorno):
    casos, _ = casos_de(entorno)
    enc = Falso()
    correr(casos, enc, CacheMemoria())
    por_art = [ll for ll in enc.llamadas if len(ll) > 1]
    assert len(por_art) == 2  # A1 (4 chunks) y B1 (2): una llamada por articulo
    assert sorted(len(x) for x in por_art) == [2, 4]


def test_acierto_de_cache_no_llama_al_codificador(entorno, tmp_path):
    casos, _ = casos_de(entorno)
    cache = CacheDisco(tmp_path / "emb")
    correr(casos, Falso(), cache)
    enc2 = Falso()
    ev = correr(casos, enc2, cache)
    assert all(len(ll) == 1 for ll in enc2.llamadas)  # solo warm-up y consultas
    assert ev.latencias["embedding_articulo"]["chunks_en_cache"] == 6


def test_clave_depende_de_parametros(entorno):
    casos, _ = casos_de(entorno)
    cache = CacheMemoria()
    correr(casos, Falso(), cache, max_length=512)
    enc = Falso()
    correr(casos, enc, cache, max_length=256)
    assert any(len(ll) > 1 for ll in enc.llamadas)


def test_sin_gold_no_hay_recall(entorno):
    casos, _ = casos_de(entorno)
    ev = correr(casos)
    txt = servicio.resumen_json(ev).lower()
    assert "recall" not in txt and "mrr" not in txt and "hit_3" not in txt and "gold" not in ev.resumen
    assert ev.resumen["metricas_relevancia"].startswith("no calculadas")


def test_resumen_determinista_y_sin_tiempos(entorno, tmp_path):
    casos, _ = casos_de(entorno)
    a = servicio.resumen_json(correr(casos, cache=CacheMemoria()))
    b = servicio.resumen_json(correr(casos, cache=CacheDisco(tmp_path / "e")))
    assert a == b
    assert "warmup" not in a and "latencia" not in a


def test_resultados_integros_y_comparacion(entorno):
    casos, _ = casos_de(entorno)
    ev = correr(casos)
    assert all(len(v) <= 3 for v in ev.denso.values())
    assert ev.bm25["c6"] == [] and len(ev.denso["c6"]) == 2  # BM25 se abstiene
    fila6 = next(f for f in ev.comparacion if f["context_id"] == "c6")
    assert fila6["abstencion_bm25"] and fila6["interseccion"] == 0
    assert len(ev.comparacion) == 5
    assert ev.resumen["comparacion"]["micro"]["n"] == 5
    assert ev.resumen["comparacion"]["macro"]["n"] == 2
    assert dominio.verificar_integridad(casos, ev.denso, "d") == []
    assert all("texto" not in r for v in ev.bm25.values() for r in v)
    assert len(ev.ejemplos) == 5 and all(len(x["contexto"]) <= 240 for x in ev.ejemplos)


def test_integridad_violada_no_devuelve_nada(entorno):
    casos, _ = casos_de(entorno)

    def malo(ctx, chunks):
        return [{"chunk_id": "inexistente", "puntaje_bm25": 1.0, "paragraph_indices": [0]}]

    with pytest.raises(ValueError, match="Integridad"):
        servicio.evaluar(casos, Falso(), malo, None, _reloj(), ad.perfil_seccion)


def test_rechaza_entradas_no_train(entorno):
    casos, _ = casos_de(entorno)
    casos[0]["split"] = "val"
    with pytest.raises(ValueError):
        correr(casos)


def test_ejemplos_estratificados_reproducibles():
    filas = [{"context_id": f"c{i}", "interseccion": i % 4} for i in range(40)]
    a = servicio.seleccionar_ejemplos(filas, 8, 102)
    assert a == servicio.seleccionar_ejemplos(filas, 8, 102)
    assert len({int(c[1:]) % 4 for c in a}) == 4
    assert a != servicio.seleccionar_ejemplos(filas, 8, 7)


# ---------------------------------------------------------------- gold: equivalencia con top3_humano
def test_equivalencia_con_evaluar_calibracion(entorno, tmp_path):
    from proyecto_de_grado.src.evaluation import top3_humano as th

    casos, meta = casos_de(entorno)
    origen = tmp_path / "casos.json"
    origen.write_text(json.dumps(servicio.exportar_casos(casos, meta)), encoding="utf-8")
    hojas = tmp_path / "hojas"
    th.preparar_hojas(origen, hojas)
    import csv
    for nombre in ("anotador_a.csv", "anotador_b.csv", "adjudicacion_plantilla.csv"):
        ruta = hojas / nombre
        with ruta.open(encoding="utf-8-sig", newline="") as fh:
            filas = list(csv.DictReader(fh))
        for f in filas:
            rel = f["chunk_id"].endswith(("p00000", "p00001")) or "00000" in f["chunk_id"]
            f["relevante_0_1"] = "1" if rel else "0"
        with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=th.COLUMNS)
            w.writeheader()
            w.writerows(filas)
    ref = th.evaluar_calibracion(origen, hojas)
    gold = ad.cargar_gold_calibracion(origen, hojas)
    ev = servicio.evaluar(casos, Falso(), ad.lexico, None, _reloj(), ad.perfil_seccion,
                          gold=gold, puntuar=ad.puntuar)
    g = ev.resumen["gold"]["bm25"]
    assert (g["hit_3"], g["recall_3"], g["mrr_3"]) == (ref["hit_3"], ref["recall_3"], ref["mrr_3"])
    assert g["casos_elegibles"] == ref["casos_elegibles"] and ref["casos_elegibles"] > 0
    assert ev.resumen["gold"]["denso"]["estado"] == "calibracion_train_no_gold"


def test_gold_con_fuente_alterada_falla(entorno, tmp_path):
    from proyecto_de_grado.src.evaluation import top3_humano as th

    casos, meta = casos_de(entorno)
    origen = tmp_path / "casos.json"
    origen.write_text(json.dumps(servicio.exportar_casos(casos, meta)), encoding="utf-8")
    th.preparar_hojas(origen, tmp_path / "h")
    origen.write_text(origen.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(th.ProtocoloError):
        ad.cargar_gold_calibracion(origen, tmp_path / "h")
