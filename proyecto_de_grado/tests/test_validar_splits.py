"""Pruebas unitarias G0.6 de splits y coherencia con ACL-200."""
import json
from types import SimpleNamespace

import pytest

from proyecto_de_grado.src.data.validar_splits import (
    build_split_index, check_gold_membership, check_train_candidates, load_split_index,
)


def fixture():
    contexts = {
        "a": {"citing_id": "citante-A", "refid": "REFERENCIA", "masked_text": "We apply TARGETCIT."},
        "b": {"citing_id": "citante-B", "refid": "REFERENCIA", "masked_text": "We compare TARGETCIT."},
        "c": {"citing_id": "citante-C", "refid": "REFERENCIA", "masked_text": "We test TARGETCIT."},
    }
    splits = {p: [{"context_id": cid, "positive_ids": ["REFERENCIA"]}]
              for p, cid in (("train", "a"), ("val", "b"), ("test", "c"))}
    return contexts, splits


def case(cid, **meta):
    return SimpleNamespace(id=cid, metadata=meta)


def test_citado_compartido_no_es_fuga():
    contexts, splits = fixture()
    assert build_split_index(contexts, splits).by_context["c"] == "test"


def test_contexto_repetido_en_dos_splits_falla():
    contexts, splits = fixture()
    splits["val"].append(splits["train"][0])
    with pytest.raises(ValueError, match="Contexto repetido"):
        build_split_index(contexts, splits)


def test_mismo_citante_entre_splits_falla():
    contexts, splits = fixture()
    contexts["c"]["citing_id"] = "citante-A"
    with pytest.raises(ValueError, match="Citante compartido"):
        build_split_index(contexts, splits)


def test_positive_ids_incoherentes_fallan():
    contexts, splits = fixture()
    splits["test"][0]["positive_ids"] = ["OTRO"]
    with pytest.raises(ValueError, match="positive_ids"):
        build_split_index(contexts, splits)


def test_cita_objetivo_invalida_falla():
    contexts, splits = fixture()
    contexts["c"]["masked_text"] = "No marker"
    with pytest.raises(ValueError, match="TARGETCIT"):
        build_split_index(contexts, splits)


def test_gold_de_train_no_pasa_control_de_test():
    contexts, splits = fixture()
    idx = build_split_index(contexts, splits)
    assert check_gold_membership([case("a")], idx) == ["1 casos Gold fuera de la particion test"]


def test_gold_fuera_de_corpus_no_pasa():
    contexts, splits = fixture()
    idx = build_split_index(contexts, splits)
    assert check_gold_membership([case("desconocido")], idx) == [
        "1 casos Gold fuera de los splits supervisados"
    ]


def test_metadata_gold_incoherente_no_pasa():
    contexts, splits = fixture()
    idx = build_split_index(contexts, splits)
    assert check_gold_membership([case("c", citing_id="falso")], idx) == [
        "1 casos Gold con citante/citado incoherente"
    ]


def test_gold_test_valido_pasa():
    contexts, splits = fixture()
    idx = build_split_index(contexts, splits)
    assert check_gold_membership([case("c", citing_id="citante-C", cited_id="REFERENCIA")], idx) == []


def test_candidato_train_con_cita_incorrecta_no_pasa():
    contexts, splits = fixture()
    idx = build_split_index(contexts, splits)
    row = {"id": "a", "split": "train", "citing_id": "citante-A",
           "cited_id": "REFERENCIA", "citation_context": "We apply TARGETCIT."}
    assert check_train_candidates([row], idx) == []
    assert check_train_candidates([{**row, "cited_id": "FALSO"}], idx)


def test_candidato_val_no_puede_disfrazarse_de_train():
    contexts, splits = fixture()
    idx = build_split_index(contexts, splits)
    row = {"id": "b", "split": "train", "citing_id": "citante-B",
           "cited_id": "REFERENCIA", "citation_context": "We compare TARGETCIT."}
    assert check_train_candidates([row], idx)


def test_load_splits_desde_json(tmp_path):
    contexts, splits = fixture()
    (tmp_path / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    for name, value in splits.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    assert load_split_index(tmp_path).by_context == {"a": "train", "b": "val", "c": "test"}


def test_faltan_splits_falla(tmp_path):
    (tmp_path / "contexts.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_split_index(tmp_path)


def test_integracion_gate_gold_y_haiku_sobre_splits_sinteticos():
    """Cobertura de integración con la suite ACL-200 que ejecuta CI."""
    from src.evaluation.commercial.acl200_gold_split_gate import audit_acl_membership

    train_id = "P13-0001_P11-0001_0"
    val_id = "P14-0002_P11-0001_0"
    test_id = "P15-0003_P11-0001_0"
    contexts = {
        train_id: {"citing_id": "P13-0001", "refid": "P11-0001", "masked_text": "Train TARGETCIT."},
        val_id: {"citing_id": "P14-0002", "refid": "P11-0001", "masked_text": "Val TARGETCIT."},
        test_id: {"citing_id": "P15-0003", "refid": "P11-0001", "masked_text": "Test TARGETCIT."},
    }
    splits = {
        "train": [{"context_id": train_id, "positive_ids": ["P11-0001"]}],
        "val": [{"context_id": val_id, "positive_ids": ["P11-0001"]}],
        "test": [{"context_id": test_id, "positive_ids": ["P11-0001"]}],
    }
    index = build_split_index(contexts, splits)
    p91 = {
        val_id: {"grupo": "calibracion3", "tanda": ""},
        test_id: {"grupo": "testgold", "tanda": "1"},
    }
    p92 = {
        val_id: {"Contexto TARGETCIT": "Val TARGETCIT."},
        test_id: {"Contexto TARGETCIT": "Test TARGETCIT."},
    }
    haiku = {train_id: {"Contexto TARGETCIT": "Train TARGETCIT."}}

    report = audit_acl_membership(index, p91, p92, haiku, excluded=set())
    assert report["status"] == "SPLITS_Y_FUENTES_INSPECCIONADOS_CERTIFICACION_HUMANA_PENDIENTE"
    assert report["cross_checks"]["pr92_annotated_vs_haiku"]["documentos_citantes"] == 0
    assert report["cross_checks"]["pr92_annotated_vs_haiku"]["pares_citante_citado"] == 0
    assert report["gold_human_certified"] is False
    assert report["final_benchmark_allowed"] is False

    # Un candidato de entrenamiento en Gold debe ser detectado y bloquear la evaluación.
    contaminated = {**p92, train_id: {"Contexto TARGETCIT": "Train TARGETCIT."}}
    report_leak = audit_acl_membership(index, p91, contaminated, haiku, excluded=set())
    assert report_leak["status"] == "BLOQUEADO"
    assert report_leak["cross_checks"]["pr92_annotated_vs_haiku"]["ids"] == 1
