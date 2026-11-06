"""Pruebas sintéticas A4; no generan resultados científicos de tesis."""
import copy
import json

import pytest

from src.evaluation.commercial.a4_factorial_benchmark import (
    load_config, main, run_factorial,
)


def gold(cid, label, paper=None):
    return {
        "id": cid, "input": "We apply TARGETCIT to this work.",
        "gold": label, "citing_id": paper or f"citing-{cid}", "cited_id": "shared-cited",
    }


def pred(cid, label, status="ok"):
    return {"case_id": cid, "status": status, "pred_label": label}


def matrix(source="Haiku", train_digest="a" * 64):
    arms = []
    for i, (encoder, inp) in enumerate(
        [(e, x) for e in ("SciBERT", "SPECTER") for x in ("A", "B")]
    ):
        arms.append({
            "name": f"{source.lower()}-{encoder.lower()}-{inp.lower()}",
            "encoder": encoder, "input": inp, "training_labels": source,
            "predictions": f"{encoder.lower()}_{inp.lower()}.jsonl",
            "checkpoint_sha256": format(i + 1, "x") * 64,
            "train_ids_sha256": train_digest,
            "train_labels_sha256": "b" * 64 if source == "Haiku" else "e" * 64,
            "input_spec_sha256": "c" * 64 if inp == "A" else "d" * 64,
        })
    return arms


def data():
    cases = [
        gold("c1", "Background"),
        gold("c2", "Gap"),
        gold("c3", "Basis"),
        gold("c4", "Comparison"),
    ]
    predictions = {
        "haiku-scibert-a": [pred("c1", "Background"), pred("c2", "Gap"),
                            pred("c3", "Background"), pred("c4", "Comparison")],
        "haiku-scibert-b": [pred("c1", "Background"), pred("c2", "Gap"),
                            pred("c3", "Basis"), pred("c4", "Comparison")],
        "haiku-specter-a": [pred("c1", "Gap"), pred("c2", "Gap"),
                            pred("c3", "Basis"), pred("c4", "Comparison")],
        "haiku-specter-b": [pred("c1", "Background"), pred("c2", "Gap"),
                            pred("c3", "Basis"), pred("c4", "Comparison")],
    }
    return cases, predictions


def config_json(tmp_path, arms=None, **overrides):
    cfg = {
        "schema_version": "a4_factorial_v1",
        "data_use": "provisional_only",
        "variants": arms if arms is not None else matrix(),
    }
    cfg.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_four_arms_same_gold_nine_class_macro_and_factors():
    cases, predictions = data()
    report = run_factorial(cases, matrix(), predictions)
    assert report["status"] == "PROVISIONAL_NO_CERTIFICADO"
    assert report["test_gold_certified"] is False
    assert report["ready_for_final_article"] is False
    assert report["n_same_gold"] == 4
    assert len(report["variants"]) == 4
    assert len(report["contrasts"]) == 4
    assert {contrast["factor"] for contrast in report["contrasts"]} == {"input", "encoder"}
    all_variants = report["variants"]
    assert all_variants["haiku-scibert-b"]["metrics"]["f1_macro"] == pytest.approx(4 / 9)
    assert all_variants["haiku-scibert-a"]["metrics"]["f1_micro"] == pytest.approx(0.75)
    pair = next(x for x in report["contrasts"] if x["variant_a"] == "haiku-scibert-a")
    assert pair["variant_b"] == "haiku-scibert-b"
    assert pair["delta_f1_macro_b_minus_a"] > 0
    assert pair["paired_cases"]["b_only_correct"] == 1
    assert sum(
        pair["paired_cases"][key] for key in
        ("a_only_correct", "b_only_correct", "both_correct", "both_wrong")
    ) == 4
    assert pair["bootstrap_cluster_95pct"] is None


