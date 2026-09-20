import pytest

from src.evaluation.commercial.providers_local import (
    LocalPilotClient,
    LocalProviderNotConfiguredError,
    build_client,
)


def test_build_client_returns_local_pilot_client():
    client = build_client()
    assert isinstance(client, LocalPilotClient)


def test_client_exposes_provider_and_model_strings():
    client = build_client()
    assert isinstance(client.provider, str) and client.provider
    assert isinstance(client.model, str) and client.model


def test_generate_raises_not_configured_error_without_network():
    client = build_client()
    with pytest.raises(LocalProviderNotConfiguredError) as exc_info:
        client.generate("cualquier prompt")
    assert "proveedor" in str(exc_info.value).lower()
