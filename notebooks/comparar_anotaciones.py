"""Compara predicciones originales; el consenso no certifica exactitud ni Gold humano."""
import csv
import json
from collections import Counter
from pathlib import Path


def compare(prediction_files, destination):
    runs = [json.loads(Path(p).read_text(encoding='utf-8')) for p in prediction_files]
    if len(runs) < 2:
        raise ValueError('Seleccionar al menos dos experimentos explícitamente.')
    if len({r['source_sha256'] for r in runs}) != 1:
        raise ValueError('Las predicciones deben corresponder al mismo Excel original.')
    models = [r['model'] for r in runs]
    if len(set(models)) != len(models):
        raise ValueError('Seleccionar un solo experimento por modelo para evitar votos duplicados.')
    ids = runs[0]['context_ids']
    if any(r['context_ids'] != ids for r in runs):
        raise ValueError('Los experimentos no tienen el mismo conjunto y orden de entradas.')
    rows = []
    for cid in ids:
        results = [r['results'].get(cid) for r in runs]
        votes = Counter(r['funcion'] for r in results if r and r['evaluabilidad'] == 'Evaluable')
        label, count = votes.most_common(1)[0] if votes else ('', 0)
        complete = all(r is not None for r in results)
        # Mayoría estricta de TODOS los modelos, solo con cobertura completa.
        consensus = label if complete and count > len(runs) / 2 else ''
        unanimous = complete and count == len(runs)
        row = {'context_id': cid, 'cobertura_completa': complete,
               'consenso_propuesto': consensus, 'votos': count,
               'requiere_revision': not unanimous or any(r and r['confianza'] == 'Baja' for r in results),
               'nota': 'Consenso sintético; no implica mayor exactitud ni validación humana.'}
        for model, result in zip(models, results):
            row[model] = json.dumps(result, ensure_ascii=False) if result else ''
        rows.append(row)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output
