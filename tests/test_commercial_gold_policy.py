"""Regresiones G0.6: impedir que el piloto se presente como Test Gold."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.evaluation.commercial.gold_policy import exclusion_ids, inspect_gold


def _case(cid, input_text="Prior TARGETCIT work", gold="Application"):
    return SimpleNamespace(id=cid, input=input_text, gold=gold)


def _root(tmp_path, *, first="DEV-1", second="LEG-1"):
    base = tmp_path / "proyecto_de_grado" / "anotacion"
    base.mkdir(parents=True)
    (base / "ids_excluir_test_gold.txt").write_text("# Practica\n" + first + "\n", encoding="utf-8")
    (base / "ids_piloto_historico_no_test_final.txt").write_text("# Piloto\n" + second + "\n", encoding="utf-8")
    return tmp_path


def test_union_dos_manifiestos(tmp_path):
    root = _root(tmp_path, first="X", second="X")
    assert exclusion_ids(root) == {"X"}


def test_exclusiones_faltantes_bloquean(tmp_path):
    with pytest.raises(FileNotFoundError, match="manifiesto"):
        exclusion_ids(tmp_path)


def test_legacy_no_se_puede_presentar_como_final(tmp_path):
    root = _root(tmp_path)
    result = inspect_gold("annotations/citation_function/test_gold.jsonl", [_case("C-1")], root=root)
    assert result.provisional
    assert "historico" in result.reasons[0]


def test_renombrar_el_piloto_no_borra_su_historial(tmp_path):
    root = _root(tmp_path)
    result = inspect_gold("copias/gold_nuevo.jsonl", [_case("LEG-1")], root=root)
    assert result.provisional
    assert "identificadores" in " ".join(result.reasons)


def test_contexto_sin_targetcit_no_puede_ser_final(tmp_path):
    root = _root(tmp_path)
    result = inspect_gold("nuevo.jsonl", [_case("NUEVO", "sin marcador")], root=root)
    assert result.provisional
    assert "TARGETCIT" in " ".join(result.reasons)


def test_nuevo_con_marcador_y_sin_exclusiones_supera_control_minimo(tmp_path):
    root = _root(tmp_path)
    result = inspect_gold("nuevo.jsonl", [_case("NUEVO")], root=root)
    assert result.provisional is False
    assert result.excluded_ids == 2


def test_gold_sin_etiqueta_se_considera_provisional(tmp_path):
    root = _root(tmp_path)
    assert inspect_gold("nuevo.jsonl", [_case("NUEVO", gold=None)], root=root).provisional


def test_ids_duplicados_se_rechazan(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ValueError, match="duplicados"):
        inspect_gold("nuevo.jsonl", [_case("N"), _case("N")], root=root)

def test_integracion_gold_rechaza_contexto_en_train(tmp_path):
    import json
    root = _root(tmp_path)
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    ctx = {"ctx-train": {"citing_id": "P12-1", "refid": "P10-2",
                         "masked_text": "We use TARGETCIT."}}
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    for name in ("train", "val", "test"):
        rows = [{"context_id": "ctx-train", "positive_ids": ["P10-2"]}] if name == "train" else []
        (raw / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    result = inspect_gold("nuevo_gold.jsonl", [_case("ctx-train")], root=root, raw_dir=raw)
    assert result.provisional
    assert "particion test" in " ".join(result.reasons)


def test_integracion_gold_falla_cerrado_si_faltan_datos(tmp_path):
    root = _root(tmp_path)
    result = inspect_gold(
        "nuevo_gold.jsonl", [_case("ejemplo")], root=root, raw_dir=tmp_path / "no-existe"
    )
    assert result.provisional
    assert "No se pudo verificar particion" in " ".join(result.reasons)