def test_bootstrap_is_clustered_and_repeatable():
    cases, predictions = data()
    first = run_factorial(cases, matrix(), predictions, bootstrap_draws=100, seed=27)
    second = run_factorial(cases, matrix(), predictions, bootstrap_draws=100, seed=27)
    a = first["contrasts"][0]["bootstrap_cluster_95pct"]
    assert a == second["contrasts"][0]["bootstrap_cluster_95pct"]
    assert a["unit"] == "citing_id"
    assert a["n_citing_documents"] == 4
    assert a["lower"] <= a["upper"]
    assert first["status"] == "PROVISIONAL_NO_CERTIFICADO"


def test_bootstrap_requires_two_independent_documents():
    cases, predictions = data()
    for case in cases:
        case["citing_id"] = "same-citing-document"
    with pytest.raises(ValueError, match=">= 2"):
        run_factorial(cases, matrix(), predictions, bootstrap_draws=100)


def test_missing_or_extra_predictions_fail_closed():
    cases, predictions = data()
    predictions["haiku-scibert-b"].pop()
    with pytest.raises(ValueError, match="IDs no comparables"):
        run_factorial(cases, matrix(), predictions)


def test_abstention_cannot_be_silently_dropped():
    cases, predictions = data()
    predictions["haiku-scibert-a"][0]["status"] = "provider_error"
    with pytest.raises(ValueError, match="incompleta"):
        run_factorial(cases, matrix(), predictions)


def test_duplicate_predictions_fail():
    cases, predictions = data()
    predictions["haiku-scibert-a"].append(pred("c1", "Background"))
    with pytest.raises(ValueError, match="duplicado"):
        run_factorial(cases, matrix(), predictions)


def test_complete_matrix_required_for_each_source(tmp_path):
    with pytest.raises(ValueError, match="incompleta"):
        load_config(config_json(tmp_path, matrix()[:-1]))


