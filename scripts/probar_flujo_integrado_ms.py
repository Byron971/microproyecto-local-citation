"""Acceptance with an invented context and public article content only."""
import argparse
import json
import re
from pathlib import Path
import time
import urllib.request


def leer_json(base, path, payload=None, timeout=32):
    request = urllib.request.Request(
        base.rstrip('/') + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json'} if payload is not None else {},
    )
    # HTTPError (incluido 429) se propaga: nunca reintentar ni iniciar otro cálculo.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.load(response)


def analizar_asincrono(base, payload, max_wait=180):
    started = time.monotonic()
    status, result = leer_json(base, '/api/analisis-cita-ms/articulo',
                               {**payload, 'asincrono': True})
    if status != 202:
        raise ValueError('La prueba requiere admisión asíncrona HTTP 202.')
    job_id = None
    while status == 202:
        current_id = result.get('trabajo_id') if isinstance(result, dict) else None
        if (not isinstance(result, dict) or result.get('estado') != 'procesando' or not isinstance(current_id, str)
                or not re.fullmatch(r'[a-f0-9]{32}', current_id)
                or (job_id is not None and current_id != job_id)):
            raise ValueError('Respuesta de trabajo pendiente inválida o identificador distinto.')
        job_id = current_id
        remaining = max_wait - (time.monotonic() - started)
        if remaining <= 1:
            raise TimeoutError('El análisis sigue pendiente; no se repitió ni se canceló la inferencia.')
        time.sleep(1)
        status, result = leer_json(base, '/api/analisis-cita-ms/articulo/' + job_id,
                                  timeout=min(32, remaining - 1))
    if status != 200:
        raise ValueError('El trabajo no devolvió un resultado HTTP 200.')
    return result


def verificar(base):
    corpus = json.loads(Path('config/corpus_ms.json').read_text())
    selected = 'W05-0821'
    status, available = leer_json(base, '/api/analisis-cita-ms/disponibilidad', {'paper_ids': [selected]})
    assert status == 200
    assert available['articulos'][0]['paper_id'] == selected
    assert available['articulos'][0]['disponible'] is True
    context = 'Earlier work TARGETCIT proposed neural methods for scientific document classification.'
    start = time.monotonic()
    result = analizar_asincrono(base, {'paper_id': selected, 'contexto': context})
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
    return {'modo': 'asincrono', 'url': base, 'paper_id': selected, 'latencia_segundos': round(latency, 3),
            'recorrido': 'contexto → artículo citado → clasificador → Top-3 y función',
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
