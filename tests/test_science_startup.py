"""M/S readiness must not depend on the experimental global index."""
from unittest.mock import patch
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.app.science_main import app


def test_startup_without_global_index(monkeypatch):
    monkeypatch.delenv('MS_ENABLE_GLOBAL_SEARCH', raising=False)
    monkeypatch.setenv('MS_SEARCH_DIR', '/nonexistent/search-index')
    with patch('src.app.ms_runtime.obtener_servicio', return_value=SimpleNamespace(recuperador=SimpleNamespace(encoder=SimpleNamespace(revision='a' * 40)))), \
         patch('src.app.article_corpus.corpus', return_value=({'documentos': {}}, 'test')):
        with TestClient(app) as client:
            assert client.get('/health/ready').status_code == 200
            state = client.get('/api/analisis-cita-ms/estado').json()
            assert state['modelos_cargados'] is True
            assert state['busqueda_cientifica_disponible'] is False
            assert client.post('/api/analisis-cita-ms/recomendar',
                               json={'contexto': 'Earlier scientific work'}).status_code == 503
    assert app.state.modelos_cargados is False


def test_model_failure_never_becomes_ready(monkeypatch):
    monkeypatch.delenv('MS_ENABLE_GLOBAL_SEARCH', raising=False)
    with patch('src.app.article_corpus.corpus', return_value=({'documentos': {}}, 'test')), \
         patch('src.app.ms_runtime.obtener_servicio', side_effect=RuntimeError('Invalid weights')):
        with pytest.raises(RuntimeError, match='Invalid weights'):
            with TestClient(app):
                pass


def test_bootstrap_downloads_optional_catalog_without_global_flag(monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from scripts.iniciar_ciencia import main
    monkeypatch.setitem(sys.modules, 'boto3', SimpleNamespace(client=lambda *a, **kw: object()))
    monkeypatch.setitem(sys.modules, 'botocore', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'botocore.config', SimpleNamespace(Config=lambda **kw: None))
    monkeypatch.delenv('MS_ENABLE_GLOBAL_SEARCH', raising=False)
    with patch('pathlib.Path.read_text', return_value=json.dumps({'release_id': 'test'})) as read, \
         patch('scripts.iniciar_ciencia.preparar') as prepare, \
         patch('src.app.article_corpus.preparar_corpus_release') as prepare_corpus, \
         patch('os.execvp') as execute:
        main()
    prepare_corpus.assert_called_once()
    assert read.call_count == 2  # M/S plus the optional step-2 index.
    assert prepare.call_count == 2
    execute.assert_called_once()


def test_catalog_download_failure_does_not_stop_ms(monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from scripts.iniciar_ciencia import main
    monkeypatch.setitem(sys.modules, 'boto3', SimpleNamespace(client=lambda *a, **kw: object()))
    monkeypatch.setitem(sys.modules, 'botocore', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'botocore.config', SimpleNamespace(Config=lambda **kw: None))
    monkeypatch.delenv('MS_ENABLE_GLOBAL_SEARCH', raising=False)
    with patch('pathlib.Path.read_text', return_value=json.dumps({'release_id': 'test'})), \
         patch('scripts.iniciar_ciencia.preparar', side_effect=[None, RuntimeError('Offline')]), \
         patch('src.app.article_corpus.preparar_corpus_release'), \
         patch('os.execvp') as execute:
        main()
    execute.assert_called_once()
