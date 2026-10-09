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
