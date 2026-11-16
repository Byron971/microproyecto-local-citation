"""La prueba de preflight jamás publica certificado Gold ni inferencia real."""
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.ci.release_readiness import EXPECTED_A4, PENDING_EXTERNAL, readiness, main


def test_inventory_real_repo_sin_pesos_no_certifica():
    from src.app.checkpoint_gate import REPO
    result = readiness(REPO)
    assert result["status"] == "TECHNICAL_INVENTORY_REVIEWED_NOT_FINAL"
    assert set(result["a4_checkpoints"]) == EXPECTED_A4
    assert result["gold_certified"] is False
    assert result["release_ready"] is False
    assert result["ci_workflows_have_executed"] == "NOT_CHECKED_BY_THIS_TOOL"
    assert result["human_chunk_gold_certified"] is False
    assert result["human_nine_class_gold_certified"] is False
    assert "sci_checkpoint_execution" in PENDING_EXTERNAL


def test_require_final_falla_aunque_codigo_exista():
    assert main(["--require-final"]) == 1


def test_faltan_archivos_importantes_falla_cerrado(tmp_path):
    result = readiness(tmp_path)
    assert result["status"] == "ENGINEERING_SOURCES_MISSING"
    assert result["release_ready"] is False
    assert "gold_chunk_gate" in result["missing"]


def test_reporte_json_no_sobrescribe(tmp_path):
    from src.app.checkpoint_gate import REPO
    result = tmp_path / "readiness.json"
    assert main(["--root", str(REPO), "--output", str(result)]) == 0
    assert result.is_file()
