"""Pruebas de regresion para la integracion optativa S2.6."""
import json

import pytest

from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar
from proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 import _analizar_citado
from proyecto_de_grado.src.data.segmentacion_oraciones_s2_6 import (
    dividir_parrafo_oraciones, _posibles_oraciones,
)


def _p(texto, numero=16, seccion="Methods"):
    return {"numero": numero, "seccion": seccion, "texto": texto}


def _parrafo_largo():
    # Dos oraciones de 170 palabras: juntas exceden 300.
    return ("Our proposed approach " + "feature " * 167 + "is effective. "
            + "The second approach " + "method " * 167 + "is robust.")


def test_primero_y_segundo_segmento_respeta_oraciones_offsets_y_tamanos():
    original = _parrafo_largo()
    chunks = fragmentar([_p(original)], dividir_parrafos_largos=True, segmentacion_oraciones=True)
    assert len(chunks) == 2
    assert [x["chunk_id"] for x in chunks] == ["p00016-s000", "p00016-s001"]
    assert "".join(x["texto"] for x in chunks) == original
    assert chunks[0]["texto"].rstrip().endswith("effective.")
    assert chunks[1]["texto"].startswith("The second")
    assert all(c["fragmentacion"] == "division_oraciones_v1" for c in chunks)
    assert all(c["seccion"] == "Methods" for c in chunks)
    assert all(c["palabras"] <= 300 and len(c["texto"]) <= 5000 for c in chunks)
    a, b = [x["paragraph_char_spans"][0] for x in chunks]
    assert a["start"] == 0 and a["end"] == b["start"] and b["end"] == len(original)


def test_s2_4_legacy_permanece_sin_modificar():
    texto = " ".join(f"word{i}" for i in range(488))
    legacy = fragmentar([_p(texto)], dividir_parrafos_largos=True)
    assert len(legacy) == 2
    assert [c["fragmentacion"] for c in legacy] == ["division_conservadora_palabras_v1"] * 2
    assert "".join(c["texto"] for c in legacy) == texto
    with pytest.raises(ValueError, match="oracion_extensa_sin_corte_seguro"):
        fragmentar([_p(texto)], dividir_parrafos_largos=True, segmentacion_oraciones=True)


def test_modo_nuevo_requiere_activar_division():
    with pytest.raises(ValueError, match="requiere"):
        fragmentar([_p("Short.")], segmentacion_oraciones=True)


def test_abreviaturas_decimales_y_parentesis():
    texto = ('Dr. Smith used Fig. 3 and et al. (2020) at 81.19% accuracy. '
             'The method worked (see results). The paper is cited.')
    assert len(_posibles_oraciones(texto)) == 3


def test_paso_de_analisis_de_fuente_ocl_a_modo_nuevo(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    pid = "P03-1054"
    doc = {"paper_id": pid, "pdf_parse": {"body_text": [
        {"text": "Introduction short.", "section": "Introduction"},
        {"text": _parrafo_largo(), "section": "Methods"},
    ]}}
    (cache / f"{pid}.json").write_text(json.dumps(doc), encoding="utf-8")
    info = _analizar_citado(pid, cache, {pid: {"title": "A Title"}}, segmentacion_oraciones=True)
    assert info["estado"] == "utilizable"
    assert len(info["chunks"]) == 3
    assert all(x["seccion"] in ("Introduction", "Methods") for x in info["chunks"])
    assert sum(x.get("fragmentacion") == "division_oraciones_v1" for x in info["chunks"]) == 2


def test_oracion_indivisible_se_excluye_sin_falsificar_chunks(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    pid = "P03-1054"
    doc = {"paper_id": pid, "pdf_parse": {"body_text": [
        {"text": " ".join(["token"] * 350), "section": "Methods"},
    ]}}
    (cache / f"{pid}.json").write_text(json.dumps(doc), encoding="utf-8")
    info = _analizar_citado(pid, cache, {pid: {"title": "Title"}}, segmentacion_oraciones=True)
    assert info["estado"] == "fragmentacion_invalida"
    legacy = _analizar_citado(pid, cache, {pid: {"title": "Title"}})
    assert legacy["estado"] == "utilizable"


def test_conservacion_de_puntuacion_y_blancos_en_dos_oraciones():
    texto = ("Sentence one is here.   " + "Sentence two is here.\n")
    parts = dividir_parrafo_oraciones(_p(texto), 5, 5000)
    assert "".join(x["texto"] for x in parts) == texto
    assert parts[0]["char_fin"] == parts[1]["char_inicio"]
