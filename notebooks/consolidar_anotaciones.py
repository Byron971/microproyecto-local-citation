"""Consolidación local de predicciones originales, sin llamadas API ni etiquetas humanas ficticias."""
import csv
import json
import math
import random
from collections import Counter
from itertools import combinations
from pathlib import Path

import anotacion_asistida as aa


DEFAULT_MODELS = [
    ('openai', 'gpt-4o-mini'), ('openai', 'gpt-5.4-mini'),
    ('openai', 'gpt-6-luna'), ('openai', 'gpt-6-sol'),
    ('anthropic', 'claude-sonnet-5-5'), ('anthropic', 'claude-opus-5-5'),
]


def agreement(pairs):
    n = len(pairs)
    if not n:
        return {'n': 0, 'agreement': None, 'kappa': None}
    observed = sum(a == b for a, b in pairs) / n
    a, b = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    expected = sum(a[k] * b[k] for k in set(a) | set(b)) / n**2
    return {'n': n, 'agreement': observed,
            'kappa': (observed - expected) / (1 - expected) if expected < 1 else None}


def consolidate(source, prediction_dir, output_dir, *, models=None, min_responses=5,
                agreement_threshold=0.8, min_votes=None, agreement_pair=None, audit_fraction=0.1, seed=2026):
    models = list(models or DEFAULT_MODELS)
    if len({m for _, m in models}) != len(models):
        raise ValueError('No duplicar modelos ni contar una ejecución más de una vez.')
    if not 1 <= min_responses <= len(models) or not 0.5 < agreement_threshold <= 1 or not 0 <= audit_fraction <= 1:
        raise ValueError('Política de consolidación inválida.')
    if min_votes is not None and (not isinstance(min_votes, int) or not len(models)/2 < min_votes <= len(models)):
        raise ValueError('El mínimo de votos debe ser una mayoría estricta de los modelos esperados.')
    if agreement_pair is not None:
        agreement_pair = tuple(agreement_pair)
        if len(agreement_pair) != 2 or len(set(agreement_pair)) != 2 or not set(agreement_pair) <= {m for _,m in models}:
            raise ValueError('La pareja de consenso debe contener dos modelos distintos de la selección.')
    template = aa.read_template(source)
    cases = template['cases']
    ids = [c['context_id'] for c in cases]
    source_ids = set(ids)
    docs, inputs = {}, []
    for provider, model in models:
        path = Path(prediction_dir) / f'{Path(source).stem}__{model}.predicciones.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc.get('model') != model or doc.get('provider', provider) != provider:
            raise ValueError(f'Modelo/proveedor inesperado: {path.name}')
        if doc.get('source_sha256') != template['sha256']:
            raise ValueError(f'Fuente distinta: {path.name}')
        declared = doc.get('context_ids', [])
        if len(declared) != len(set(declared)) or set(declared) != source_ids:
            raise ValueError(f'Manifiesto de entradas incompatible: {path.name}')
        if not isinstance(doc.get('results'), dict) or set(doc['results']) - source_ids:
            raise ValueError(f'Resultados con estructura o IDs inválidos: {path.name}')
        docs[model] = doc
        inputs.append({'provider': provider, 'model': model, 'path': str(path.resolve()),
                       'sha256': aa.digest(path.read_bytes()), 'run_key': doc.get('run_key')})

    details, consolidated, validated = [], [], {}
    for case in cases:
        cid = case['context_id']
        valid = []
        available = 0
        for provider, model in models:
            raw = docs[model]['results'].get(cid)
            quality = 'ausente'
            error = ''
            normalized = {}
            if cid in docs[model]['results']:
                available += 1
                try:
                    normalized = aa.validate_result(raw, case['contexto'])
                    if not case['valid_target']:
                        raise ValueError('El contexto no tiene exactamente un TARGETCIT')
                    quality = 'valida'
                    valid.append((provider, model, normalized))
                    validated[(cid, model)] = normalized
                except ValueError as exc:
                    quality = 'invalida'
                    error = getattr(exc, 'code', 'formato_o_contexto')
            values = raw if isinstance(raw, dict) else {}
            details.append({'context_id': cid, 'provider': provider, 'model': model,
                            'calidad_respuesta': quality, 'error_validacion': error,
                            **{k: values.get(k, '') for k in aa.FIELDS},
                            'respuesta_original_json': json.dumps(raw, ensure_ascii=False)})

        evaluable = [(p, m, r) for p, m, r in valid if r['evaluabilidad'] == 'Evaluable']
        votes = Counter(r['funcion'] for _, _, r in evaluable)
        ordered = votes.most_common()
        leading = ordered[0][1] if ordered else 0
        second = ordered[1][1] if len(ordered) > 1 else 0
        tied = len(ordered) > 1 and leading == second
        label = ordered[0][0] if ordered and not tied else ''
        rate = leading / available if available else 0
        supporters = sorted({p for p, _, r in evaluable if r['funcion'] == label})
        low = sum(r['confianza'] == 'Baja' for _, _, r in valid)
        reasons = []
        if available < min_responses: reasons.append('cobertura_insuficiente')
        if len(valid) < available: reasons.append('respuesta_invalida')
        if len(evaluable) < len(valid): reasons.append('ambiguo_o_no_evaluable')
        if not label: reasons.append('empate_o_sin_funcion')
        if rate + 1e-12 < agreement_threshold: reasons.append('acuerdo_insuficiente')
        if len(supporters) < 2: reasons.append('sin_respaldo_entre_proveedores')
        if low: reasons.append('confianza_baja')
        alerts = list(reasons)
        if min_votes is None:
            accepted = not reasons
        else:
            # La política explícita de votos prima sobre filtros anteriores. Solo se
            # cuentan respuestas estructuralmente válidas y marcadas Evaluable.
            accepted = bool(label) and leading >= min_votes
            reasons = [] if accepted else ['sin_mayoria_de_votos_validos']
        accepted_label = label if accepted else ''
        acceptance_rule = ('minimo_votos' if min_votes is not None else 'calidad_estricta') if accepted else ''
        pair_label = ''
        if agreement_pair is not None:
            pair_results = [validated.get((cid,m)) for m in agreement_pair]
            if all(r and r['evaluabilidad']=='Evaluable' for r in pair_results):
                if pair_results[0]['funcion'] == pair_results[1]['funcion']:
                    pair_label = pair_results[0]['funcion']
        # Fallback únicamente para filas que aún requieren revisión. El consenso
        # de la pareja puede diferir de la función más votada o resolver un empate.
        if not accepted and pair_label:
            accepted = True
            accepted_label = pair_label
            acceptance_rule = 'coincidencia_pareja_prioritaria'
            reasons = []
        n_eval = len(evaluable)
        entropy = -sum((n/n_eval) * math.log(n/n_eval) for n in votes.values()) / math.log(len(aa.LABELS['funcion'])) if n_eval else None
        pair_agreement = sum(n*(n-1)//2 for n in votes.values()) / (n_eval*(n_eval-1)//2) if n_eval > 1 else None
        row = {'context_id': cid, 'fila_excel': case['row'],
               'contexto_original': case['contexto'], 'titulo_citado': case['titulo'], 'resumen_citado': case['resumen'],
               'modelos_esperados': len(models), 'respuestas_disponibles': available,
               'respuestas_validas': len(valid), 'respuestas_evaluables': n_eval,
               'modelos_ausentes': json.dumps([m for _, m in models if cid not in docs[m]['results']], ensure_ascii=False),
               'votos_por_funcion': json.dumps(dict(votes), ensure_ascii=False),
               'funcion_mas_votada': label, 'votos_ganadores': leading,
               'proporcion_acuerdo': rate, 'margen_votos': leading-second,
               'acuerdo_pares_evaluables': pair_agreement, 'entropia_normalizada': entropy,
               'proveedores_respaldo': json.dumps(supporters), 'respuestas_confianza_baja': low,
               'decision_automatica': 'consenso_provisional' if accepted else 'revision_requerida',
               'requiere_revision': not accepted, 'motivos_revision': '; '.join(reasons),
               'alertas_calidad': '; '.join(alerts),
               'funcion_consenso': accepted_label, 'regla_aceptacion': acceptance_rule,
               'votos_funcion_consenso': votes.get(accepted_label,0),
               'funcion_coincidente_pareja': pair_label,
               'seleccion_auditoria': False, 'revision_humana_pendiente': not accepted,
               'final_evaluabilidad': '', 'funcion_final': '', 'revisor': '', 'fecha_revision': '', 'justificacion_revision': ''}
        for _, model in models:
            r = docs[model]['results'].get(cid)
            for field in aa.FIELDS:
                row[f'{model}__{field}'] = r.get(field, '') if isinstance(r, dict) else ''
        consolidated.append(row)

    accepted_rows = [r for r in consolidated if not r['requiere_revision']]
    sample_size = math.ceil(len(accepted_rows) * audit_fraction)
    sampled = set(random.Random(seed).sample([r['context_id'] for r in accepted_rows], sample_size))
    for r in consolidated:
        if r['context_id'] in sampled:
            r['seleccion_auditoria'] = r['revision_humana_pendiente'] = True

    pairwise = []
    for (_, a), (_, b) in combinations(models, 2):
        common = [(validated[(cid,a)], validated[(cid,b)]) for cid in ids
                  if (cid,a) in validated and (cid,b) in validated]
        states = agreement([(x['evaluabilidad'],y['evaluabilidad']) for x,y in common])
        labels = agreement([(x['funcion'],y['funcion']) for x,y in common
                            if x['evaluabilidad'] == y['evaluabilidad'] == 'Evaluable'])
        pairwise.append({'modelo_a': a, 'modelo_b': b,
                         **{'evaluabilidad_'+k:v for k,v in states.items()},
                         **{'funcion_'+k:v for k,v in labels.items()}})
    coverage = []
    for provider, model in models:
        rr = [r for r in details if r['model'] == model]
        coverage.append({'provider':provider, 'model':model,
                         'calidad':dict(Counter(r['calidad_respuesta'] for r in rr)),
                         'evaluabilidad':dict(Counter(r['evaluabilidad'] for r in rr if r['calidad_respuesta']=='valida')),
                         'funciones_evaluables':dict(Counter(r['funcion'] for r in rr if r['calidad_respuesta']=='valida' and r['evaluabilidad']=='Evaluable'))})
    review = [r for r in consolidated if r['revision_humana_pendiente']]
    review.sort(key=lambda r: (not r['requiere_revision'], r['proporcion_acuerdo'], r['margen_votos'], r['fila_excel']))
    metrics = {'n_entradas':len(ids), 'n_anotaciones_disponibles':sum(r['calidad_respuesta']!='ausente' for r in details),
               'n_consenso_provisional':len(accepted_rows), 'n_revision_desacuerdos':len(ids)-len(accepted_rows),
               'n_auditoria_consensos':sample_size, 'n_cola_revision_total':len(review),
               'cobertura_por_fila':dict(Counter(r['respuestas_disponibles'] for r in consolidated)),
               'motivos_revision':dict(Counter(reason for r in consolidated for reason in r['motivos_revision'].split('; ') if reason)),
               'funciones_consenso_provisional':dict(Counter(r['funcion_consenso'] for r in accepted_rows)),
               'aceptaciones_por_regla':dict(Counter(r['regla_aceptacion'] for r in accepted_rows)),
               'por_modelo':coverage,
               'nota':'Acuerdo sintético, no exactitud. No se certifica Gold ni se asignan etiquetas humanas finales.'}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)

    def save_csv(name, records):
        # Cabecera aun cuando la cola está vacía.
        headers = list(records[0]) if records else list(consolidated[0])
        with (out/name).open('w', encoding='utf-8-sig', newline='') as f:
            writer=csv.DictWriter(f, fieldnames=headers)
            writer.writeheader(); writer.writerows(records)

    save_csv('anotaciones_por_modelo.csv', details)
    save_csv('dataset_consolidado.csv', consolidated)
    save_csv('cola_revision_humana.csv', review)
    save_csv('acuerdo_entre_modelos.csv', pairwise)
    (out/'dataset_consolidado.json').write_text(json.dumps(consolidated,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'metricas.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    provenance = {'created_at':aa._now(), 'source':str(Path(source).resolve()), 'source_sha256':template['sha256'],
                  'inputs':inputs, 'policy':{'mode':'min_votes' if min_votes is not None else 'strict_quality',
                  'min_votes':min_votes, 'min_responses':min_responses if min_votes is None else None,
                  'agreement_pair':agreement_pair, 'agreement_pair_only_fallback':True,
                  'agreement_threshold':agreement_threshold if min_votes is None else None,
                  'all_available_valid_and_evaluable':min_votes is None,
                  'both_providers_required':min_votes is None,'no_low_confidence':min_votes is None,
                  'audit_fraction':audit_fraction,'seed':seed},
                  'script_sha256':aa.digest(Path(__file__).read_bytes()), 'human_final_labels_assigned':False}
    (out/'procedencia.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'LEEME.md').write_text(
        '# Consolidación de anotaciones\n\n'
        'Los originales permanecen intactos. La decisión automática es un consenso provisional, no Gold humano.\n\n'
        'funcion_consenso contiene la respuesta aceptada por la regla; funcion_final queda reservada para humanos. '
        'Con la política min_votes, cuatro votos válidos bastan aunque haya alertas de calidad en otros modelos. '
        'alertas_calidad conserva esas observaciones sin bloquear el consenso.\n\n'
        'Si se configura agreement_pair, su coincidencia válida y Evaluable acepta filas pendientes, '
        'sin reemplazar consensos ya aceptados. regla_aceptacion distingue el criterio aplicado; '
        'funcion_consenso puede diferir de funcion_mas_votada en esta regla de pareja.\n\n'
        'dataset_consolidado.csv contiene una fila por entrada; anotaciones_por_modelo.csv conserva cada respuesta. '
        'cola_revision_humana.csv incluye desacuerdos y la muestra reproducible de auditoría de consensos. '
        'Completar final_evaluabilidad, funcion_final, revisor, fecha_revision y justificacion_revision en una copia. '
        'No editar las columnas de predicciones originales ni rellenar decisiones humanas automáticamente.\n\n'
        'La proporción usa todas las respuestas disponibles como denominador. El acuerdo por pares y entropía '
        'usan solo votos evaluables válidos; los CSV de métricas indican sus denominadores. '
        'Los motivos pueden superponerse. Los modelos no son jueces independientes y su confianza no está calibrada.\n\n'
        'Abrir CSV como texto/UTF-8 y no ejecutar fórmulas presentes en texto de fuentes. '
        'La copia JSON conserva tipos y campos sin interpretación de hoja de cálculo.\n', encoding='utf-8')
    return metrics
