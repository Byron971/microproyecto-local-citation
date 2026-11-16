"""Pipeline A4 2x2 sin Gold: casos sintéticos y adaptadores de prueba explícitos."""
import hashlib
import json

import pytest

from src.evaluation.a4_infer_unlabeled import (
    InputError, metadata_plan, read_unlabeled_inputs, run_four_arm,
    build_factorial_config, _arm_evidence,
)
from src.evaluation.commercial.metrics import CATEGORIES


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@pytest.fixture
def cases(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    sources = {
        "t1": {"citing_id": "cit-t1", "refid": "paper-t1",
               "masked_text": "Training TARGETCIT data."},
        "v1": {"citing_id": "cit-v1", "refid": "paper-v1",
               "masked_text": "Validation TARGETCIT data."},
        "q1": {"citing_id": "cit-q1", "refid": "paper-q1",
               "masked_text": "Graph TARGETCIT evidence."},
    }
    (raw / "contexts.json").write_text(json.dumps(sources))
    for part, ids in (("train", ["t1"]), ("val", ["v1"]), ("test", ["q1"])):
        (raw / f"{part}.json").write_text(json.dumps([
            {"context_id": i, "positive_ids": [sources[i]["refid"]]} for i in ids
        ]))
    source = tmp_path / "heldout.jsonl"
    source.write_text(json.dumps({
        "context_id": "q1", "citing_id": "cit-q1", "cited_id": "paper-q1",
        "split": "test", "citation_context": "Graph TARGETCIT evidence.",
        "context_sha256": sha("Graph TARGETCIT evidence."),
        "cited_title": "Graph Citation Science",
        "cited_abstract": "Article discussing scientific graphs.",
        "chunks": [
            {"chunk_id": f"p{i}", "texto": f"Graph methods in chunk {i}.",
             "seccion": "Methods"} for i in range(1, 4)
        ],
    }) + "\n")
    return source, raw


def test_offline_dry_run_reads_no_gold_and_checks_acl(cases):
    source, raw = cases
    report = metadata_plan(source, raw_dir=raw)
    assert report["status"] == "INPUTS_ACL_OFICIAL_VERIFICADOS_SIN_INFERENCIA"
    assert report["n_inputs_unlabeled"] == 1
    assert report["n_four_arms_expected"] == 4
    assert report["predictions_executed"] is False
    assert report["test_gold_certified"] is False
    assert set(report["acl_official_sha256"]) == {
        "contexts.json", "train.json", "val.json", "test.json",
    }


def test_offline_refuses_gold_keys_before_any_model_load(cases):
    source, raw = cases
    doc = json.loads(source.read_text())
    doc["gold"] = "Background"
    source.write_text(json.dumps(doc) + "\n")
    with pytest.raises(InputError, match="campos no permitidos"):
        read_unlabeled_inputs(source)


def test_offline_rejects_source_document_sha_mismatch(cases):
    source, raw = cases
    doc = json.loads(source.read_text())
    doc["context_sha256"] = sha("unrelated TARGETCIT")
    source.write_text(json.dumps(doc) + "\n")
    with pytest.raises(InputError, match="hash del contexto"):
        read_unlabeled_inputs(source)


def test_offline_no_implicit_model_download_or_checkpoint_fallback(cases, tmp_path, monkeypatch):
    source, raw = cases
    import src.evaluation.a4_infer_unlabeled as pipeline
    monkeypatch.setattr(pipeline, "preflight", lambda *a, **k: {
        "ready_four_a4": False,
    })
    output = tmp_path / "inferencia"
    with pytest.raises(RuntimeError, match="pesos originales"):
        run_four_arm(source, raw_dir=raw, checkpoint_root=tmp_path,
                     output_dir=output)
    assert not output.exists()


def test_a4_original_four_manifests_form_valid_controlled_matrix(tmp_path):
    from src.evaluation.commercial.a4_factorial_benchmark import load_config
    from src.evaluation.a4_infer_unlabeled import ARMS
    historic = {name: _arm_evidence(name, encoder, inp)
                for name, encoder, inp in ARMS}
    config = build_factorial_config(historic)
    output = tmp_path / "factorial.json"
    output.write_text(json.dumps(config))
    variants = load_config(output)
    assert len(variants) == 4
    assert {x["encoder"] for x in variants} == {"SciBERT", "SPECTER"}
    assert {x["input"] for x in variants} == {"A", "B"}
    assert {x["training_labels"] for x in variants} == {"Haiku"}


def test_offline_pipeline_synthetic_four_arm_atomic_outputs(cases, tmp_path, monkeypatch):
    import src.evaluation.a4_infer_unlabeled as pipeline
    from src.app.classifier_runtime import A4Classifier
    from src.app.scibert_runtime import SciBERTRuntime

    source, raw = cases
    monkeypatch.setattr(pipeline, "preflight", lambda *a, **k: {
        "ready_four_a4": True,
    })

    class FakeDense:
        def top3(self, ctx, chunks, *, document_key=None):
            assert document_key is None  # NO cache de heldout
            return chunks[:3]

    class FakeClassifier:
        def __init__(self, run):
            self.name = run.name
            self.encoder = self.name.split("_")[0]
            self.variant = self.name.split("_")[1]

        def classify(self, context, title=None, abstract=None, top3=None):
            assert context.count("TARGETCIT") == 1
            if self.variant == "B":
                assert top3 is not None and len(top3) == 3
            else:
                assert title and abstract and top3 is None
            return {
                "modelo": self.name, "encoder": self.encoder,
                "entrada": self.variant, "training_labels": "Haiku",
                "validacion": "provisional_no_gold_humano",
                "clase": CATEGORIES[0], "indice_clase": 0,
                "puntuaciones_softmax": [
                    {"categoria": label, "score": 0.92 if i == 0 else 0.01}
                    for i, label in enumerate(CATEGORIES)
                ], "latencia_modelo_ms": 1.0,
            }

    monkeypatch.setattr(SciBERTRuntime, "load",
                        classmethod(lambda cls, *a, **k: FakeDense()))
    monkeypatch.setattr(A4Classifier, "load",
                        classmethod(lambda cls, run, *a, **k: FakeClassifier(run)))

    output = tmp_path / "private_predictions"
    report = run_four_arm(source, raw_dir=raw, checkpoint_root=tmp_path,
                          output_dir=output)
    assert report["status"] == "PREDICCIONES_A4_CIEGAS_NO_EVALUADAS"
    assert report["n_models"] == 4
    assert report["n_cases"] == 1
    assert report["contains_gold_labels"] is False
    assert report["test_gold_certified"] is False
    assert report["results_computed"] is False
    files = sorted(output.iterdir())
    assert len(files) == 6  # cuatro JSONL, config y manifiesto
    for fname in ("scibert_A_42", "scibert_B_42", "specter_A_42", "specter_B_42"):
        rows = [json.loads(line) for line in (output / f"{fname}.jsonl").read_text().splitlines()]
        assert rows == [{"case_id": "q1", "status": "ok",
                         "pred_label": CATEGORIES[0], "pred_index": 0,
                         "model_id": fname, "latency_model_ms": 1.0}]
    with pytest.raises(InputError, match="ya existe"):
        run_four_arm(source, raw_dir=raw, checkpoint_root=tmp_path,
                     output_dir=output)
