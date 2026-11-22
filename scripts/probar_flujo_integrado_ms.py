"""Acceptance with an invented context and public article content only."""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def verificar(base):
    def post(path, payload):
        req = urllib.request.Request(base.rstrip('/') + path, data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=32) as response:
            return json.load(response)

    corpus = json.loads(Path('config/corpus_ms.json').read_text())
    known = corpus['documentos']['S15-1012']
    query = known['titulo'] + '\n' + known['abstract']
    recommendations = post('/api/analisis-cita-ms/recomendar', {'contexto': query, 'top_k': 10})
    assert recommendations['modelo'] == 'scibert-articulos-v1'
    assert recommendations['total_catalogo'] == 19776
    ids = [r['paper_id'] for r in recommendations['recomendaciones']]
    available = post('/api/analisis-cita-ms/disponibilidad', {'paper_ids': ids})
    selected = next(a['paper_id'] for a in available['articulos'] if a['disponible'])
    context = 'Earlier work TARGETCIT proposed neural methods for scientific document classification.'
    start = time.monotonic()
    result = post('/api/analisis-cita-ms/articulo', {'paper_id': selected, 'contexto': context})
    latency = time.monotonic() - start
    assert result['articulo']['paper_id'] == selected
    assert result['articulo']['version_contenido'] == available['version_contenido']
    assert len(result['top3']) == 3 and len({f['chunk_id'] for f in result['top3']}) == 3
    # Independently match every returned text against the prepared article.
    chunks = {c['chunk_id']: c['texto'] for c in corpus['documentos'][selected]['candidatos']}
    assert all(chunks[f['chunk_id']] == f['texto'] for f in result['top3'])
    for classifier in result['clasificadores'].values():
        probs = classifier['probabilidades']
        assert len(probs) == 9 and len({p['clase'] for p in probs}) == 9
        assert all(0 <= p['probabilidad'] <= 1 for p in probs)
        assert abs(sum(p['probabilidad'] for p in probs) - 1) < .005
    return {'url': base, 'paper_id': selected, 'latencia_segundos': round(latency, 3),
            'modelo_recomendacion': recommendations['modelo'], 'total_catalogo': recommendations['total_catalogo'],
            'total_fragmentos': result['articulo']['total_fragmentos'],
            'version_contenido': available['version_contenido'],
            'top3': [f['chunk_id'] for f in result['top3']],
            'clases': {k: v['clase'] for k, v in result['clasificadores'].items()},
            'identidad_y_textos_verificados': True, 'categorias_por_modelo': 9,
            'contexto_inventado_sin_train_gold': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://api.proyectocitas-grupo19.click')
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    report = verificar(args.url)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
