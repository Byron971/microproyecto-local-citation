"""Contratos de documentación G0/G1: los ejemplos no deben eludir Gold."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CLI = "uv run python -m src.evaluation.commercial.orchestrate"


def _commands(relative):
    text = (ROOT / relative).read_text(encoding="utf-8")
    blocks = re.findall(r"```(?:bash|powershell)\\?\n([\s\S]*?)```", text)
    return [block for block in blocks if CLI in block]


def test_instrucciones_de_gold_siempre_especifican_archivo():
    for relative in ("README.md", "docs/evaluacion_comercial.md"):
        commands = _commands(relative)
        assert commands, f"No hay comandos documentados: {relative}"
        for command in commands:
            assert "--gold " in command, (
                f"Un ejemplo de {relative} omite --gold y fallara al ejecutar."
            )
            if "--check-only" not in command:
                assert "--allow-provisional" in command, (
                    f"{relative} promete una corrida real sin advertir que "
                    "la evaluacion final esta bloqueada."
                )


def test_la_documentacion_ya_no_presenta_piloto_como_gold_final():
    for path in ("README.md", "docs/evaluacion_comercial.md"):
        s = (ROOT / path).read_text(encoding="utf-8")
        assert "test_gold.jsonl" in s
        assert "histórico" in s.lower() or "historico" in s.lower()
        assert "no" in s.lower() and "final" in s.lower()


def test_guia_reproduccion_no_asume_origin_de_un_fork():
    s = (ROOT / "proyecto_de_grado/docs/guia_reproduccion_equipo_g1_3.md").read_text(encoding="utf-8")
    assert "git fetch origin" not in s
    assert "git fetch https://github.com/Byron971/microproyecto-local-citation.git" in s


def test_sesgo_multicita_registrado_como_evidencia_no_validada():
    s = (ROOT / "proyecto_de_grado/docs/politica_evaluacion_g0.md").read_text(encoding="utf-8")
    assert "44,7 %" in s
    assert "pendientes de reproducción versionada" in s
    assert "con y sin" in s
