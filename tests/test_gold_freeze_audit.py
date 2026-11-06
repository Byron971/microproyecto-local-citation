"""Pruebas sintéticas del gate Gold: ninguna anotación equivale a Gold real."""
import copy
import json
from pathlib import Path

import pytest

from src.evaluation.commercial.gold_freeze_audit import (
    audit_candidate, load_dataset_ids, main, read_adjudications,
)


def fixture_gold(tmp_path):
    root = tmp_path / "repo"
    exclusions = root / "proyecto_de_grado/anotacion"
    exclusions.mkdir(parents=True)
    (exclusions / "ids_excluir_test_gold.txt").write_text("old_practice\n", encoding="utf-8")
    (exclusions / "ids_piloto_historico_no_test_final.txt").write_text("old_pilot\n", encoding="utf-8")

    ids = ("tr", "va", "g1", "g2", "extra1", "extra2", "extra3", "extra4", "extra5", "extra6")
    raw = tmp_path / "raw"
    raw.mkdir()
    def context(cid):
        return {
            "citing_id": "citing_" + cid,
            "refid": "cited_" + cid,
            "masked_text": "Citation " + cid + " TARGETCIT context.",
        }
    contexts = {cid: context(cid) for cid in ids}
    (raw / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    for split, subset in {"train": ["tr"], "val": ["va"], "test": ["g1", "g2"]}.items():
        rows = [{"context_id": cid, "positive_ids": ["cited_" + cid]} for cid in subset]
        (raw / f"{split}.json").write_text(json.dumps(rows), encoding="utf-8")
    def row(cid, gold=None):
        result = {
            "id": cid, "input": contexts[cid]["masked_text"],
            "citing_id": contexts[cid]["citing_id"], "cited_id": contexts[cid]["refid"],
        }
        if gold is not None:
            result["gold"] = gold
        return result
    gold = [row("g1", "Background"), row("g2", "Gap")]
    train = [row("tr")]
    val = [row("va")]
    reviews = [
        {"case_id": "g1", "annotator_id": "human-A", "label": "Background"},
        {"case_id": "g1", "annotator_id": "human-B", "label": "Background"},
        {"case_id": "g2", "annotator_id": "human-A", "label": "Gap"},
        {"case_id": "g2", "annotator_id": "human-B", "label": "Basis"},
        {"case_id": "extra1", "annotator_id": "human-A", "label": "Gap"},
    ]
    adjudications = [{
        "case_id": "g2", "adjudicator_id": "human-C",
        "label": "Gap", "reason": "Evidence supports a missing research gap",
    }]
    return {
        "root": root, "raw": raw, "ids": set(ids),
        "gold": gold, "train": train, "val": val,
        "reviews": reviews, "adjudications": adjudications,
        "gold_path": tmp_path / "gold_candidate.jsonl",
    }


def audit(f, **overrides):
    options = {key: val for key, val in f.items()}
    options.update(overrides)
    return audit_candidate(
        options["gold"], options["reviews"], options["adjudications"],
        options["ids"], options["train"], options["val"],
        gold_path=options["gold_path"],
        raw_dir=options["raw"], root=options["root"],
    )


def test_valid_synthetic_candidate_never_certifies_gold(tmp_path):
    f = fixture_gold(tmp_path)
    report = audit(f)
    assert report["status"] == "CANDIDATO_PARA_REVISION_HUMANA_NO_CERTIFICADO"
    assert report["blockers"] == []
    assert report["gold_human_certified"] is False
    assert report["ready_for_final_benchmark"] is False
    assert report["human_review_fraction"] == pytest.approx(0.3)
    assert report["human_stats"]["n_gold_double_reviewed"] == 2
    assert report["human_stats"]["n_gold_disagreements"] == 1
    assert report["n_gold_classes"] == 2


def test_missing_human_coverage_blocks_even_if_gold_double_annotated(tmp_path):
    f = fixture_gold(tmp_path)
    f["ids"] = {f"dataset_{i}" for i in range(100)} | {"g1", "g2", "extra1"}
    report = audit(f)
    assert report["status"] == "BLOQUEADO"
    assert any("Validación humana" in b for b in report["blockers"])


def test_human_reviewer_missing_for_gold_blocks(tmp_path):
    f = fixture_gold(tmp_path)
    f["reviews"] = [r for r in f["reviews"]
                    if not (r["case_id"] == "g2" and r["annotator_id"] == "human-B")]
    result = audit(f)
    assert any("faltan dos anotaciones" in b for b in result["blockers"])


def test_unadjudicated_disagreement_blocks(tmp_path):
    f = fixture_gold(tmp_path)
    result = audit(f, adjudications=[])
    assert any("desacuerdo sin adjudicación" in b for b in result["blockers"])


def test_adjudicator_cannot_be_original_reviewer(tmp_path):
    f = fixture_gold(tmp_path)
    f["adjudications"][0]["adjudicator_id"] = "human-A"
    result = audit(f)
    assert any("coincide con anotador" in b for b in result["blockers"])


def test_gold_label_must_match_adjudication(tmp_path):
    f = fixture_gold(tmp_path)
    f["gold"][1]["gold"] = "Basis"
    result = audit(f)
    assert any("contradice adjudicación" in b for b in result["blockers"])


def test_gold_label_must_match_agreement(tmp_path):
    f = fixture_gold(tmp_path)
    f["gold"][0]["gold"] = "Basis"
    result = audit(f)
    assert any("contradice consenso" in b for b in result["blockers"])


def test_duplicate_annotator_does_not_count_as_two_humans(tmp_path):
    f = fixture_gold(tmp_path)
    f["reviews"][1]["annotator_id"] = "human-A"
    result = audit(f)
    assert any("anotador duplicado" in b for b in result["blockers"])
    assert any("faltan dos" in b for b in result["blockers"])


def test_prelabel_scores_not_accepted_as_gold_or_human(tmp_path):
    f = fixture_gold(tmp_path)
    f["gold"][0]["gold"] = [1.0] + [0.0] * 8
    with pytest.raises(ValueError, match="nueve etiquetas"):
        audit(f)


def test_old_gold_pilot_ids_always_blocked(tmp_path):
    f = fixture_gold(tmp_path)
    f["gold"][0]["id"] = "old_practice"
    result = audit(f)
    assert any("Política Gold" in x for x in result["blockers"])


def test_train_citing_document_leakage_blocked(tmp_path):
    f = fixture_gold(tmp_path)
    f["train"][0]["citing_id"] = f["gold"][0]["citing_id"]
    result = audit(f)
    assert any("citantes Gold compartidos" in x for x in result["blockers"])


def test_duplicate_text_in_validation_blocks_even_with_new_ids(tmp_path):
    f = fixture_gold(tmp_path)
    f["val"][0]["input"] = f["gold"][0]["input"]
    result = audit(f)
    assert any("contextos textuales repetidos" in x for x in result["blockers"])


def test_gold_must_belong_to_acl_test_split(tmp_path):
    f = fixture_gold(tmp_path)
    f["gold"][0]["id"] = "tr"
    result = audit(f)
    assert any("particion test" in x for x in result["blockers"])


def test_train_validation_missing_manifests_block(tmp_path):
    f = fixture_gold(tmp_path)
    result = audit(f, train=[], val=[])
    assert any("manifiesto" in x for x in result["blockers"])


def test_no_raw_data_blocks_audit(tmp_path):
    f = fixture_gold(tmp_path)
    result = audit(f, raw=tmp_path / "missing")
    assert any("No se pudo verificar particion" in x or "no verificables" in x
               for x in result["blockers"])


def test_dataset_ids_duplicate_blocked_and_comment_allowed(tmp_path):
    p = tmp_path / "dataset_ids.txt"
    p.write_text("# comentario\na\nb\n", encoding="utf-8")
    assert load_dataset_ids(p) == {"a", "b"}
    p.write_text("a\na\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicado"):
        load_dataset_ids(p)


def test_empty_adjudications_file_permitted_when_consensus(tmp_path):
    p = tmp_path / "adjudications.jsonl"
    p.write_text("", encoding="utf-8")
    assert read_adjudications(p) == []


def test_cli_writes_sha256_report_but_does_not_certify(tmp_path, monkeypatch):
    f = fixture_gold(tmp_path)
    paths = {}
    for key in ("gold", "reviews", "adjudications", "train", "val"):
        p = tmp_path / (key + ".jsonl")
        p.write_text(
            "".join(json.dumps(row) + "\n" for row in f[key]), encoding="utf-8"
        )
        paths[key] = p
    ids = tmp_path / "dataset_ids.txt"
    ids.write_text("\n".join(sorted(f["ids"])) + "\n", encoding="utf-8")
    import src.evaluation.commercial.gold_freeze_audit as gate

    original = gate.audit_candidate

    def with_test_root(*args, **kwargs):
        kwargs["root"] = f["root"]
        return original(*args, **kwargs)

    monkeypatch.setattr(gate, "audit_candidate", with_test_root)
    out = tmp_path / "reports"
    code = main([
        "--gold", str(paths["gold"]), "--reviews", str(paths["reviews"]),
        "--adjudications", str(paths["adjudications"]),
        "--train", str(paths["train"]), "--validation", str(paths["val"]),
        "--dataset-ids", str(ids), "--raw-dir", str(f["raw"]),
        "--output-dir", str(out),
    ])
    assert code == 0
    report = json.loads((out / "gold_audit.json").read_text(encoding="utf-8"))
    assert report["status"] == "CANDIDATO_PARA_REVISION_HUMANA_NO_CERTIFICADO"
    assert len(report["input_sha256"]["gold"]) == 64
    assert report["gold_human_certified"] is False
    assert "Gold TARGETCIT" not in json.dumps(report)


def test_cli_fails_with_invalid_input_or_missing_files(tmp_path):
    code = main([
        "--gold", str(tmp_path / "none.jsonl"),
        "--reviews", str(tmp_path / "none_reviews.jsonl"),
        "--adjudications", str(tmp_path / "none_adjudications.jsonl"),
        "--train", str(tmp_path / "train.jsonl"), "--validation", str(tmp_path / "val.jsonl"),
        "--dataset-ids", str(tmp_path / "dataset.txt"), "--raw-dir", str(tmp_path),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert code == 2
    assert not (tmp_path / "out").exists()
