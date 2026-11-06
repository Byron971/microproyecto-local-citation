"""Limites contra el fragmentar REAL (via el unico adaptador)."""
import pytest

pytest.importorskip("auditoria_corpus")
ad = pytest.importorskip("auditoria_corpus.adaptador_proyecto_grado")

from auditoria_corpus import dominio  # noqa: E402

fr, R = ad.fragmentar, ad.REGLAS


def par(n, palabras=10, sec="S", texto=None):
    return {"numero": n, "texto": texto if texto is not None else " ".join(["w"] * palabras), "seccion": sec}


def test_reglas_son_las_del_proyecto():
    assert (R.max_palabras, R.max_parrafos, R.max_caracteres) == (300, 2, 5000)


def test_300_palabras_ok_301_falla():
    assert fr([par(0, 300)])[0]["palabras"] == 300
    with pytest.raises(ValueError) as e:
        fr([par(0, 301)])
    assert dominio.clasificar_error(e.value, [par(0, 301)], R) == "parrafo_supera_palabras"


def test_5000_caracteres_ok_5001_falla():
    t = (("x" * 24 + " ") * 200).strip() + "y"  # 200 palabras, 5000 caracteres
    assert len(t) == 5000 and len(t.split()) == 200
    assert fr([par(0, texto=t)])
    t2 = t + "y"
    assert len(t2) == 5001
    with pytest.raises(ValueError) as e:
        fr([par(0, texto=t2)])
    assert dominio.clasificar_error(e.value, [par(0, texto=t2)], R) == "parrafo_supera_caracteres"


def test_150_150_un_chunk_150_151_dos():
    assert len(fr([par(0, 150), par(1, 150)])) == 1
    assert len(fr([par(0, 150), par(1, 151)])) == 2


def test_tres_parrafos_cortos_dan_2_y_1():
    cs = fr([par(0), par(1), par(2)])
    assert [c["paragraph_indices"] for c in cs] == [[0, 1], [2]]


def test_cambio_de_seccion_corta():
    cs = fr([par(0, sec="A"), par(1, sec="B")])
    assert len(cs) == 2


def test_hueco_de_indice_corta():
    cs = fr([par(0), par(2)])
    assert [c["paragraph_indices"] for c in cs] == [[0], [2]]
    v, m = dominio.verificar_chunks(cs, [par(0), par(2)], R)
    assert v == [] and m["huecos_indice"] == 1


def test_seccion_vacia_se_acepta_y_se_cuenta():
    ps = [par(0, sec="")]
    cs = fr(ps)
    v, m = dominio.verificar_chunks(cs, ps, R)
    assert v == [] and m["chunks_sin_seccion"] == 1


def test_verificador_acepta_la_salida_real():
    ps = [par(i, 100 + i, sec="A" if i < 5 else "B") for i in range(10)]
    v, _ = dominio.verificar_chunks(fr(ps), ps, R)
    assert v == []
