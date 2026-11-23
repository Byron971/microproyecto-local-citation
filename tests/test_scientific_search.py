import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np
import pytest

from src.app.scientific_search import ArticleSearch, PROFILE, MODEL_ID
from src.app.ms_router import router
from src.app.ms_lock import LOCK


class Encoder:
    revision = 'a' * 40
    def encode(self, texts):
        assert texts == ['scientific query']
        return [[1., 0.] + [0.] * 766]


def make_index(tmp_path):
    # The semantic match is deliberately last in metadata order.
    papers = [{'paper_id': x, 'titulo': x, 'resumen': 'Invented abstract'} for x in ['P14-0002', 'P14-0001', 'P14-0003']]
    (tmp_path / 'papers.json').write_text(json.dumps(papers))
    vectors = np.zeros((3, 768), dtype=np.float32)
    vectors[0, 1] = vectors[1, 1] = vectors[2, 0] = 1.
    np.save(tmp_path / 'embeddings.npy', vectors)
    meta = {'perfil': PROFILE, 'revision_scibert': Encoder.revision, 'dimension': 768,
            'total_articulos': 3, 'files': {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
            for name in ['papers.json', 'embeddings.npy']}}
    (tmp_path / 'indice.json').write_text(json.dumps(meta))
    return ArticleSearch(tmp_path, Encoder())


def test_semantic_ranking_and_deterministic_ties(tmp_path):
    search = make_index(tmp_path)
    result = search.recommend('scientific TARGETCIT query', 3)
    assert [r['paper_id'] for r in result['recomendaciones']] == ['P14-0003', 'P14-0001', 'P14-0002']
    assert result['modelo'] == MODEL_ID and result['total_catalogo'] == 3
    assert result['recomendaciones'][0]['similitud'] == 1.
    assert all('similitud_tfidf' not in r for r in result['recomendaciones'])
    with pytest.raises(ValueError):
        search.recommend(' TARGETCIT OTHERCIT ', 3)


def test_index_hash_corruption_rejected(tmp_path):
    make_index(tmp_path)
    (tmp_path / 'papers.json').write_text('[]')
    with pytest.raises(ValueError, match='SHA256'):
        ArticleSearch(tmp_path, Encoder())


def test_api_science_catalog_and_no_silent_fallback(tmp_path):
    app = FastAPI(); app.include_router(router)
    client = TestClient(app)
    assert client.post('/api/analisis-cita-ms/recomendar', json={'contexto': 'scientific query'}).status_code == 503
    app.state.article_search = make_index(tmp_path)
    catalog = client.get('/api/analisis-cita-ms/modelos').json()
    assert catalog['predeterminado'] == MODEL_ID
    assert catalog['modelos'][0]['disponible'] and not catalog['modelos'][0]['devuelve_tfidf']
    response = client.post('/api/analisis-cita-ms/recomendar', json={'contexto': 'scientific query', 'top_k': 1})
    assert response.status_code == 200 and response.json()['recomendaciones'][0]['paper_id'] == 'P14-0003'
    for payload, status in [({'contexto': 'scientific query', 'modelo': 'old-model'}, 404),
                            ({'contexto': 'TARGETCIT'}, 422), ({'contexto': 'x', 'top_k': 21}, 422)]:
        assert client.post('/api/analisis-cita-ms/recomendar', json=payload).status_code == status


def test_search_rejects_concurrent_inference(tmp_path):
    app = FastAPI(); app.include_router(router); app.state.article_search = make_index(tmp_path)
    started, release = threading.Event(), threading.Event()
    def hold():
        with LOCK:
            started.set(); release.wait(5)
    thread = threading.Thread(target=hold); thread.start()
    try:
        assert started.wait(2)
        response = TestClient(app).post('/api/analisis-cita-ms/recomendar', json={'contexto': 'scientific query'})
        assert response.status_code == 429 and response.headers['Retry-After'] == '5'
    finally:
        release.set(); thread.join(2)


def test_public_default_routes_use_scibert(tmp_path, monkeypatch):
    from src.app.science_main import app
    monkeypatch.setattr(app.state, 'article_search', make_index(tmp_path), raising=False)
    client = TestClient(app)  # Unit test without loading model lifespan.
    assert client.get('/api/modelos').json()['predeterminado'] == MODEL_ID
    response = client.post('/api/recomendar', json={'contexto': 'scientific query', 'top_k': 2})
    assert response.status_code == 200 and response.json()['modelo'] == MODEL_ID


