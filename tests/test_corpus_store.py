"""Indexed corpus integrity, lazy reads, and compatibility with the article API."""
import copy
import hashlib
import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.ampliar_cobertura_corpus import guardar, preparar_documento
from src.app.article_corpus import CorpusUnavailable, load_indexed_corpus
from src.app.corpus_store import IndexedCorpus
from src.app.ms_router import router


def fixture_store(tmp_path, mutate=None):
    doc = dict(paper_id='A00-1001', titulo='Public title', abstract='Public abstract',
               publicacion='https://aclanthology.org/A00-1001/', fuente='https://example.org/source', sha256_ocl='a'*64,
               candidatos=[dict(chunk_id=f'p{i}', texto=f'Public paragraph {i}.', seccion='Introduction') for i in range(3)])
    path = tmp_path / 'corpus.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=1')
        db.execute('CREATE TABLE documentos (paper_id TEXT PRIMARY KEY, titulo TEXT, abstract TEXT, total_fragmentos INTEGER, sha256_json TEXT, documento BLOB)')
        guardar(db, doc)
        if mutate:
            mutate(db)
    manifest = dict(corpus_schema=2, total_articulos=1, licencia='CC-BY-NC-4.0', fragmentacion='v2', revision_ocl='b'*40,
                    files=[dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
    config = tmp_path / 'release.json'; config.write_text(json.dumps(manifest))
    return path, config, doc


def test_reads_only_the_selected_article_and_preserves_contract(tmp_path):
    path, config, expected = fixture_store(tmp_path)
    data, version = load_indexed_corpus(str(config), str(path))
    docs = data['documentos']
    with patch('gzip.GzipFile', side_effect=AssertionError('Metadata must not decompress article bodies')):
        assert list(docs) == ['A00-1001']
        assert 'A00-1001' in docs and 'P99-9999' not in docs
        assert dict(docs.metadata())['A00-1001']['titulo'] == expected['titulo']
    assert docs['A00-1001'] == expected
    assert docs.get('P99-9999') is None
    assert len(version) == 64 and len(docs) == 1


def test_corrupt_database_is_rejected_before_readiness(tmp_path):
    path, config, _ = fixture_store(tmp_path)
    path.write_bytes(path.read_bytes()+b'corrupt')
    with pytest.raises(CorpusUnavailable):
        load_indexed_corpus(str(config), str(path))


def test_corrupt_article_does_not_masquerade_as_missing(tmp_path, monkeypatch):
    path, config, _ = fixture_store(tmp_path, lambda db: db.execute("UPDATE documentos SET documento=?", (b'broken',)))
    data, version = load_indexed_corpus(str(config), str(path))
    with pytest.raises(CorpusUnavailable):
        data['documentos']['A00-1001']
    monkeypatch.setattr('src.app.article_corpus.corpus', lambda: (data, version))
    app = FastAPI(); app.include_router(router)
    with patch('src.app.ms_router.analisis_cita_ms') as infer:
        response = TestClient(app).post('/api/analisis-cita-ms/articulo', json=dict(paper_id='A00-1001', contexto='Prior work TARGETCIT.'))
    assert response.status_code == 503
    availability = TestClient(app).post('/api/analisis-cita-ms/disponibilidad', json={'paper_ids':['A00-1001']})
    assert availability.status_code == 503
    infer.assert_not_called()


def test_preparation_keeps_sections_and_detects_identity_mismatch():
    source = dict(paper_id='A00-1001', pdf_parse=dict(body_text=[dict(text=f'Public scientific paragraph {i}.', section=f'Section {i}') for i in range(3)]))
    raw = json.dumps(source).encode()
    doc = preparar_documento('A00-1001', dict(title='Title', abstract='Abstract'), raw)
    assert [c['seccion'] for c in doc['candidatos']] == ['Section 0','Section 1','Section 2']
    assert doc['sha256_ocl'] == hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match='Identidad'):
        preparar_documento('A00-1002', dict(title='Title', abstract='Abstract'), raw)


def test_rejects_missing_source_without_claiming_paper_is_absent(tmp_path):
    from scripts.ampliar_cobertura_corpus import fetch
    relative = 'Base_JSON/prefixA/json/A00/A00-1001.json'
    row, doc = fetch('A00-1001', {'title':'Title','abstract':'Abstract'}, tmp_path/'cache', tmp_path/'source', {relative})
    assert row['estado'] == 'error_fuente' and doc is None
    row, doc = fetch('A00-1001', {'title':'Title','abstract':'Abstract'}, tmp_path/'cache', tmp_path/'source', set())
    assert row['estado'] == 'no_encontrado' and doc is None


def test_truncates_first_hundred_distinct_fragments_without_changing_order():
    source = dict(paper_id='A00-1001', pdf_parse=dict(body_text=[dict(text=f'Scientific paragraph {i}.', section=f'Section {i}') for i in range(105)]))
    doc = preparar_documento('A00-1001', dict(title='Title', abstract='Abstract'), json.dumps(source).encode())
    assert len(doc['candidatos']) == 100
    assert [c['seccion'] for c in doc['candidatos']] == [f'Section {i}' for i in range(100)]
    assert doc['truncamiento']['fragmentos_originales'] == 105
    assert doc['truncamiento']['texto_recortado'] is True


def test_character_budget_includes_metadata_and_retains_source_prefix():
    source = dict(paper_id='A00-1001', pdf_parse=dict(body_text=[dict(text=(f'term{i} ' * 299).strip(), section='Methods') for i in range(60)]))
    raw = json.dumps(source).encode()
    doc = preparar_documento('A00-1001', dict(title='Title', abstract='Abstract'), raw)
    cut = doc['truncamiento']
    assert 3 <= len(doc['candidatos']) <= 100
    size = len(doc['titulo']) + len(doc['abstract']) + sum(len(c['texto']) for c in doc['candidatos'])
    assert 55000 < size <= 56000 and cut['caracteres_analizados'] == size
    assert cut['caracteres_originales'] > 56000
    assert doc['candidatos'][-1]['recortado'] is True
    for i, chunk in enumerate(doc['candidatos']):
        assert source['pdf_parse']['body_text'][i]['text'].startswith(chunk['texto'])


def test_original_metadata_stays_searchable_while_analysis_uses_bounded_copy(tmp_path):
    meta = dict(title='Title '*150, abstract='Abstract '*1600)
    source = dict(paper_id='A00-1001', pdf_parse=dict(body_text=[dict(text=f'Paragraph {i}.', section=f'{i}'+ 'S'*220) for i in range(3)]))
    doc = preparar_documento('A00-1001', meta, json.dumps(source).encode())
    path, _, _ = fixture_store(tmp_path)
    with sqlite3.connect(path) as db:
        guardar(db, doc, meta)
    store = IndexedCorpus(path, hashlib.sha256(path.read_bytes()).hexdigest(), 1)
    assert dict(store.metadata())['A00-1001']['titulo'] == meta['title']
    assert dict(store.metadata())['A00-1001']['abstract'] == meta['abstract']
    loaded = store['A00-1001']
    assert loaded == doc and len(loaded['titulo']) <= 600 and len(loaded['abstract']) <= 12000
    assert all(len(c['seccion']) <= 200 for c in loaded['candidatos'])
