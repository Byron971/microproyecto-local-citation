"""Exporta ejemplos de validación compatibles sin etiquetas ni respuestas del modelo."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def exportar():
    paths = {name: ROOT / 'data/raw' / (name + '.json') for name in ['contexts', 'train', 'val', 'test']}
    data = {name: json.loads(path.read_text()) for name, path in paths.items()}
    catalog = json.loads((ROOT / 'frontend/src/articleCatalog.json').read_text())
    articles = {a['paper_id']: a for a in catalog['articulos']}
    excluded = {r['context_id'] for name in ['train', 'test'] for r in data[name]}
    for path in (ROOT / 'annotations/citation_function').glob('*gold*.jsonl'):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            excluded.add(row.get('id', row.get('context_id', '')))
    examples = []
    for row in data['val']:
        cid = row['context_id']
        context = data['contexts'][cid]
        pid = context['refid']
        text = context['masked_text']
        if cid in excluded or pid not in articles or row['positive_ids'] != [pid]:
            continue
        if text.count('TARGETCIT') != 1 or not 0 < len(text) <= 4000:
            continue
        examples.append({'context_id': cid, 'paper_id': pid, 'citing_id': context['citing_id'],
                         'titulo': articles[pid]['titulo'], 'contexto': text})
    examples.sort(key=lambda e: (e['titulo'], e['context_id']))
    assert examples and len({e['context_id'] for e in examples}) == len(examples)
    result = {'fuente': 'ACL-200', 'particion': 'val',
              'version_contenido': catalog['version_contenido'],
              'sha256_fuentes': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
              'ejemplos': examples}
    (ROOT / 'frontend/src/scientificExamples.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(examples)} ejemplos; {len({e["paper_id"] for e in examples})} artículos.')

if __name__ == '__main__':
    exportar()
