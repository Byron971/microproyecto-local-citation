"""Gate #119: las evidencias CI locales no habilitan entrega de URL pública."""
import json

import pytest

from scripts.validar_paquete_entrega import (
    REPO_URL, REQUIRED_CHECKS, audit_manifest, main, read_manifest,
    report_markdown, validate_external_url,
)

TEAM = ["John", "Caicedo", "Zambrana", "Duque", "Pinzón"]


def manifest():
    return {
        "project_title": "Proyecto de grado PLN",
        "team": TEAM,
        "repository_url": REPO_URL,
        "application_url": None,
        "api_url": None,
        "reviewer_access_instructions": "PENDIENTE",
        "external_validation": {"performed": False},
        "evidence": {"docker_ci_url": REPO_URL + "/actions/runs/41959273085"},
        "expected_final_features": {
            "scibert_top3_required": True,
            "nine_function_classifier_required": True,
        },
    }


@pytest.mark.parametrize("url", [
    "http://example.com",
    "http://localhost:8080",
    "https://localhost",
    "https://127.0.0.1",
    "https://10.0.0.1",
    "https://192.168.1.25",
    "https://169.254.7.1",
    "https://internal.local",
    "https://dev.internal",
    "https://private.test",
    "https://sub.example",
    "https://service.invalid",
    "https://user:password@service.example.com",
    "https://api.service.com/?token=abc",
    "https://api.service.com/path",
    "https://api.service.com/#fragment",
    "https://api.service.com:99999",
    "https://",
    "not a url",
])
def test_disallow_local_insecure_and_credential_urls(url):
    with pytest.raises(ValueError):
        validate_external_url(url, "application_url")


@pytest.mark.parametrize("url", [
    "https://demo.universidad.edu.co",
    "https://api.mi-dominio.co:8443",
])
def test_allow_https_public_candidates_but_not_claim_reachability(url):
    assert validate_external_url(url, "api_url") == url


def test_defaults_block_final_delivery_even_with_existing_ci():
    result = audit_manifest(manifest())
    assert result["status"] == "NO_APTO_PARA_ENTREGA_FINAL"
    assert result["manifest_is_not_proof"] is True
    assert any("externa" in b for b in result["blockers"])
    assert any("smoke externo" in b for b in result["blockers"])
    assert "NO_APTO" in report_markdown(result)


def test_duplicate_team_members_rejected():
    data = manifest()
    data["team"] = ["john", "JOHN", "José", "Gabriel", "Carlos"]
    assert any("cinco integrantes" in b for b in audit_manifest(data)["blockers"])


def test_ci_local_not_external_evidence_even_when_links_are_https():
    data = manifest()
    data["application_url"] = "https://demo.universidad.edu.co"
    data["api_url"] = "https://api.universidad.edu.co"
    data["reviewer_access_instructions"] = "Abrir demo sin clave y probar Top-3"
    result = audit_manifest(data)
    assert any("independiente" in b for b in result["blockers"])
    assert any("CI" in msg for msg in result["warnings"])


def test_forged_manual_check_without_evidence_is_not_enough():
    data = manifest()
    data["application_url"] = "https://demo.universidad.edu.co"
    data["api_url"] = "https://api.universidad.edu.co"
    data["reviewer_access_instructions"] = "Ingreso por HTTPS"
    data["external_validation"] = {
        "performed": True,
        "observer": "Verificador",
        "checked_at_utc": "2026-11-04T20:00:00Z",
        "proof_url": "https://evil.com/test",
    }
    result = audit_manifest(data)
    assert any("evidencia externa" in b for b in result["blockers"])
    assert any("smoke externo" in b for b in result["blockers"])


def test_external_baseline_smoke_does_not_complete_scientific_final_models():
    data = manifest()
    data["application_url"] = "https://demo.universidad.edu.co"
    data["api_url"] = "https://api.universidad.edu.co"
    data["reviewer_access_instructions"] = "Abrir demo"
    data["external_validation"] = {
        "performed": True,
        "observer": "Docente",
        "checked_at_utc": "2026-11-04T20:00:00Z",
        "proof_url": REPO_URL + "/issues/119#issuecomment-123",
    }
    smoke = {
        "status": "ok", "checks": [{"name": name, "status": 200} for name in REQUIRED_CHECKS],
    }
    result = audit_manifest(data, external_probe=smoke)
    assert result["status"] == "NO_APTO_PARA_ENTREGA_FINAL"
    assert any("SciBERT" in x for x in result["blockers"])
    assert not any("smoke externo incompleto" in x for x in result["blockers"])


def test_fails_if_external_smoke_does_not_cover_required_checks():
    result = audit_manifest(manifest(), external_probe={"status": "ok", "checks": []})
    assert any("incompleto" in x for x in result["blockers"])


def test_cli_writes_draft_and_strict_refuses_claim(tmp_path):
    data = tmp_path / "manifest.json"
    data.write_text(json.dumps(manifest()), encoding="utf-8")
    out = tmp_path / "report"
    assert main(["--manifest", str(data), "--output-dir", str(out)]) == 0
    assert main(["--manifest", str(data), "--output-dir", str(out), "--strict"]) == 2
    assert (out / "auditoria.json").exists()
    assert "PENDIENTE" in (out / "borrador_entrega.md").read_text(encoding="utf-8")
    assert "NO_APTO_PARA_ENTREGA_FINAL" in (out / "auditoria.json").read_text(encoding="utf-8")


def test_manifest_example_is_structurally_sound():
    doc = read_manifest(__import__("pathlib").Path("config/entrega_despliegue.example.json"))
    assert len(doc["team"]) == 5
    assert doc["application_url"] is None
    assert doc["api_url"] is None
    assert doc["repository_url"] == REPO_URL
