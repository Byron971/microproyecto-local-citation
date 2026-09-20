from pathlib import Path

from src.evaluation.commercial import orchestrate


def test_resolve_gold_prefers_explicit_path():
    assert orchestrate.resolve_gold("custom.jsonl") == Path("custom.jsonl")


def test_is_provisional_gold_by_filename():
    assert orchestrate.is_provisional_gold("x/provisional_test_gold.jsonl")
    assert not orchestrate.is_provisional_gold("x/test_gold.jsonl")


def test_validate_environment_reports_missing_values(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENWEIGHT_MODEL", raising=False)

    errors = orchestrate.validate_environment("both")

    assert any("OPENAI_API_KEY" in error for error in errors)
    assert any("OPENWEIGHT_MODEL" in error for error in errors)


def test_validate_environment_accepts_configured_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setenv("OPENWEIGHT_MODEL", "local-model")

    assert orchestrate.validate_environment("both") == []


def test_build_clients_uses_environment_model_names(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "commercial-model")
    monkeypatch.setenv("OPENWEIGHT_MODEL", "local-model")

    clients = orchestrate.build_clients("both")

    assert [(client.provider, client.model) for client in clients] == [
        ("openai", "commercial-model"),
        ("openweight", "local-model"),
    ]
