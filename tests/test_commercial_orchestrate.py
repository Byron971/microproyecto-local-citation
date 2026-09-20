from pathlib import Path

from src.evaluation.commercial import orchestrate


def test_resolve_gold_prefers_explicit_path():
    assert orchestrate.resolve_gold("custom.jsonl") == Path("custom.jsonl")


def test_is_provisional_gold_by_filename():
    assert orchestrate.is_provisional_gold("x/provisional_test_gold.jsonl")
    assert not orchestrate.is_provisional_gold("x/test_gold.jsonl")


def test_validate_environment_reports_missing_values(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "COHERE_API_KEY",
        "OPENWEIGHT_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    errors = orchestrate.validate_environment("all")

    assert any("OPENAI_API_KEY" in error for error in errors)
    assert any("GEMINI_API_KEY" in error for error in errors)
    assert any("GEMINI_MODEL" in error for error in errors)
    assert any("OPENWEIGHT_MODEL" in error for error in errors)


def test_validate_environment_accepts_commercial_configuration(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-model")

    assert orchestrate.validate_environment("commercial") == []


def test_build_clients_for_commercial_mode(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "openai-model")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-model")

    clients = orchestrate.build_clients("commercial")

    assert [(client.provider, client.model) for client in clients] == [
        ("openai", "openai-model"),
        ("gemini", "gemini-model"),
    ]


def test_build_clients_for_all_mode(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "openai-model")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-model")
    monkeypatch.setenv("OPENWEIGHT_MODEL", "local-model")

    clients = orchestrate.build_clients("all")

    assert [(client.provider, client.model) for client in clients] == [
        ("openai", "openai-model"),
        ("gemini", "gemini-model"),
        ("openweight", "local-model"),
    ]


def test_validate_environment_reports_missing_cohere_key(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    errors = orchestrate.validate_environment("cohere")
    assert any("COHERE_API_KEY" in error for error in errors)


def test_build_clients_for_cohere_mode(monkeypatch):
    monkeypatch.setenv("COHERE_MODEL", "cohere-model")
    clients = orchestrate.build_clients("cohere")
    assert [(client.provider, client.model) for client in clients] == [
        ("cohere", "cohere-model"),
    ]
