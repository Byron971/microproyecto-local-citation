"""Pruebas sin red/datos reales de la auditoría de lotes de jueces."""
import json
from pathlib import Path

import pytest

from proyecto_de_grado.scripts.auditar_lotes_jueces import (
    acl_year, audit, load_acl, read_ids, summarize,
)


def fixture_acl(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    contexts = {
        "train-old": {"citing_id": "P11-0001", "refid": "P95-0002", "masked_text": "TARGETCIT example"},
        "val-new": {"citing_id": "P14-0001", "refid": "P11-0001", "masked_text": "TARGETCIT example"},
        "test-old": {"citing_id": "P15-0001", "refid": "P88-0002", "masked_text": "TARGETCIT example"},
    }
    (raw / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    for name, ids in (("train", ["train-old"]), ("val", ["val-new"]), ("test", ["test-old"])):
        (raw / f"{name}.json").write_text(json.dumps([{"context_id": cid} for cid in ids]), encoding="utf-8")
    return raw


def test_anyo_citado_no_implica_exclusion_de_train(tmp_path):
    contexts, index, sizes = load_acl(fixture_acl(tmp_path))
    result = summarize(["train-old", "test-old"], contexts, index)
    assert sizes == {"train": 1, "val": 1, "test": 1}
    assert result["por_split_ids_unicos"] == {"train": 1, "val": 0, "test": 1}
    assert result["citado_1980_1999_por_split"] == {"train": 1, "val": 0, "test": 1}
    assert result["citante_1980_1999_por_split"] == {"train": 0, "val": 0, "test": 0}


def test_no_confundir_duplicados_con_entradas_fuera_split(tmp_path):
    contexts, index, _ = load_acl(fixture_acl(tmp_path))
    result = summarize(["train-old", "train-old", "unknown"], contexts, index, {"train-old"})
    assert result["filas"] == 3
    assert result["ids_unicos"] == 2
    assert result["ids_duplicados"] == 1
    assert result["fuera_de_splits_o_desconocidos"] == 1
    assert result["ids_en_exclusiones_gold"] == 1


def test_csv_jsonl_y_txt(tmp_path):
    csv_path = tmp_path / "lote.csv"
    csv_path.write_text("context_id,etiqueta\ntrain-old,Background\nval-new,Gap\n", encoding="utf-8")
    assert read_ids(csv_path) == ["train-old", "val-new"]
    jl = tmp_path / "lote.jsonl"
    jl.write_text('{"id":"test-old"}\n', encoding="utf-8")
    assert read_ids(jl) == ["test-old"]
    text = tmp_path / "lote.txt"
    text.write_text("# comentario\ntrain-old\n", encoding="utf-8")
    assert read_ids(text) == ["train-old"]


def test_falla_ante_id_no_identificable(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('[{"other":1,"x":2}]', encoding="utf-8")
    with pytest.raises(ValueError):
        read_ids(bad)


def test_reporte_no_afirma_lotes_ausentes(tmp_path):
    result = audit(fixture_acl(tmp_path), {"lote_18000": None, "etiquetas_2700": None})
    assert result["lotes"]["lote_18000"]["estado"].startswith("no_aportado")
    assert result["qlora"]["estado"] == "ruta no proporcionada; no auditado"


def test_year_codificacion_acl():
    assert acl_year("P95-1011") == 1995
    assert acl_year("P11-1011") == 2011
    assert acl_year("D79-0024") == 1979
    assert acl_year("not-id") is None


def test_cruce_2700_con_18000_y_antiguos(tmp_path):
    raw = fixture_acl(tmp_path)
    lote = tmp_path / "lote.txt"
    lote.write_text("train-old\nval-new\n", encoding="utf-8")
    etiquetas = tmp_path / "etiquetas.txt"
    etiquetas.write_text("train-old\ntest-old\n", encoding="utf-8")
    antiguas = tmp_path / "antiguas.txt"
    antiguas.write_text("train-old\n", encoding="utf-8")
    report = audit(raw, {"lote_18000": lote, "etiquetas_2700": etiquetas, "antiguas_595": antiguas})
    assert report["cruces_entre_lotes"]["etiquetas_2700_vs_lote_18000"]["fuera_de_lote"] == 1
    assert report["cruces_entre_lotes"]["antiguas_595_vs_lote_18000"]["en_lote"] == 1
