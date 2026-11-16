"""Readiness de entrega: inventario reproducible, sin Gold, API ni AWS.

Ejecución CI NO equivale a certificación científica. Los controles de inferencia,
anotación humana, despliegue y rúbrica permanecen explícitamente pendientes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.app.checkpoint_gate import REPO, verificar_registro


ENGINEERING_FILES = {
    "split_acl200": "proyecto_de_grado/src/data/validar_splits.py",
    "gold_nine_class_gate": "src/evaluation/commercial/gold_freeze_audit.py",
    "gold_chunk_gate": "proyecto_de_grado/src/evaluation/top3_gold_gate.py",
    "top3_human_calibration": "proyecto_de_grado/src/evaluation/top3_humano.py",
    "paired_factorial": "src/evaluation/commercial/a4_factorial_benchmark.py",
    "science_preflight": "src/app/science_preflight.py",
    "science_smoke": "scripts/ci/smoke_tesis.py",
    "api_integration_ci": ".github/workflows/fullstack-e2e.yml",
    "react_ci": ".github/workflows/frontend.yml",
    "scientific_cpu_ci": ".github/workflows/science-image-build.yml",
    "terraform_ci": ".github/workflows/terraform.yml",
    "science_docker": "Dockerfile.science",
    "manuscript_draft": "proyecto_de_grado/docs/articulo_metodologia_borrador_sin_gold_2026_11.md",
}
EXPECTED_A4 = {"scibert_A_42", "scibert_B_42", "specter_A_42", "specter_B_42"}
PENDING_EXTERNAL = {
    "human_nine_class_gold": "Dos etiquetas independientes, consenso/adjudicación, 15% y acta #98-100",
    "human_chunk_relevance": "Juicios ciegos de TODOS los chunks y Gold de fragmentos #127",
    "heldout_eligibility": "Conciliar manifiestos, versiones y muestras no usadas para tuning",
    "sci_checkpoint_execution": "Recuperar cuatro checkpoints A4 auténticos y ejecutar inferencias reales",
    "experiment_matrix": "Validar 2x2 SciBERT/SPECTER A/B y ablaciones sobre el MISMO Gold #103/#128",
    "commercial_costs_and_inference": "Autorización de APIs, trazas reales y precios fechados #105/#106",
    "https_aws": "Autorización, prueba de endpoints HTTPS y costos AWS observados #116",
    "quantitative_results": "Evaluación final, comparaciones pareadas, error y métricas #109/#110",
    "article_and_defense": "Citas IEEE verificadas, revisión autores, resultados, PDF <=12 pp y sustentación #112-123",
}


def readiness(root: Path = REPO, *, checkpoint_base: Path | None = None) -> dict:
    root = Path(root)
    files = {key: (root / path).is_file() for key, path in ENGINEERING_FILES.items()}
    if not all(files.values()):
        missing = sorted(key for key, found in files.items() if not found)
        return {"status": "ENGINEERING_SOURCES_MISSING", "missing": missing,
                "files_present": files, "gold_certified": False, "release_ready": False}
    registered = verificar_registro(
        registro=root / "config/checkpoint_registry.json",
        base=checkpoint_base,
        repo=root,
    )
    ids = {row["id"] for row in registered["models"]}
    if ids != EXPECTED_A4:
        return {"status": "EXPERIMENT_REGISTRY_INCOMPLETE",
                "ids_observed": sorted(ids), "ids_expected": sorted(EXPECTED_A4),
                "gold_certified": False, "release_ready": False}
    model_status = {item["id"]: item["status"] for item in registered["models"]}
    return {
        "status": "TECHNICAL_INVENTORY_REVIEWED_NOT_FINAL",
        "engineering_sources": files,
        "a4_manifest_integrity": True,
        "a4_checkpoints": model_status,
        "a4_checkpoints_all_sha_verified": registered["ready"],
        "ci_workflows_have_executed": "NOT_CHECKED_BY_THIS_TOOL",
        "http_e2e_executed": "NOT_CHECKED_BY_THIS_TOOL",
        "science_smoke_executed": "NOT_CHECKED_BY_THIS_TOOL",
        "terraform_apply_executed": False,
        "human_nine_class_gold_certified": False,
        "human_chunk_gold_certified": False,
        "gold_certified": False,
        "release_ready": False,
        "pending_external_and_manual": PENDING_EXTERNAL,
        "note": ("Este informe valida existencia de código y coherencia SHA histórica. "
                 "El pase de tests sintéticos NO certifica datos humanos, modelos cargados, "
                 "independencia experimental, cifras, DOI ni servicios AWS."),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--checkpoint-base", type=Path,
                   help="Directorio privado con checkpoints de corridas originales, opcional")
    p.add_argument("--output", type=Path, help="JSON nuevo: no sobrescribir")
    p.add_argument("--require-final", action="store_true",
                   help="Exit 1 mientras falten certificaciones humanas/externas")
    a = p.parse_args(argv)
    try:
        doc = readiness(a.root, checkpoint_base=a.checkpoint_base)
        if a.output:
            a.output.parent.mkdir(parents=True, exist_ok=True)
            with a.output.open("x", encoding="utf-8") as out:
                json.dump(doc, out, indent=2, ensure_ascii=False)
                out.write("\n")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        p.exit(2, f"Readiness bloqueado: {exc}\n")
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    if doc["status"] != "TECHNICAL_INVENTORY_REVIEWED_NOT_FINAL":
        return 2
    return 1 if a.require_final and not doc["release_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
