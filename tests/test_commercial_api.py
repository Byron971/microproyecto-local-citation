import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.app import commercial_router as commercial
from src.evaluation.commercial.schema import ProviderResponse


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(commercial.router)
    monkeypatch.setenv('CITAS_COMMERCIAL_ENABLED', '1')
    monkeypatch.setenv('CITAS_COMMERCIAL_VISIBLE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-unit-key')
    monkeypatch.setenv('CITAS_COMMERCIAL_LIMIT_TABLE', 'unit-table')
    monkeypatch.setattr(commercial, 'reserve_call', Mock())
    from src.evaluation.commercial import providers_openai
    response = ProviderResponse('[0.1,0,0,0,0.8,0,0,0,0]', 100, 20, 'gpt-6.1-sol')
    fake = Mock(return_value=SimpleNamespace(generate=Mock(return_value=response)))
    monkeypatch.setattr(providers_openai, 'OpenAIClient', fake)
    return TestClient(app), fake


def payload(**overrides):
    return {'paper_id': 'W05-0821', 'contexto': 'We use TARGETCIT in our system.',
            'consentimiento': True, **overrides}


def test_disabled_hidden_and_no_call(client, monkeypatch):
    http, provider = client
    monkeypatch.delenv('OPENAI_API_KEY')
    assert [m['id'] for m in http.get('/api/clasificadores').json()['clasificadores']] == ['M', 'S']
    assert http.post('/api/comercial/clasificar', json=payload()).status_code == 503
    provider.assert_not_called()


@pytest.mark.parametrize('bad,code', [({'consentimiento': False}, 422), ({'contexto': 'unmarked'}, 422),
                                     ({'paper_id': 'W05-9999'}, 404)])
def test_invalid_requests_never_consume_quota(client, bad, code):
    http, provider = client
    assert http.post('/api/comercial/clasificar', json=payload(**bad)).status_code == code
    commercial.reserve_call.assert_not_called()
    provider.assert_not_called()


def test_real_contract_reuses_profile_and_identity(client):
    http, provider = client
    response = http.post('/api/comercial/clasificar', json=payload())
    assert response.status_code == 200
    data = response.json()
    assert data['clase'] == 'Application'
    assert data['modelo_efectivo'] == data['modelo_solicitado'] == 'gpt-6.1-sol'
    assert data['tipo_puntuacion'] == 'puntajes_generados_no_calibrados'
    assert len(data['puntuaciones']) == 9
    provider.assert_called_once_with('gpt-6.1-sol', timeout_seconds=20, max_completion_tokens=1024)
    commercial.reserve_call.assert_called_once()
    prompt = provider.return_value.generate.call_args.args[0]
    template = json.loads(commercial.PROMPTS.read_text())['zero_shot_detailed']
    assert prompt.startswith(template.split('{input}')[0])
    assert 'Citation context: We use TARGETCIT' in prompt
    assert 'Cited paper title:' in prompt and 'Cited paper abstract:' in prompt
    assert 'fake-unit-key' not in response.text


@pytest.mark.parametrize('text,model', [('not json', 'gpt-6.1-sol'), ('[1,2]', 'gpt-6.1-sol'),
                                      ('[1,0,0,0,0,0,0,0,0]', None), ('[1,0,0,0,0,0,0,0,0]', 'other-model')])
def test_parse_or_identity_errors_are_not_predictions(client, text, model):
    http, provider = client
    provider.return_value.generate.return_value = ProviderResponse(text, model=model)
    response = http.post('/api/comercial/clasificar', json=payload())
    assert response.status_code == 502
    assert 'clase' not in response.json()
    provider.return_value.generate.assert_called_once()


def test_tied_scores_abstain_without_inventing_probabilities(client):
    http, provider = client
    provider.return_value.generate.return_value = ProviderResponse('[0.5,0.5,0,0,0,0,0,0,0]', model='gpt-6.1-sol')
    data = http.post('/api/comercial/clasificar', json=payload()).json()
    assert data['clase'] is None and data['abstencion']
    assert data['puntuaciones'][0]['valor'] == .5


def test_limit_blocks_provider_and_errors_are_sanitized(client):
    http, provider = client
    commercial.reserve_call.side_effect = HTTPException(429, 'Límite diario')
    assert http.post('/api/comercial/clasificar', json=payload()).status_code == 429
    provider.assert_not_called()
    commercial.reserve_call.side_effect = None
    provider.return_value.generate.side_effect = RuntimeError('secret-provider-details')
    response = http.post('/api/comercial/clasificar', json=payload())
    assert response.status_code == 502 and 'secret-provider-details' not in response.text


def test_preparation_does_not_advertise_commercial(client, monkeypatch):
    http, _ = client
    monkeypatch.setenv('CITAS_COMMERCIAL_VISIBLE', '0')
    assert all(m['id'] != 'commercial' for m in http.get('/api/clasificadores').json()['clasificadores'])


def test_atomic_limit_and_fail_closed(monkeypatch):
    import boto3
    from botocore.exceptions import ClientError
    monkeypatch.setenv('CITAS_COMMERCIAL_LIMIT_TABLE', 'unit-table')
    monkeypatch.setenv('CITAS_COMMERCIAL_DAILY_LIMIT', '10')
    db = Mock()
    monkeypatch.setattr(boto3, 'client', Mock(return_value=db))
    commercial.reserve_call()
    args = db.update_item.call_args.kwargs
    assert args['TableName'] == 'unit-table'
    assert args['ConditionExpression'] == 'attribute_not_exists(#calls) OR #calls < :limit'
    assert args['ExpressionAttributeValues'][':limit'] == {'N': '10'}
    assert args['Key']['id']['S'].startswith('openai:')
    for code, status in [('ConditionalCheckFailedException', 429), ('AccessDeniedException', 503)]:
        db.update_item.side_effect = ClientError({'Error': {'Code': code}}, 'UpdateItem')
        with pytest.raises(HTTPException) as error:
            commercial.reserve_call()
        assert error.value.status_code == status
