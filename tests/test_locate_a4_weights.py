"""Descubrimiento A4 SHA: 100% sintético, sin snapshots ni pesos auténticos."""
import hashlib
import json

import pytest

from scripts.locate_a4_weights import locate, main


ARMS = (
    ("scibert_A_42", "scibert", "A"),
    ("scibert_B_42", "scibert", "B"),
    ("specter_A_42", "specter", "A"),
    ("specter_B_42", "specter", "B"),
)


@pytest.fixture
def repository(tmp_path):
    files = {}
    models = []
    for name, encoder, variant in ARMS:
        # No resemblance to a real neural model checkpoint.
        payload = f"SYNTHETIC_TEST_ARTIFACT_{name}".encode("ascii")
        checksum = hashlib.sha256(payload).hexdigest()
        manifest = tmp_path / "manifests" / (name + ".json")
        manifest.parent.mkdir(exist_ok=True)
        manifest.write_text(json.dumps({
            "encoder": encoder, "entrada": variant, "semilla": 42,
            "training_labels": "Haiku", "checkpoint_sha256": checksum,
        }), encoding="utf-8")
        models.append({
            "id": name, "encoder": encoder, "entrada": variant, "semilla": 42,
            "checkpoint": f"{name}/model.safetensors",
            "source_manifest": f"manifests/{name}.json",
            "expected_sha256": checksum, "training_labels": "Haiku",
            "validation": "provisional_not_gold",
        })
        files[name] = payload
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "version": 1, "root": "missing_original_run",
        "models": models,
    }), encoding="utf-8")
    scan_root = tmp_path / "backup"
    scan_root.mkdir()
    return tmp_path, registry, scan_root, files


def verify(repo, registry, scan_root, **kwargs):
    return locate([scan_root], registry=registry, repo=repo, **kwargs)


def test_four_models_identified_by_bytes_not_filenames(repository):
    repo, registry, root, files = repository
    for i, (model, payload) in enumerate(files.items()):
        folder = root / f"unrelated-archive-{i}"
        folder.mkdir()
        (folder / f"renamed_{i}.safetensors").write_bytes(payload)
    result = verify(repo, registry, root, show_paths=True)
    assert result["all_four_found"] is True
    assert result["search_complete"] is True
    assert result["verified_model_count"] == 4
    assert all(item["number_of_matching_files"] == 1 for item in result["models"])
    assert all(item["local_paths"] for item in result["models"])
    assert result["weights_loaded_in_torch"] is False
    assert result["human_gold_certified"] is False


def test_missing_checkpoint_never_reported_as_available(repository):
    repo, registry, root, files = repository
    (root / "specter_A_42.safetensors").write_bytes(files["specter_A_42"])
    (root / "scibert_B_42.safetensors").write_bytes(b"wrong-checkpoint-content")
    result = verify(repo, registry, root)
    assert result["all_four_found"] is False
    assert result["verified_model_count"] == 1
    assert all("local_paths" not in row for row in result["models"])
    assert next(x for x in result["models"] if x["id"] == "scibert_B_42")["status"] == "not_found"


def test_scan_does_not_follow_symlinks(repository):
    repo, registry, root, files = repository
    other = repo / "external"
    other.mkdir()
    (other / "sci.safetensors").write_bytes(files["scibert_A_42"])
    try:
        (root / "shortcut").symlink_to(other, target_is_directory=True)
        (root / "fake.safetensors").symlink_to(other / "sci.safetensors")
    except (OSError, NotImplementedError):
        pytest.skip("Filesystem does not support symlinks")
    result = verify(repo, registry, root, show_paths=True)
    assert result["verified_model_count"] == 0
    assert result["symlinks_skipped"] >= 2


def test_budget_reports_incomplete_search_as_failure(repository):
    repo, registry, root, files = repository
    (root / "a.safetensors").write_bytes(files["scibert_A_42"])
    (root / "b.safetensors").write_bytes(files["scibert_B_42"])
    result = verify(repo, registry, root, max_candidates=1)
    assert result["search_complete"] is False
    assert result["stopped_by_candidate_budget"] is True
    assert result["candidate_safetensors_hashed"] == 1
    assert result["all_four_found"] is False


def test_depth_boundary_and_duplicate_roots(repository):
    repo, registry, root, files = repository
    nested = root / "one" / "two"
    nested.mkdir(parents=True)
    (nested / "model.safetensors").write_bytes(files["specter_A_42"])
    shallow = locate([root, root], registry=registry, repo=repo, max_depth=1)
    assert shallow["roots_count"] == 1
    assert shallow["verified_model_count"] == 0
    deep = verify(repo, registry, root, max_depth=2)
    assert deep["verified_model_count"] == 1


def test_registry_tampering_or_missing_root_rejected(repository):
    repo, registry, root, files = repository
    with pytest.raises(ValueError, match="raíz"):
        locate([], registry=registry, repo=repo)
    doc = json.loads(registry.read_text(encoding="utf-8"))
    doc["models"][0]["expected_sha256"] = "0" * 64
    registry.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA histórico"):
        verify(repo, registry, root)


def test_cli_never_overwrites_report_and_exposes_missing(capsys, tmp_path, monkeypatch):
    from scripts import locate_a4_weights as cli
    reports = []
    def mock_locate(*args, **kwargs):
        reports.append(kwargs)
        return {
            "all_four_found": False,
            "file_read_errors": 0,
            "stopped_by_candidate_budget": False,
            "human_gold_certified": False,
        }
    monkeypatch.setattr(cli, "locate", mock_locate)
    output = tmp_path / "scan.json"
    assert main(["--roots", str(tmp_path), "--report", str(output)]) == 1
    assert json.loads(output.read_text())["all_four_found"] is False
    with pytest.raises(SystemExit) as error:
        main(["--roots", str(tmp_path), "--report", str(output)])
    assert error.value.code == 2
