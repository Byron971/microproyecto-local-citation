"""Exporta una selección editorial diversa de validación, sin etiquetas ni predicciones."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def exportar():
    paths = {name: ROOT / 'data/raw' / (name + '.json') for name in ['contexts', 'train', 'val', 'test']}
    paths['catalogo'] = ROOT / 'frontend/src/fullArticleCatalog.json'
    paths['seleccion'] = ROOT / 'config/ui_example_articles.json'
    data = {name: json.loads(path.read_text()) for name, path in paths.items()}
    catalog = data['catalogo']
    articles = {a['paper_id']: a for a in catalog['articulos'] if a['preparado']}
    excluded = {r['context_id'] for name in ['train', 'test'] for r in data[name]}
    gold_paths = sorted((ROOT / 'annotations/citation_function').glob('*gold*.jsonl'))
    for path in gold_paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            excluded.add(row.get('id', row.get('context_id', '')))
    eligible = defaultdict(list)
    for row in data['val']:
        cid = row['context_id']
        context = data['contexts'][cid]
        pid = context['refid']
        text = context['masked_text']
        if cid in excluded or pid not in articles or row['positive_ids'] != [pid]:
            continue
        if text.count('TARGETCIT') != 1 or not 0 < len(text) <= 4000:
            continue
        eligible[pid].append(context)
    groups = data['seleccion']['temas']
    selected = [pid for group in groups for pid in group['paper_ids']]
    assert len(selected) == len(set(selected)), 'No repetir artículos en la selección'
    examples = []
    # Intercalar subtemas: la primera página no queda dominada por un solo artículo/tema.
    for index in range(max(len(group['paper_ids']) for group in groups)):
        for group in groups:
            if index >= len(group['paper_ids']):
                continue
            pid = group['paper_ids'][index]
            assert eligible[pid], f'Sin contexto de validación elegible para {pid}'
            def legibilidad(context):
                text = context['masked_text'].strip()
                # Preferencia editorial por prosa: no transforma el texto ni evalúa modelos.
                unusual = sum(not (char.isascii() and (char.isalpha() or char.isspace()
                              or char in ".,;:!?'\"()-")) for char in text)
                starts_with_word = bool(re.match(r'(?:[A-Z][a-z]+\b|TARGETCIT\b)', text))
                return unusual > 5, not starts_with_word, unusual, text.count('OTHERCIT'), context['context_id']
            context = min(eligible[pid], key=legibilidad)
            examples.append({'context_id': context['context_id'], 'paper_id': pid,
                             'citing_id': context['citing_id'], 'titulo': articles[pid]['titulo'],
                             'tema': group['nombre'], 'contexto': context['masked_text']})
    assert examples and len({e['context_id'] for e in examples}) == len(examples)
    result = {'fuente': 'ACL-200', 'particion': 'val',
              'version_contenido': catalog['version_contenido'],
              'sha256_fuentes': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
              'sha256_exclusiones': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in gold_paths},
              'ejemplos': examples}
    (ROOT / 'frontend/src/scientificExamples.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(examples)} ejemplos; {len(selected)} artículos; {len(groups)} subtemas de PLN.')
    print(f'Universo elegible: {sum(map(len, eligible.values()))} contextos; {len(eligible)} artículos.')


if __name__ == '__main__':
    exportar()
