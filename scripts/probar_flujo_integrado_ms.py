"""Acceptance with an invented context and public article content only."""
import argparse
import json
import re
from pathlib import Path
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor


def leer_json(base, path, payload=None, timeout=32):
    request = urllib.request.Request(
        base.rstrip('/') + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json'} if payload is not None else {},
    )
    # HTTPError (incluido 429) se propaga: nunca reintentar ni iniciar otro cálculo.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.load(response)


TERMINALES = ('completado', 'fallido', 'expirado', 'cancelado')


def analizar_asincrono(base, payload, max_wait=None, estados=None):
    """Una admisión con clave de idempotencia y solo GET del mismo trabajo hasta un estado terminal."""
    started = time.monotonic()
    clave = str(uuid.uuid4())
    status, job = leer_json(base, '/api/analisis-cita-ms/trabajos',
                            {**payload, 'clave_idempotencia': clave})
    if status not in (200, 202):
        raise ValueError('La admisión no devolvió HTTP 202/200.')
    job_id = None
    if max_wait is None:
        # La expiración del servidor manda; este límite solo protege al comprobador.
        max_wait = (job.get('espera_maxima_s', 900) if isinstance(job, dict) else 900) + 300
    while True:
        current_id = job.get('trabajo_id') if isinstance(job, dict) else None
        if (not isinstance(job, dict) or job.get('estado') not in TERMINALES + ('en_cola', 'procesando')
                or not isinstance(current_id, str) or not re.fullmatch(r'[a-f0-9]{32}', current_id)
                or (job_id is not None and current_id != job_id)):
            raise ValueError('Estado de trabajo inválido o identificador distinto.')
        job_id = current_id
        if estados is not None and (not estados or estados[-1] != job['estado']):
            estados.append(job['estado'])
        if job['estado'] == 'completado':
            return job['resultado']
        if job['estado'] in TERMINALES:
            raise RuntimeError(f"Trabajo {job['estado']}: {job.get('error', {}).get('mensaje', '')}")
        remaining = max_wait - (time.monotonic() - started)
        if remaining <= 1:
            raise TimeoutError('El análisis sigue pendiente; no se repitió ni se canceló la inferencia.')
        time.sleep(2)
        status, job = leer_json(base, '/api/analisis-cita-ms/trabajos/' + job_id,
                                timeout=min(32, remaining - 1))
        if status != 200:
            raise ValueError('La consulta del trabajo no devolvió HTTP 200.')


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
    return {'modo': 'cola_trabajos', 'url': base, 'paper_id': selected, 'latencia_segundos': round(latency, 3),
            'recorrido': 'contexto → artículo citado → clasificador → Top-3 y función',
            'total_fragmentos': result['articulo']['total_fragmentos'],
            'version_contenido': available['version_contenido'],
            'top3': [f['chunk_id'] for f in result['top3']],
            'clases': {k: v['clase'] for k, v in result['clasificadores'].items()},
            'identidad_y_textos_verificados': True, 'categorias_por_modelo': 9,
            'contexto_inventado_sin_train_gold': True}


CONTEXTOS = [
    'Earlier work TARGETCIT proposed neural methods for scientific document classification.',
    'We follow the evaluation protocol of TARGETCIT for machine translation quality.',
    'Unlike TARGETCIT, our approach does not require parallel corpora.',
]


def caso(base, indice):
    estados, inicio = [], time.monotonic()
    try:
        resultado = analizar_asincrono(base, {'paper_id': 'W05-0821', 'contexto': CONTEXTOS[indice % 3]},
                                       estados=estados)
        ok = len(resultado['top3']) == 3 and set(resultado['clasificadores']) == {'M', 'S'}
        return {'caso': indice + 1, 'ok': ok, 'estados': estados,
                'segundos': round(time.monotonic() - inicio, 1)}
    except Exception as exc:  # Se registra y no se reenvía.
        return {'caso': indice + 1, 'ok': False, 'estados': estados, 'error': f'{type(exc).__name__}: {exc}',
                'segundos': round(time.monotonic() - inicio, 1)}


def gradual(base, secuenciales, simultaneos):
    if not (0 <= secuenciales <= 5 and 0 <= simultaneos <= 3):
        raise SystemExit('Aceptación acotada: hasta 5 secuenciales y 3 simultáneos.')
    informe = {'url': base, 'secuenciales': [], 'simultaneos': []}
    for i in range(secuenciales):
        informe['secuenciales'].append(caso(base, i))
        if not informe['secuenciales'][-1]['ok']:
            break  # Detener ante el primer fallo.
    if simultaneos and all(c['ok'] for c in informe['secuenciales']):
        with ThreadPoolExecutor(max_workers=simultaneos) as pool:
            informe['simultaneos'] = list(pool.map(lambda i: caso(base, i), range(simultaneos)))
    informe['ok'] = all(c['ok'] for c in informe['secuenciales'] + informe['simultaneos'])
    return informe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://api.proyectocitas-grupo19.click')
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--secuenciales', type=int, default=0)
    parser.add_argument('--simultaneos', type=int, default=0)
    args = parser.parse_args()
    if args.secuenciales or args.simultaneos:
        report = gradual(args.url, args.secuenciales, args.simultaneos)
    else:
        report = verificar(args.url)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
