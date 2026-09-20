import json

from src.evaluation.commercial.cli import main


class _BrokenClient:
    """Simula un cliente cuyo `generate()` falla por falta de configuracion
    (p.ej. OpenAIProviderNotConfiguredError), no por un error de proveedor
    transitorio: run_evaluation no lo captura y deberia propagar hasta el
    manejo de errores de configuracion de la CLI."""

    provider = "broken"
    model = "broken-model"

    def generate(self, prompt: str):
        raise RuntimeError("proveedor no configurado (simulado)")


def _broken_client_factory() -> _BrokenClient:
    return _BrokenClient()


def test_cli_check_only_validates_gold_and_prompts(tmp_path, capsys):
    gold = tmp_path / "gold.jsonl"
    prompts = tmp_path / "prompts.json"
    gold.write_text('{"id":"c1","input":"text","gold":"A"}\n', encoding="utf-8")
    prompts.write_text(json.dumps({"zero": "Classify {input}"}), encoding="utf-8")

    code = main(["--gold", str(gold), "--prompts", str(prompts), "--check-only"])

    assert code == 0
    out = capsys.readouterr().out
    assert "1 casos" in out
    assert "1 prompts" in out


def test_cli_requires_at_least_one_client_for_execution(tmp_path, capsys):
    gold = tmp_path / "gold.jsonl"
    prompts = tmp_path / "prompts.json"
    gold.write_text('{"id":"c1","input":"text","gold":"A"}\n', encoding="utf-8")
    prompts.write_text(json.dumps({"zero": "Classify {input}"}), encoding="utf-8")

    code = main(["--gold", str(gold), "--prompts", str(prompts)])

    assert code == 2
    assert "--client" in capsys.readouterr().err


def test_cli_reports_clean_error_when_client_raises_runtime_error(tmp_path, capsys):
    gold = tmp_path / "gold.jsonl"
    prompts = tmp_path / "prompts.json"
    gold.write_text('{"id":"c1","input":"text","gold":"A"}\n', encoding="utf-8")
    prompts.write_text(json.dumps({"zero": "Classify {input}"}), encoding="utf-8")

    code = main(
        [
            "--gold",
            str(gold),
            "--prompts",
            str(prompts),
            "--client",
            "test_commercial_cli:_broken_client_factory",
        ]
    )

    assert code == 2
    assert "Error de configuración" in capsys.readouterr().err
