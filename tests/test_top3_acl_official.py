"""ACL-200 oficial debe prevalecer sobre etiquetas de split auto-declaradas."""
import csv
import hashlib
import json

import pytest

from proyecto_de_grado.src.evaluation.top3_gold_gate import (
    ProtocolError, audit, check_acl_official, load_universe,
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_acl(tmp_path):
    raw = tmp_path / "acl"
    raw.mkdir()
    texts = {
        "q1": "Graph models TARGETCIT are reviewed.",
        "q2": "Scientific citations TARGETCIT are useful.",
        "t1": "Training examples TARGETCIT do not overlap.",
        "v1": "Development examples TARGETCIT do not overlap.",
    }
    ctx = {
        cid: {"citing_id": "citing-" + cid, "refid": "cited-" + cid,
              "masked_text": text}
        for cid, text in texts.items()
    }
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    for split, ids in (("train", ["t1"]), ("val", ["v1"]), ("test", ["q1", "q2"])):
        (raw / (split + ".json")).write_text(json.dumps([
            {"context_id": cid, "positive_ids": ["cited-" + cid]}
            for cid in ids
        ]), encoding="utf-8")
    manifest = tmp_path / "universe.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "purpose": "heldout_chunk_relevance",
        "used_for_tuning": False, "cases": [
            {
                "context_id": cid, "citing_id": "citing-" + cid,
                "cited_id": "cited-" + cid,
                "split": "test", "context_sha256": sha(texts[cid]),
                "chunks": [
                    {"chunk_id": f"p{i}", "text_sha256": sha(f"{cid}-{i}"),
                     "section": "Methods"} for i in range(1, 4)
                ],
            }
            for cid in ("q1", "q2")
        ],
    }), encoding="utf-8")
    return raw, manifest


def test_acl_official_checks_true_splits_and_hashes(tmp_path):
    raw, manifest = make_acl(tmp_path)
    cases, _ = load_universe(manifest)
    hashes = check_acl_official(cases, raw)
    assert set(hashes) == {"contexts.json", "train.json", "val.json", "test.json"}
    assert all(len(h) == 64 for h in hashes.values())


def test_acl_rejects_manifest_false_test_membership(tmp_path):
    raw, manifest = make_acl(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["cases"][0]["context_id"] = "t1"
    doc["cases"][0]["citing_id"] = "citing-t1"
    doc["cases"][0]["cited_id"] = "cited-t1"
    doc["cases"][0]["context_sha256"] = sha("Training examples TARGETCIT do not overlap.")
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    cases, _ = load_universe(manifest)
    with pytest.raises(ProtocolError, match="split test ACL-200"):
        check_acl_official(cases, raw)


def test_acl_rejects_mismatched_document_pair(tmp_path):
    raw, manifest = make_acl(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["cases"][0]["cited_id"] = "unrelated-paper"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    cases, _ = load_universe(manifest)
    with pytest.raises(ProtocolError, match="identidad de documentos"):
        check_acl_official(cases, raw)


def test_acl_rejects_replaced_context_text_even_when_manifest_structurally_valid(tmp_path):
    raw, manifest = make_acl(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["cases"][0]["context_sha256"] = sha("fabricated TARGETCIT")
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    cases, _ = load_universe(manifest)
    with pytest.raises(ProtocolError, match="SHA de contexto"):
        check_acl_official(cases, raw)


def test_require_acl_official_without_raw_always_blocks_before_gold(tmp_path):
    raw, manifest = make_acl(tmp_path)
    empty = tmp_path / "empty"
    with pytest.raises(ProtocolError, match="--raw-dir"):
        audit(manifest, empty, empty, empty, empty, require_official_splits=True)


def test_acl_invalid_source_fails_not_silently_accepted(tmp_path):
    raw, manifest = make_acl(tmp_path)
    (raw / "test.json").write_text("[]", encoding="utf-8")
    cases, _ = load_universe(manifest)
    with pytest.raises(ProtocolError, match="split test ACL-200"):
        check_acl_official(cases, raw)
