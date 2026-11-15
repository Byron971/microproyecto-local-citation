"""Pruebas sin Gold real de la barrera de particiones ACL-200."""
import csv
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.data.validar_splits import build_split_index
from src.evaluation.commercial.acl200_gold_split_gate import (
    _manifest_pr91, audit_acl_membership, main,
)


def fixture_sets():
    train = "P13-0001_P11-0001_0"
    valid = "P14-0002_P11-0001_0"
    test = "P15-0003_P11-0001_0"
    contexts = {
        train: {"citing_id": "P13-0001", "refid": "P11-0001", "masked_text": "Use TARGETCIT."},
        valid: {"citing_id": "P14-0002", "refid": "P11-0001", "masked_text": "Review TARGETCIT."},
        test: {"citing_id": "P15-0003", "refid": "P11-0001", "masked_text": "Test TARGETCIT."},
    }
    partitions = {
        "train": [{"context_id": train, "positive_ids": ["P11-0001"]}],
        "val": [{"context_id": valid, "positive_ids": ["P11-0001"]}],
        "test": [{"context_id": test, "positive_ids": ["P11-0001"]}],
    }
    idx = build_split_index(contexts, partitions)
    pr91 = {test: {"grupo": "testgold", "tanda": "1"},
            valid: {"grupo": "calibracion3", "tanda": ""}}
    annotated = {
        valid: {"Contexto TARGETCIT": "Review TARGETCIT."},
        test: {"Contexto TARGETCIT": "Test TARGETCIT."},
    }
    haiku = {train: {"Contexto TARGETCIT": "Use TARGETCIT."}}
    return idx, pr91, annotated, haiku, train, valid, test, contexts, partitions


def test_split_verificado_no_significa_gold_humano_certificado():
    idx, p91, p92, train, *_ = fixture_sets()
    report = audit_acl_membership(idx, p91, p92, train, excluded=set())
    assert not report["blockers"]
    assert report["acl_official_splits_loaded"] is True
    assert report["gold_human_certified"] is False
    assert report["final_benchmark_allowed"] is False
    assert report["cross_checks"]["pr92_annotated_vs_haiku"][
        "documentos_citados_compartidos_no_fuga_automatica"
    ] == 1


def test_val_disfrazado_de_test_se_bloquea():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    p91[test]["grupo"] = "calibracion3"
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert any("split_incorrecto" in issue for issue in report["blockers"])


def test_gold_compartido_con_train_se_bloquea():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    p92[train] = {"Contexto TARGETCIT": "Use TARGETCIT."}
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert any("split_incorrecto" in issue for issue in report["blockers"])
    assert report["cross_checks"]["pr92_annotated_vs_haiku"]["ids"] == 1


def test_texto_modificado_se_bloquea():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    p92[test]["Contexto TARGETCIT"] = "Cambiado TARGETCIT."
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert any("texto_distinto_del_original" in issue for issue in report["blockers"])


def test_caso_historico_pr92_no_se_borra_y_se_desestima():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    report = audit_acl_membership(idx, p91, p92, haiku, excluded={test})
    assert report["source_counts"]["pr92_annotated"]["total"] == 2
    assert report["source_counts"]["pr92_annotated"]["ids_candidatos_sin_exclusion"] == 1
    assert report["source_counts"]["pr92_annotated"]["errores_o_exclusiones"][
        "historicamente_excluido"
    ] == 1
    assert not report["final_benchmark_allowed"]


def test_pr91_manifest_rechaza_duplicados(tmp_path):
    f = tmp_path / "p91.csv"
    f.write_text(
        "context_id,grupo,tanda\nP15-0003_P11-0001_0,testgold,1\n"
        "P15-0003_P11-0001_0,testgold,1\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicado"):
        _manifest_pr91(f)


def test_cli_falla_si_raw_ausente(tmp_path):
    assert main(["--raw-dir", str(tmp_path)]) == 2
    assert not (tmp_path / "resumen_acl200.json").exists()


