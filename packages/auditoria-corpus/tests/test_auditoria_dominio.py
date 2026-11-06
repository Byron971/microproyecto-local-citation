import pytest

pytest.importorskip("auditoria_corpus")

from auditoria_corpus import dominio  # noqa: E402
from auditoria_corpus.reglas import ReglasChunk  # noqa: E402

R = ReglasChunk(300, 2, 5000)


def par(n, texto="uno dos", sec="Intro"):
    return {"numero": n, "texto": texto, "seccion": sec}


def chunk(idx, parrafos, sec="Intro"):
    t = "\n".join(p["texto"] for p in parrafos if p["numero"] in idx)
    return {"chunk_id": f"p{idx[0]:05d}-p{idx[-1]:05d}", "texto": t, "seccion": sec,
            "paragraph_indices": idx, "palabras": len(t.split())}


def test_chunks_validos_sin_violaciones():
    ps = [par(0), par(1), par(2)]
    v, m = dominio.verificar_chunks([chunk([0, 1], ps), chunk([2], ps)], ps, R)
    assert v == [] and m["chunks"] == 2 and m["chunks_2_parrafos"] == 1


def test_parrafo_perdido_y_duplicado():
    ps = [par(0), par(1), par(2)]
    v, _ = dominio.verificar_chunks([chunk([0], ps), chunk([2], ps)], ps, R)
    assert any("perdidos=[1]" in x for x in v)
    v, _ = dominio.verificar_chunks([chunk([0, 1], ps), chunk([1, 2], ps)], ps, R)
    assert any("duplicados=[1]" in x for x in v)


def test_texto_alterado_y_chunk_id_incoherente():
    ps = [par(0), par(1)]
    c = chunk([0, 1], ps)
    c["texto"] = "otro"
    c["chunk_id"] = "p00000-p00009"
    v, _ = dominio.verificar_chunks([c], ps, R)
    assert any("no reconstruye" in x for x in v) and any("incoherente con" in x for x in v)


def test_mezcla_de_secciones_y_exceso_de_palabras():
    ps = [par(0, sec="A"), par(1, sec="B")]
    v, _ = dominio.verificar_chunks([chunk([0, 1], ps, "A")], ps, R)
    assert any("mezcla secciones" in x for x in v)
    grande = [par(0, "w " * 301)]
    v, _ = dominio.verificar_chunks([chunk([0], grande)], grande, R)
    assert any("301 palabras" in x for x in v)


def test_huecos_y_sin_seccion():
    ps = [par(0, sec=""), par(2, sec="")]
    v, m = dominio.verificar_chunks([chunk([0], ps, ""), chunk([2], ps, "")], ps, R)
    assert v == [] and m["huecos_indice"] == 1 and m["chunks_sin_seccion"] == 2


@pytest.mark.parametrize("exc,causa", [
    (FileNotFoundError("No encontramos ACL OCL para X."), "citado_no_descargado"),
    (ValueError("ID incorrecto: esperado A, recibido B."), "id_incorrecto"),
    (ValueError("El artículo X no existe en ACL-200."), "citado_no_en_papers"),
    (ValueError("El contexto c no tiene una cita objetivo única."), "targetcit_no_unico"),
    (ValueError("El artículo X no contiene párrafos."), "sin_parrafos"),
    (ValueError("Indice de parrafo invalido o duplicado."), "indice_invalido"),
    (KeyError("x"), "otro_KeyError"),
])
def test_clasificar_error(exc, causa):
    assert dominio.clasificar_error(exc) == causa


def test_clasificar_json_invalido_y_parrafo_largo():
    import json
    assert dominio.clasificar_error(json.JSONDecodeError("m", "d", 0)) == "archivo_invalido"
    exc = ValueError("Parrafo demasiado largo: requiere division por oraciones.")
    assert dominio.clasificar_error(exc, [par(0, "w " * 301)], R) == "parrafo_supera_palabras"
    assert dominio.clasificar_error(exc, [par(0, "x" * 5001)], R) == "parrafo_supera_caracteres"


def test_huella_estable_y_sensible():
    ps = [par(0)]
    a = [chunk([0], ps)]
    assert dominio.huella_chunks(a) == dominio.huella_chunks([dict(a[0])])
    b = [dict(a[0], texto="x")]
    assert dominio.huella_chunks(a) != dominio.huella_chunks(b)


@pytest.mark.parametrize("nombre,perfil", [
    ("1 Introduction", "introduction"), ("Related Work", "related_work"),
    ("Experimental Results", "results"), ("Conclusions", "conclusion"),
    ("Our Approach", "method"), ("Appendix", "otra"), ("", "vacia"), (None, "vacia"),
])
def test_perfil_seccion(nombre, perfil):
    assert dominio.perfil_seccion(nombre) == perfil


def test_resumir_colisiones_globales_de_chunk_id():
    def cit(i):
        ps = [par(0)]
        ch = [chunk([0], ps)]
        v, m = dominio.verificar_chunks(ch, ps, R)
        return {"cited_id": i, "estado": "ok", "causa": "", "chunks": ch, "violaciones": v,
                "metricas": m, "reproducible": True, "perfiles": ["introduction"]}
    filas = [{"split": "train", "cited_id": "A", "estado": "ok", "causa": ""},
             {"split": "val", "cited_id": "B", "estado": "ok", "causa": ""},
             {"split": "test", "cited_id": "C", "estado": "error", "causa": "citado_404"}]
    citados = [cit("A"), cit("B"),
               {"cited_id": "C", "estado": "error", "causa": "citado_404", "chunks": [],
                "violaciones": [], "metricas": {}, "reproducible": True, "perfiles": []}]
    r = dominio.resumir(filas, citados)
    assert r["ids"]["chunk_id_en_varios_articulos"] == 1
    assert r["ids"]["pares_citado_chunk"] == r["ids"]["pares_citado_chunk_unicos"] == 2
    assert r["cobertura_por_split"]["train"]["cobertura_contextos_pct"] == 100.0
    assert r["errores_por_causa_citados"] == {"citado_404": 1}


def test_muestras_solo_train_sin_excluidos_y_determinista():
    cands = [{"context_id": f"c{i}", "split": s, "cited_id": f"P{i}"}
             for i, s in enumerate(["train"] * 30 + ["val"] * 5 + ["test"] * 5)]
    ex = {"c0", "c1"}
    a = dominio.seleccionar_muestras(cands, ex, 10, 101)
    assert a == dominio.seleccionar_muestras(list(reversed(cands)), ex, 10, 101)
    assert len(a) == 10 and all(c["split"] == "train" and c["context_id"] not in ex for c in a)
