import hashlib
import json
from pathlib import Path
import tarfile
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from scripts.empaquetar_serverless_ms import empaquetar
from scripts.iniciar_serverless_ms import validar
from src.app.serverless_main import app


def inventory(root):
    (root / 'weights.bin').write_bytes(b'fixed model')
    return {'release_id': 'test', 'files': [{'path': 'weights.bin', 'bytes': 11,
            'sha256': hashlib.sha256(b'fixed model').hexdigest()}], 'bucket': 'private', 'prefix': 'release/'}


def test_bundle_is_deterministic_and_only_contains_allowlist(tmp_path):
    manifest = inventory(tmp_path)
    (tmp_path / 'private_gold.json').write_text('never ship')
    first = empaquetar(tmp_path, manifest, tmp_path / 'a.tar.gz')
    second = empaquetar(tmp_path, manifest, tmp_path / 'b.tar.gz')
    assert first['sha256'] == second['sha256']
    with tarfile.open(tmp_path / 'a.tar.gz') as archive:
        assert archive.getnames() == ['weights.bin', 'release.json']
        assert all(item.isfile() for item in archive.getmembers())
        data = json.load(archive.extractfile('release.json'))
        assert 'bucket' not in data and 'prefix' not in data


def test_bundle_rejects_corruption_and_does_not_replace_output(tmp_path):
    manifest = inventory(tmp_path)
    (tmp_path / 'weights.bin').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='SHA256'):
        empaquetar(tmp_path, manifest, tmp_path / 'a.tar.gz')
    assert not (tmp_path / 'a.tar.gz').exists()
    manifest = inventory(tmp_path)
    (tmp_path / 'a.tar.gz').write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        empaquetar(tmp_path, manifest, tmp_path / 'a.tar.gz')
    assert (tmp_path / 'a.tar.gz').read_bytes() == b'keep'


def test_startup_rejects_wrong_or_corrupt_bundle(tmp_path):
    manifest = inventory(tmp_path)
    (tmp_path / 'release.json').write_text(json.dumps({k: v for k, v in manifest.items() if k not in ('bucket', 'prefix')}))
    validar(tmp_path, manifest)
    (tmp_path / 'weights.bin').write_bytes(b'broken')
    with pytest.raises(RuntimeError, match='corrupto'):
        validar(tmp_path, manifest)
    (tmp_path / 'release.json').write_text('{}')
    with pytest.raises(RuntimeError, match='release'):
        validar(tmp_path, manifest)


def test_bundle_rejects_paths_outside_root(tmp_path):
    manifest = inventory(tmp_path)
    manifest['files'][0]['path'] = '../weights.bin'
    with pytest.raises(ValueError, match='Ruta'):
        empaquetar(tmp_path, manifest, tmp_path / 'a.tar.gz')


def test_adapter_preserves_article_and_manual_contracts():
    client = TestClient(app)
    with patch.object(app.state, 'modelos_cargados', False, create=True):
        assert client.get('/ping').status_code == 503
    with patch.object(app.state, 'modelos_cargados', True, create=True):
        assert client.get('/ping').status_code == 200
    with patch('src.app.serverless_main.analizar_articulo', return_value={'article': True}) as article:
        result = client.post('/invocations', json={'paper_id': 'W05-0821', 'contexto': 'Earlier work TARGETCIT.'})
        assert result.status_code == 200 and result.json() == {'article': True}
        assert article.call_args.args[0].paper_id == 'W05-0821'
    fixture = Path('tests/fixtures/ms_sintetico_solicitud.json')
    with patch('src.app.serverless_main.analisis_cita_ms', return_value={'manual': True}):
        assert client.post('/invocations', json=json.loads(fixture.read_text())).json() == {'manual': True}
    assert client.post('/invocations', json={}).status_code == 422