def test_cli_realiza_auditoria_sintetica_y_no_exporta_ids(tmp_path, monkeypatch):
    idx, p91, p92, haiku, train, valid, test, contexts, partitions = fixture_sets()
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    for split, rows in partitions.items():
        (raw / f"{split}.json").write_text(json.dumps(rows), encoding="utf-8")
    manifest = tmp_path / "pr91.csv"
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["context_id", "grupo", "tanda"])
        writer.writeheader()
        for cid, row in p91.items():
            writer.writerow({"context_id": cid, **row})
    columns = [
        "context_id", "Contexto TARGETCIT", "¿Evaluable?", "Función principal",
        "Confianza", "Justificación / duda", "Estado",
    ]
    def write_annotations(path, data):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for cid, row in data.items():
                writer.writerow({"context_id": cid, "Contexto TARGETCIT": row["Contexto TARGETCIT"],
                                 "¿Evaluable?": "Evaluable", "Función principal": "Background",
                                 "Confianza": "Alta", "Justificación / duda": "", "Estado": "COMPLETO"})
    csv92 = tmp_path / "pr92.csv"
    csvhaiku = tmp_path / "haiku.csv"
    write_annotations(csv92, p92)
    write_annotations(csvhaiku, haiku)
    monkeypatch.setattr(
        "src.evaluation.commercial.acl200_gold_split_gate.exclusion_ids",
        lambda: set(),
    )
    out = tmp_path / "out"
    assert main(["--raw-dir", str(raw), "--pr91", str(manifest),
                 "--pr92", str(csv92), "--haiku", str(csvhaiku),
                 "--output-dir", str(out)]) == 0
    report_text = (out / "resumen_acl200.json").read_text(encoding="utf-8")
    assert "P15-0003" not in report_text
    assert "P13-0001" not in report_text
    assert json.loads(report_text)["final_benchmark_allowed"] is False


def test_espacios_externos_no_son_cambio_de_contenido():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    # El lector _read del repositorio elimina espacios externos de los CSV.
    # El ACL original aún puede conservar esos espacios.
    idx.contexts[test]["masked_text"] = "  Test TARGETCIT.  "
    idx.contexts[train]["masked_text"] = " Use TARGETCIT. "
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert "texto_distinto_del_original" not in report["source_counts"]["pr92_annotated"]["errores_o_exclusiones"]
    assert "texto_distinto_del_original" not in report["source_counts"]["haiku_train"]["errores_o_exclusiones"]
    assert report["blockers"] == []


def test_contexto_existente_pero_ausente_de_particiones_bloquea():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    orphan = "P15-9999_P11-0001_0"
    idx.contexts[orphan] = {
        "citing_id": "P15-9999", "refid": "P11-0001",
        "masked_text": "Unused TARGETCIT."
    }
    p92[orphan] = {"Contexto TARGETCIT": "Unused TARGETCIT."}
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert report["source_counts"]["pr92_annotated"]["errores_o_exclusiones"][
        "presente_en_contexts_sin_split"
    ] == 1
    assert report["status"] == "BLOQUEADO"


def test_pr92_validacion_2014_fuera_splits_es_no_elegible_sin_bloquear():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    extra = "P14-7777_P11-0001_0"
    idx.contexts[extra] = {
        "citing_id": "P14-7777", "refid": "P11-0001",
        "masked_text": "Historical TARGETCIT."
    }
    p92[extra] = {"Contexto TARGETCIT": "Historical TARGETCIT.", "Estado": "COMPLETO"}
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert report["blockers"] == []
    assert report["historical_validation_noneligible"] == 1
    assert report["source_counts"]["pr92_annotated"]["ids_candidatos_sin_exclusion"] == 2
    assert report["gold_human_certified"] is False
    assert report["final_benchmark_allowed"] is False


def test_pr92_historico_fuera_splits_si_en_pr91_se_bloquea():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    extra = "P14-7777_P11-0001_0"
    idx.contexts[extra] = {
        "citing_id": "P14-7777", "refid": "P11-0001",
        "masked_text": "Historical TARGETCIT."
    }
    p92[extra] = {"Contexto TARGETCIT": "Historical TARGETCIT.", "Estado": "COMPLETO"}
    p91[extra] = {"grupo": "calibracion3", "tanda": ""}
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert report["status"] == "BLOQUEADO"
    assert report["historical_validation_noneligible"] == 0


def test_pr92_test_2015_fuera_splits_sigue_bloqueado():
    idx, p91, p92, haiku, train, valid, test, *_ = fixture_sets()
    extra = "P15-7777_P11-0001_0"
    idx.contexts[extra] = {
        "citing_id": "P15-7777", "refid": "P11-0001",
        "masked_text": "Test orphan TARGETCIT."
    }
    p92[extra] = {"Contexto TARGETCIT": "Test orphan TARGETCIT.", "Estado": "COMPLETO"}
    report = audit_acl_membership(idx, p91, p92, haiku, excluded=set())
    assert report["status"] == "BLOQUEADO"
    assert report["source_counts"]["pr92_annotated"]["errores_o_exclusiones"][
        "presente_en_contexts_sin_split"
    ] == 1
