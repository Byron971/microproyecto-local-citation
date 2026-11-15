import csv
import json

import pytest

pytest.importorskip("auditoria_corpus")
ad = pytest.importorskip("auditoria_corpus.adaptador_proyecto_grado")

from auditoria_corpus import cli  # noqa: E402
from auditoria_corpus.servicio import auditar_corpus  # noqa: E402


class Indice:
    def __init__(self, by_context, contexts):
        self.by_context, self.contexts = by_context, contexts


def doc(pid, parrafos):
    return {"paper_id": pid, "title": pid, "pdf_parse": {"body_text": [
        {"text": t, "section": s} for t, s in parrafos]}}


@pytest.fixture
def entorno(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    escr = lambda n, d: (cache / f"{n}.json").write_text(json.dumps(d), encoding="utf-8")  # noqa: E731
    escr("OK1", doc("OK1", [("a b c", "Intro"), ("d e", "Intro"), ("f", "Methods")]))
    escr("OK2", doc("OK2", [("x y", "Intro")]))
    escr("BADID", doc("OTRO", [("a", "S")]))
    escr("LARGO", doc("LARGO", [("w " * 301, "S")]))
    escr("VACIO", doc("VACIO", [("  ", "S")]))
    (cache / "CORRUPTO.json").write_text("{no es json", encoding="utf-8")
    (cache / "NO404.404").write_text("", encoding="utf-8")
    contexts, by, papers = {}, {}, {}
    casos = [("c_ok1", "train", "OK1", "x TARGETCIT y"), ("c_ok2", "train", "OK2", "TARGETCIT"),
             ("c_val", "val", "OK1", "TARGETCIT"), ("c_test", "test", "OK2", "TARGETCIT"),
             ("c_badid", "train", "BADID", "TARGETCIT"), ("c_largo", "train", "LARGO", "TARGETCIT"),
             ("c_vacio", "train", "VACIO", "TARGETCIT"), ("c_corr", "train", "CORRUPTO", "TARGETCIT"),
             ("c_404", "train", "NO404", "TARGETCIT"), ("c_sin", "train", "SINCACHE", "TARGETCIT"),
             ("c_dup", "train", "OK2", "TARGETCIT TARGETCIT"), ("c_nopapers", "train", "FANTASMA", "TARGETCIT")]
    for cid, split, cited, texto in casos:
        contexts[cid] = {"refid": cited, "citing_id": "C-" + cid, "masked_text": texto}
        by[cid] = split
        if cited != "FANTASMA":
            papers[cited] = {"title": "T " + cited, "abstract": ""}
    # FANTASMA tiene cache pero no esta en papers
    (cache / "FANTASMA.json").write_text(json.dumps(doc("FANTASMA", [("a", "S")])), encoding="utf-8")
    return Indice(by, contexts), papers, cache


def correr(entorno, excluidos=frozenset()):
    ind, papers, cache = entorno
    return auditar_corpus(ind, papers, cache, ad.integrar, ad.fragmentar, ad.REGLAS, set(excluidos), 20, 101)


def test_causas_de_error(entorno):
    a = correr(entorno)
    por_ctx = {f["context_id"]: f["causa"] or "ok" for f in a.filas}
    assert por_ctx == {
        "c_ok1": "ok", "c_ok2": "ok", "c_val": "ok", "c_test": "ok",
        "c_badid": "id_incorrecto", "c_largo": "parrafo_supera_palabras", "c_vacio": "sin_parrafos",
        "c_corr": "archivo_invalido", "c_404": "citado_404", "c_sin": "citado_no_descargado",
        "c_dup": "targetcit_no_unico", "c_nopapers": "citado_no_en_papers",
    }


def test_resumen_sin_violaciones_y_reproducible(entorno):
    r = correr(entorno).resumen
    assert r["violaciones_total"] == 0 and r["reproducibilidad"]["huellas_distintas"] == 0
    assert r["cobertura_por_split"]["val"]["cobertura_contextos_pct"] == 100.0
    assert "CACHE LOCAL" in r["alcance"]


def test_salidas_identicas_byte_a_byte(entorno, tmp_path):
    ex = {"c_ok2"}
    cli.escribir(correr(entorno, ex), tmp_path / "a")
    cli.escribir(correr(entorno, ex), tmp_path / "b")
    for nombre in ("resumen.json", "auditoria_chunks.csv", "muestras_train.csv"):
        assert (tmp_path / "a" / nombre).read_bytes() == (tmp_path / "b" / nombre).read_bytes()


def test_muestras_solo_train_y_sin_excluidos(entorno):
    a = correr(entorno, {"c_ok2"})
    ids = {m["context_id"] for m in a.muestras}
    assert ids == {"c_ok1"}  # c_val/c_test no son train; c_ok2 excluido
    assert a.muestras[0]["verificado_por"] == ""


def test_csv_de_chunks_no_contiene_texto(entorno, tmp_path):
    cli.escribir(correr(entorno), tmp_path)
    with (tmp_path / "auditoria_chunks.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert filas and "texto" not in filas[0]


def test_error_de_fragmentacion_se_propaga_a_todos_los_contextos_del_citado(entorno):
    ind, papers, cache = entorno
    ind.contexts["c_largo2"] = {"refid": "LARGO", "citing_id": "C2", "masked_text": "TARGETCIT"}
    ind.by_context["c_largo2"] = "train"
    a = correr((ind, papers, cache))
    fila = next(f for f in a.filas if f["context_id"] == "c_largo2")
    assert (fila["estado"], fila["causa"]) == ("error", "parrafo_supera_palabras")