def test_same_training_examples_required_within_matrix(tmp_path):
    arms = matrix()
    arms[-1]["train_ids_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="train_ids_sha256"):
        load_config(config_json(tmp_path, arms))


def test_same_label_manifest_required_within_matrix(tmp_path):
    arms = matrix()
    arms[0]["train_labels_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="train_labels_sha256"):
        load_config(config_json(tmp_path, arms))


def test_same_input_definition_across_encoders(tmp_path):
    arms = matrix()
    arms[-1]["input_spec_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="definición"):
        load_config(config_json(tmp_path, arms))


def test_duplicate_cell_and_model_version_digest_rejected(tmp_path):
    arms = matrix()
    arms[1]["input"] = "A"
    with pytest.raises(ValueError, match="Celda A4 duplicada"):
        load_config(config_json(tmp_path, arms))
    arms = matrix()
    arms[0]["checkpoint_sha256"] = ""
    with pytest.raises(ValueError, match="checkpoint_sha256"):
        load_config(config_json(tmp_path, arms))


def test_cannot_label_source_as_input_factor(tmp_path):
    arms = matrix()
    arms[0]["input"] = "Jurado"
    with pytest.raises(ValueError, match="matriz A4 inválida"):
        load_config(config_json(tmp_path, arms))


def test_extra_label_source_with_nonmatching_training_examples_has_no_causal_delta():
    cases, preds = data()
    other = matrix("Jurado", train_digest="f" * 64)
    predictions = dict(preds)
    for arm in other:
        source_name = arm["name"].replace("jurado-", "haiku-")
        predictions[arm["name"]] = list(predictions[source_name])
    result = run_factorial(cases, matrix() + other, predictions)
    assert len(result["variants"]) == 8
    assert len(result["contrasts"]) == 8
    assert all(c["factor"] != "training_labels" for c in result["contrasts"])
    assert any("no controlados" in w for w in result["warnings"])


def test_equal_training_samples_allow_isolated_label_source_comparison():
    cases, preds = data()
    other = matrix("Jurado")
    predictions = dict(preds)
    for arm in other:
        predictions[arm["name"]] = list(predictions[arm["name"].replace("jurado-", "haiku-")])
    result = run_factorial(cases, matrix() + other, predictions)
    assert len(result["contrasts"]) == 12
    assert sum(c["factor"] == "training_labels" for c in result["contrasts"]) == 4


def test_different_gold_label_vector_not_scientific_claim():
    cases, predictions = data()
    report = run_factorial(cases, matrix(), predictions)
    assert report["ready_for_final_article"] is False


def test_cli_without_provisional_does_not_create_report(tmp_path):
    out = tmp_path / "reports"
    rc = main([
        "--gold", str(tmp_path / "none.jsonl"),
        "--config", str(tmp_path / "none.json"),
        "--raw-dir", str(tmp_path / "no_raw"),
        "--output-dir", str(out),
    ])
    assert rc == 2
    assert not out.exists()


def test_cli_fails_with_missing_raw_even_when_provisional(tmp_path):
    cases, predictions = data()
    path = config_json(tmp_path)
    gold_path = tmp_path / "not-certified-gold.jsonl"
    gold_path.write_text(
        "\n".join(json.dumps(row) for row in cases) + "\n", encoding="utf-8"
    )
    for arm in matrix():
        (tmp_path / arm["predictions"]).write_text(
            "\n".join(json.dumps(row) for row in predictions[arm["name"]]) + "\n",
            encoding="utf-8"
        )
    out = tmp_path / "out"
    rc = main([
        "--gold", str(gold_path), "--config", str(path),
        "--raw-dir", str(tmp_path / "missing"), "--output-dir", str(out),
        "--provisional",
    ])
    assert rc == 2
    assert not out.exists()


def test_cli_synthetic_acl_e2e_only_provisional(tmp_path, monkeypatch):
    import src.evaluation.commercial.a4_factorial_benchmark as mod

    root = tmp_path / "fake_repo"
    anno = root / "proyecto_de_grado" / "anotacion"
    anno.mkdir(parents=True)
    (anno / "ids_excluir_test_gold.txt").write_text("old-practice\n", encoding="utf-8")
    (anno / "ids_piloto_historico_no_test_final.txt").write_text("old-pilot\n", encoding="utf-8")

    cases, predictions = data()
    raw = tmp_path / "raw"
    raw.mkdir()
    contexts = {
        case["id"]: {
            "citing_id": case["citing_id"], "refid": case["cited_id"],
            "masked_text": case["input"],
        }
        for case in cases
    }
    (raw / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    for split in ("train", "val", "test"):
        rows = [
            {"context_id": case["id"], "positive_ids": [case["cited_id"]]}
            for case in cases
        ] if split == "test" else []
        (raw / f"{split}.json").write_text(json.dumps(rows), encoding="utf-8")

    gold_file = tmp_path / "gold_candidate.jsonl"
    gold_file.write_text(
        "\n".join(json.dumps(row) for row in cases) + "\n", encoding="utf-8"
    )
    config = config_json(tmp_path)
    for arm in matrix():
        path = tmp_path / arm["predictions"]
        path.write_text(
            "\n".join(json.dumps(row) for row in predictions[arm["name"]]) + "\n",
            encoding="utf-8",
        )

    original = mod.inspect_gold

    def fake_audit(gold_path, instances, *, raw_dir):
        return original(gold_path, instances, raw_dir=raw_dir, root=root)

    monkeypatch.setattr(mod, "inspect_gold", fake_audit)
    out = tmp_path / "results"
    args = [
        "--gold", str(gold_file), "--config", str(config),
        "--raw-dir", str(raw), "--output-dir", str(out),
        "--provisional", "--bootstrap-draws", "100", "--seed", "23",
    ]
    assert main(args) == 0
    data = json.loads((out / "a4_factorial_provisional.json").read_text(encoding="utf-8"))
    assert data["n_same_gold"] == 4
    assert data["provenance"]["human_gold_certified"] is False
    assert data["provenance"]["raw_dir_verified"] is True
    assert data["provenance"]["predictions_sha256"]
    assert data["variants"]["haiku-scibert-a"]["metrics"]["confusion_matrix"]
    assert (out / "a4_model_scores.csv").exists()
    assert "We apply TARGETCIT" not in json.dumps(data)
