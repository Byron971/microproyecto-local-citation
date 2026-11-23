"""Comprobación pública acotada del selector, sin OpenAI ni evaluación científica."""
import json
import urllib.request
from pathlib import Path

catalog = json.loads(Path('frontend/src/articleCatalog.json').read_text())
query = 'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.'
request = urllib.request.Request('https://api.proyectocitas-grupo19.click/api/analisis-cita-ms/recomendar',
    data=json.dumps({'contexto': query, 'top_k': 5, 'modelo': 'scibert-articulos-v1'}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=60) as response:
    assert response.status == 200
    data = json.load(response)
assert data['total_catalogo'] == len(catalog['articulos']) == 37
assert data['version_contenido'] == catalog['version_contenido']
assert len(data['recomendaciones']) == 5
assert len({a['paper_id'] for a in data['recomendaciones']}) == 5
by_id = {a['paper_id']: a for a in catalog['articulos']}
for article in data['recomendaciones']:
    assert article['titulo'] == by_id[article['paper_id']]['titulo']
    assert article['resumen'] == by_id[article['paper_id']]['resumen']
Path('artifacts/article-search-public.json').write_text(json.dumps(data, indent=2))
print(json.dumps({'ok': True, 'articulos_preparados': 37, 'ids': [a['paper_id'] for a in data['recomendaciones']]}))
