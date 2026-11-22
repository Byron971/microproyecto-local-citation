"""Preparación y recepción local de anotaciones humanas de Toloka; sin llamadas API."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from anotacion_asistida import HEADER, LABELS, digest, read_sheets, read_template

FIELDS = ('context_id', 'worker_id', 'assignment_id', 'evaluabilidad', 'funcion',
          'confianza', 'justificacion')


def prepare(source, output_dir):
    template = read_template(source)
    if any(c['has_answers'] for c in template['cases']):
        raise ValueError('La fuente contiene respuestas; elegir una copia original en blanco.')
    if not all(c['valid_target'] for c in template['cases']):
        raise ValueError('Revisar contextos sin exactamente un TARGETCIT antes de exportar.')
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    items = [{k: c[k] for k in ('context_id', 'contexto', 'titulo', 'resumen')}
             for c in template['cases']]
    (out / 'tareas.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    sheets = read_sheets(source)
    guide = '\n'.join(' | '.join(filter(None, row)) for row in sheets['9_funciones'] if any(row))
    (out / 'guia.txt').write_text(guide + '\n\n' +
        'Anotación humana independiente. No usar LLM ni consultar decisiones ajenas. '
        'Clasificar TARGETCIT según el inglés original. En Ambiguo o No evaluable, '
        'dejar función vacía y explicar la duda. Confianza: Alta, Media o Baja. '
        'Escribir una justificación breve en todos los casos.\n', encoding='utf-8')
    with (out / 'plantilla_respuestas.csv').open('w', newline='', encoding='utf-8-sig') as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    (out / 'procedencia_entrada.json').write_text(json.dumps({
        'source': str(template['path']), 'sha256': template['sha256'],
        'n': len(items), 'budget_usd': 20, 'origin': 'human_toloka',
        'note': 'No se ejecutó el agente ni se exportaron sus anotaciones.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return template


def receive(source, response_csv, output_dir):
    """Valida 1 respuesta humana por caso y prepara CSV alineado con el Excel original.

    No aplica validate_result del agente: su política de Ambiguo pide función,
    mientras que la guía humana deja esa función vacía.
    """
    template = read_template(source)
    out = Path(output_dir)
    provenance = json.loads((out / 'procedencia_entrada.json').read_text(encoding='utf-8'))
    if template['sha256'] != provenance['sha256']:
        raise ValueError('El Excel cambió desde la exportación.')
    with Path(response_csv).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if set(FIELDS) - set(reader.fieldnames or []):
            raise ValueError('Faltan columnas de la plantilla de respuestas.')
        rows = list(reader)
    expected = {c['context_id'] for c in template['cases']}
    by_id, assignments = {}, set()
    for row in rows:
        r = {k: (row.get(k) or '').strip() for k in FIELDS}
        cid = r['context_id']
        if cid not in expected or cid in by_id:
            raise ValueError(f'ID ajeno o duplicado: {cid}')
        if not r['worker_id'] or not r['assignment_id'] or r['assignment_id'] in assignments:
            raise ValueError(f'Falta identidad o assignment duplicado: {cid}')
        if r['evaluabilidad'] not in LABELS['evaluabilidad']:
            raise ValueError(f'Evaluabilidad inválida: {cid}')
        if r['evaluabilidad'] == 'Evaluable':
            if r['funcion'] not in LABELS['funcion']:
                raise ValueError(f'Función inválida: {cid}')
        elif r['funcion']:
            raise ValueError(f'Ambiguo/No evaluable debe dejar función vacía: {cid}')
        if r['confianza'] not in LABELS['confianza'] or not r['justificacion']:
            raise ValueError(f'Falta confianza o justificación: {cid}')
        if len(r['justificacion']) > 3000 or any(ord(c) < 32 and c not in '\n\r\t' for c in r['justificacion']):
            raise ValueError(f'Justificación incompatible con la plantilla: {cid}')
        by_id[cid] = r
        assignments.add(r['assignment_id'])
    if set(by_id) != expected:
        raise ValueError(f'Faltan {len(expected - set(by_id))} entradas; no se completa la entrega.')
    # Mismo orden de columnas I–L del Excel, sin fórmulas ni cambios al libro.
    output = out / 'respuestas_para_excel.csv'
    if output.exists():
        raise FileExistsError('La entrega ya existe; conservarla o usar otra carpeta versionada.')
    with output.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['context_id', *HEADER[7:11]])
        for c in template['cases']:
            r = by_id[c['context_id']]
            writer.writerow([c['context_id'], r['evaluabilidad'], r['funcion'], r['confianza'], r['justificacion']])
    (out / 'procedencia_respuestas.json').write_text(json.dumps({
        'origin': 'human_toloka', 'source_sha256': template['sha256'],
        'response_sha256': digest(Path(response_csv).read_bytes()),
        'count': len(rows), 'review_status': 'pendiente_equipo',
        'workers': sorted({r['worker_id'] for r in by_id.values()}),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return output