def test_prepared_index_matches_corpus_without_loading_models():
    from src.app.article_corpus import corpus
    from src.app.scientific_search import prepared_article_search
    metadata = json.loads(Path('config/prepared_article_search/indice.json').read_text())
    search = prepared_article_search(SimpleNamespace(revision=metadata['revision_scibert']))
    data, version = corpus()
    assert set(search.ids) == set(data['documentos'])
    assert search.metadata['version_contenido'] == version
    assert len(search.papers) == 37
    assert all(' '.join(data['documentos'][p['paper_id']]['abstract'].split()) == p['resumen'] for p in search.papers)


def test_search_startup_failure_does_not_break_ms(monkeypatch):
    import sys
    from src.app import scientific_search, science_main
    monkeypatch.delenv('MS_ENABLE_GLOBAL_SEARCH', raising=False)
    monkeypatch.setitem(sys.modules, 'src.app.ms_runtime', SimpleNamespace(
        obtener_servicio=lambda: SimpleNamespace(recuperador=SimpleNamespace(encoder=Encoder()))))
    def unavailable(encoder):
        raise ValueError('Corrupt suggestion index')
    monkeypatch.setattr(scientific_search, 'catalog_article_search', unavailable)
    app = FastAPI(lifespan=science_main.lifespan)
    app.include_router(router)
    with TestClient(app) as client:
        assert app.state.modelos_cargados is True
        assert client.post('/api/analisis-cita-ms/recomendar', json={'contexto': 'scientific query'}).status_code == 503


def test_export_preserves_existing_vectors_and_checks_source(tmp_path):
    from scripts.exportar_busqueda_preparada import export
    docs = json.loads(Path('config/corpus_ms.json').read_text())['documentos']
    source = tmp_path / 'source'; source.mkdir()
    papers = [{'paper_id': pid, 'titulo': ' '.join(doc['titulo'].split()), 'resumen': ' '.join(doc['abstract'].split())}
              for pid, doc in reversed(list(docs.items()))]
    vectors = np.eye(768, dtype=np.float32)[:len(papers)]
    (source / 'papers.json').write_text(json.dumps(papers))
    np.save(source / 'embeddings.npy', vectors, allow_pickle=False)
    source_meta = json.loads(Path('config/prepared_article_search/indice.json').read_text())
    source_meta['files'] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in ['papers.json','embeddings.npy']}
    (source / 'indice.json').write_text(json.dumps(source_meta))
    catalog = tmp_path / 'catalog.json'; catalog.write_bytes(Path('frontend/src/articleCatalog.json').read_bytes())
    destination = tmp_path / 'export'
    export(source, destination, catalog)
    rows = json.loads((destination / 'papers.json').read_text())
    exported = np.load(destination / 'embeddings.npy', allow_pickle=False)
    by_id = {p['paper_id']: i for i,p in enumerate(papers)}
    assert np.array_equal(exported, vectors[[by_id[p['paper_id']] for p in rows]])
    (source / 'papers.json').write_text('[]')
    with pytest.raises(ValueError, match='hash incorrecto'):
        export(source, destination, catalog)


def test_full_catalog_preserves_corpus_and_existing_embeddings(monkeypatch):
    from src.app.article_corpus import corpus
    from src.app.scientific_search import catalog_article_search
    root = Path('artifacts/scientific_search')
    if not root.exists():
        pytest.skip('Full offline index is supplied separately')
    metadata = json.loads((root / 'indice.json').read_text())
    monkeypatch.setenv('MS_SEARCH_DIR', str(root))
    search = catalog_article_search(SimpleNamespace(revision=metadata['revision_scibert']))
    data, version = corpus()
    assert len(search.papers) == 19776
    assert set(data['documentos']) < set(search.ids)
    assert search.metadata['version_contenido'] == version
    assert search.metadata['files'] == metadata['files']
    foreign = next(p for p in search.papers if p['paper_id'] not in data['documentos'])
    vector = search.vectors[list(search.ids).index(foreign['paper_id'])]
    search.encoder = SimpleNamespace(encode=lambda texts: [vector.copy()], revision=metadata['revision_scibert'])
    result = search.recommend('synthetic TARGETCIT context', 5)
    assert result['recomendaciones'][0]['paper_id'] == foreign['paper_id']
    assert result['version_catalogo'] == metadata['files']['papers.json']
    assert result['version_contenido'] == version
