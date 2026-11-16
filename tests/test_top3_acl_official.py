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



def test_ocl_chunk_universe_matches_original_document_and_rejects_forgery(tmp_path):
    from proyecto_de_grado.src.evaluation.top3_gold_gate import check_ocl_chunks
    from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar

    raw, manifest = make_acl(tmp_path)
    source = json.loads(manifest.read_text(encoding="utf-8"))
    ocl = tmp_path / "ocl-cache"
    ocl.mkdir()
    for case in source["cases"]:
        cited = case["cited_id"]
        paragraphs = [
            {"numero": i, "texto": f"Academic evidence {cited} {i}.",
             "seccion": ("Introduction", "Methods", "Results")[i]}
            for i in range(3)
        ]
        (ocl / (cited + ".json")).write_text(json.dumps({
            "paper_id": cited,
            "pdf_parse": {"body_text": [
                {"text": p["texto"], "section": p["seccion"]}
                for p in paragraphs
            ]},
        }), encoding="utf-8")
        chunks = fragmentar(paragraphs)
        case["chunks"] = [
            {
                "chunk_id": chunk["chunk_id"],
                "text_sha256": sha(chunk["texto"]),
                "section": chunk["seccion"],
            }
            for chunk in chunks
        ]
    manifest.write_text(json.dumps(source), encoding="utf-8")
    cases, universe = load_universe(manifest)
    report = check_ocl_chunks(cases, ocl)
    assert report["documents_checked"] == 2
    assert len(report["source_registry_sha256"]) == 64
    assert len(universe) == 6

    tampered = json.loads(manifest.read_text())
    tampered["cases"][0]["chunks"][0]["text_sha256"] = sha("fake chunk")
    manifest.write_text(json.dumps(tampered))
    cases, _ = load_universe(manifest)
    with pytest.raises(ProtocolError, match="contradice el OCL V1"):
        check_ocl_chunks(cases, ocl)

    tampered["cases"][0]["chunks"][0]["text_sha256"] = source["cases"][0]["chunks"][0]["text_sha256"]
    tampered["cases"][0]["chunks"].pop()
    manifest.write_text(json.dumps(tampered))
    cases, _ = load_universe(manifest)
    with pytest.raises(ProtocolError, match="universo de chunks no es completo"):
        check_ocl_chunks(cases, ocl)


def test_gold_final_requires_ocl_cache_before_opening_private_judgments(tmp_path):
    raw, manifest = make_acl(tmp_path)
    with pytest.raises(ProtocolError, match="--ocl-cache"):
        audit(manifest, tmp_path / "missing.csv", tmp_path / "missing.csv",
              tmp_path / "missing.csv", tmp_path / "missing.csv",
              require_ocl=True)
