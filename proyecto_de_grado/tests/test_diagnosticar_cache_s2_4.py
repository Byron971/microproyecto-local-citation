"""S2.4: diagnostico preciso de cobertura sin redes, Gold o fuga de test."""
import json

from proyecto_de_grado.src.data.diagnosticar_cache_s2_4 import (
    caracterizar_parrafos,
    diagnosticar,
)
from proyecto_de_grado.src.data.validar_splits import build_split_index


def _datos(tmp_path):
    cache = tmp_path / "ocl"
    cache.mkdir()
    casos = [
        ("train", "T1", "C1", "intro TARGETCIT uno"),
        ("train", "T2", "C2", "metodo TARGETCIT dos"),
        ("train", "T3", "C3", "datos TARGETCIT tres"),
        ("train", "T4", "C4", "prueba TARGETCIT cuatro"),
        ("train", "T5", "C1", "exclusion TARGETCIT cinco"),
        ("train", "T6", "C1", "duplicado TARGETCIT comun"),
        ("val", "V1", "C1", "duplicado TARGETCIT comun"),
        ("test", "X1", "C1", "independiente TARGETCIT ocho"),
    ]
    contextos, splits, papers = {}, {"train": [], "val": [], "test": []}, {}
    for split, citante, citado, texto in casos:
        id = f"{citante}_{citado}_0"
        contextos[id] = {"citing_id": citante, "refid": citado, "masked_text": texto}
        splits[split].append({"context_id": id, "positive_ids": [citado]})
        papers[citado] = {"title": f"Paper {citado}", "abstract": ""}
    (cache / "C1.json").write_text(json.dumps({
        "paper_id": "C1", "pdf_parse": {"body_text": [
            {"text": "Short introductory paragraph.", "section": "Intro"}
        ]}
    }), encoding="utf-8")
    (cache / "C2.json").write_text(json.dumps({
        "paper_id": "C2", "pdf_parse": {"body_text": [
            {"text": "x " * 301, "section": "Methods"}
        ]}
    }), encoding="utf-8")
    (cache / "C4.404").write_text("", encoding="utf-8")
    return build_split_index(contextos, splits), papers, cache


def test_diagnostico_separa_documentos_de_contextos(tmp_path):
    index, papers, cache = _datos(tmp_path)
    resultado = diagnosticar(index, papers, cache, {"T5_C1_0"}, top=12)
    assert resultado["contextos_train_originales"] == 6
    assert resultado["exclusiones"] == {
        "duplicado_exacto_cruzado": 1,
        "exclusion_reservada": 1,
    }
    assert resultado["contextos_train_no_excluidos"] == 4
    assert resultado["documentos_citados_distintos_train"] == 4
    assert resultado["estado_documentos_citados"] == {
        "fragmentacion_invalida": 1, "no_descargado": 1,
        "no_disponible_404": 1, "utilizable": 1,
    }
    assert resultado["estado_contextos_train"] == resultado["estado_documentos_citados"]


def test_no_recomienda_descargar_404_ni_exporta_val_test(tmp_path):
    index, papers, cache = _datos(tmp_path)
    resultado = diagnosticar(index, papers, cache, {"T5_C1_0"})
    assert resultado["prioridad_descarga_train"] == [
        {"cited_id": "C3", "contextos_train_potenciales": 1}
    ]
    serialized = json.dumps(resultado)
    assert "V1_C1" not in serialized
    assert "X1_C1" not in serialized
    assert "duplicado TARGETCIT comun" not in serialized
    assert "x x x" not in serialized


def test_diagnostica_rechazo_por_largo_sin_volcar_texto(tmp_path):
    index, papers, cache = _datos(tmp_path)
    info = caracterizar_parrafos("C2", cache)
    assert info["estado_diagnostico"] == "analizado"
    assert info["parrafos_demasiado_largos"] == 1
    assert info["detalle_excesos"] == [{
        "indice_parrafo": 0,
        "palabras": 301,
        "caracteres": 601,
        "supera_300_palabras": True,
        "supera_5000_caracteres": False,
    }]
    assert "x x x" not in json.dumps(info)


def test_diagnostico_identifica_cache_corrupta(tmp_path):
    index, papers, cache = _datos(tmp_path)
    (cache / "C2.json").write_text("{broken", encoding="utf-8")
    resultado = diagnosticar(index, papers, cache, set())
    assert resultado["estado_documentos_citados"]["archivo_ocl_invalido"] == 1
    c2 = next(x for x in resultado["inspeccion_documentos_en_cache"] if x["cited_id"] == "C2")
    assert c2["estado_diagnostico"] == "json_ilegible"


def test_limite_de_top_controlado(tmp_path):
    index, papers, cache = _datos(tmp_path)
    import pytest
    with pytest.raises(ValueError, match="--top"):
        diagnosticar(index, papers, cache, set(), top=0)
    with pytest.raises(ValueError, match="--top"):
        diagnosticar(index, papers, cache, set(), top=101)
