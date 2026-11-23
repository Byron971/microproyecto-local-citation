"""Comprobación pública acotada del selector, sin OpenAI ni evaluación científica."""
import json
import urllib.request
from pathlib import Path

catalog = json.loads(Path('frontend/src/articleCatalog.json').read_text())
full = json.loads(Path('frontend/src/fullArticleCatalog.json').read_text())
source = json.loads(Path('artifacts/scientific_search/papers.json').read_text())
query = 'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.'
request = urllib.request.Request('https://api.proyectocitas-grupo19.click/api/analisis-cita-ms/recomendar',
    data=json.dumps({'contexto': query, 'top_k': 5, 'modelo': 'scibert-articulos-v1'}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=60) as response:
    assert response.status == 200
    data = json.load(response)
assert data['total_catalogo'] == len(full['articulos']) == 19776
assert data['version_catalogo'] == full['source_sha256']
assert data['version_contenido'] == catalog['version_contenido']
assert len(data['recomendaciones']) == 5
assert len({a['paper_id'] for a in data['recomendaciones']}) == 5
by_id = {a['paper_id']: a for a in source}
for article in data['recomendaciones']:
    assert article['titulo'] == ' '.join(by_id[article['paper_id']]['titulo'].split())
    assert article['resumen'] == by_id[article['paper_id']]['resumen']
Path('artifacts/full-catalog-public.json').write_text(json.dumps(data, indent=2))
print(json.dumps({'ok': True, 'articulos_catalogo': len(full['articulos']), 'articulos_preparados': len(catalog['articulos']), 'ids': [a['paper_id'] for a in data['recomendaciones']]}))
