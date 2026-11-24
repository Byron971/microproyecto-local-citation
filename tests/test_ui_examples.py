"""Integridad de ejemplos UI; no evalúa modelos ni calidad científica."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def test_ui_examples_cover_distinct_prepared_articles_and_keep_catalog_identity():
    examples = read('frontend/src/scientificExamples.json')
    catalog = read('frontend/src/fullArticleCatalog.json')
    selection = read('config/ui_example_articles.json')
    articles = {a['paper_id']: a for a in catalog['articulos']}
    rows = examples['ejemplos']
    selected_ids = {pid for group in selection['temas'] for pid in group['paper_ids']}
    assert len(rows) == len(selected_ids) == 40
    assert {e['paper_id'] for e in rows} == selected_ids
    assert len({e['context_id'] for e in rows}) == len(rows)
    assert len({e['tema'] for e in rows[:10]}) == len(selection['temas']) == 8
    assert examples['version_contenido'] == catalog['version_contenido']
    assert examples['sha256_fuentes']['seleccion'] == hashlib.sha256(
        (ROOT / 'config/ui_example_articles.json').read_bytes()).hexdigest()
    for row in rows:
        article = articles[row['paper_id']]
        assert article['preparado'] is True
        assert article['titulo'] == row['titulo']
        assert row['contexto'].count('TARGETCIT') == 1
        assert 0 < len(row['contexto']) <= 4000
        assert set(row) == {'context_id', 'paper_id', 'citing_id', 'titulo', 'tema', 'contexto'}


def test_ui_examples_preserve_validation_text_and_exclude_reserved_partitions():
    paths = {name: ROOT / f'data/raw/{name}.json' for name in ['contexts', 'train', 'val', 'test']}
    if not all(path.exists() for path in paths.values()):
        pytest.skip('Requiere fuentes locales de ACL-200 para contrastar textos y particiones')
    data = {name: json.loads(path.read_text()) for name, path in paths.items()}
    examples = read('frontend/src/scientificExamples.json')
    valid = {r['context_id']: r for r in data['val']}
    excluded = {r['context_id'] for name in ['train', 'test'] for r in data[name]}
    for path in (ROOT / 'annotations/citation_function').glob('*gold*.jsonl'):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            excluded.add(row.get('id', row.get('context_id', '')))
    for name, path in paths.items():
        assert examples['sha256_fuentes'][name] == hashlib.sha256(path.read_bytes()).hexdigest()
    for row in examples['ejemplos']:
        cid = row['context_id']
        source = data['contexts'][cid]
        assert cid in valid and cid not in excluded
        assert valid[cid]['positive_ids'] == [source['refid']] == [row['paper_id']]
        assert row['contexto'] == source['masked_text']
        assert row['citing_id'] == source['citing_id']
