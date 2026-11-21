"""Recalcula, de forma independiente al programa del repo, las métricas de la evaluación de modelos comerciales.

Lee los results.jsonl unidos (D:/tmp/costos/unido_<modelo>/), toma como predicción el argmax del vector de 9 puntajes
(el primero en caso de empate), y calcula F1 macro/micro, precisión y recall macro, accuracy, F1 por clase, matrices de
confusión, latencia, tokens y costo. Compara con el evaluation_summary.csv que escribió el programa del repo.
Salida: <destino>/ con resumen.csv, por_clase.csv, matrices/ y resumen.json.
Uso: python analizar.py <destino>
"""
import csv                                                        # leer y escribir CSV
import json                                                       # leer JSONL y escribir JSON
import statistics                                                 # mediana y cuantiles
import sys                                                        # argumentos
from collections import Counter, defaultdict                      # conteos
from pathlib import Path                                          # rutas

DESTINO = Path(sys.argv[1]); (DESTINO / 'matrices').mkdir(parents=True, exist_ok=True)
CL = ['Background', 'Gap', 'Basis', 'Comparison', 'Application', 'Improvement / Modification', 'Evidence',
      'Identification of the Originator', 'Further Reading']                  # orden de los prompts del proyecto
gold = {}
for i in range(1, 5):
    for linea in open(f'D:/tmp/costos/completo_{i}.jsonl', encoding='utf-8'):
        d = json.loads(linea); gold[d['id']] = d['gold']


def f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


filas, clases, resumen = [], [], {}
for modelo in ('gemini', 'openai'):
    registros = [json.loads(l) for l in open(f'D:/tmp/costos/unido_{modelo}/results.jsonl', encoding='utf-8')]
    repo = {r['prompt_name']: r for r in csv.DictReader(open(f'D:/tmp/costos/unido_{modelo}/metrics/evaluation_summary.csv', encoding='utf-8'))}
    for prompt in ('zero_shot_generic', 'zero_shot_detailed', 'few_shot'):
        rs = [r for r in registros if r['prompt_name'] == prompt]
        mat = [[0] * 9 for _ in range(9)]                          # filas = gold, columnas = predicción
        sin_parseo = 0
        for r in rs:
            p = r['parsed_output']
            if not isinstance(p, list) or len(p) != 9:
                sin_parseo += 1; continue
            pred = max(range(9), key=lambda k: (p[k], -k))         # argmax; en empate gana el primero
            mat[CL.index(gold[r['case_id']])][pred] += 1
        n = sum(map(sum, mat))
        tps = [mat[k][k] for k in range(9)]
        fps = [sum(mat[j][k] for j in range(9)) - mat[k][k] for k in range(9)]
        fns = [sum(mat[k]) - mat[k][k] for k in range(9)]
        por = [f1(tps[k], fps[k], fns[k]) for k in range(9)]
        f1_macro = sum(x[2] for x in por) / 9; p_macro = sum(x[0] for x in por) / 9; r_macro = sum(x[1] for x in por) / 9
        acc = sum(tps) / n
        lat = [r['latency_ms'] / 1000 for r in rs]
        cos = sum(r['estimated_cost_usd'] or 0 for r in rs)
        ent = statistics.mean(r['input_tokens'] for r in rs); sal = statistics.mean(r['output_tokens'] for r in rs)
        reg = repo[prompt]
        dif = abs(f1_macro - float(reg['f1_macro']))
        filas.append({'modelo': rs[0]['model'], 'proveedor': modelo, 'prompt': prompt, 'citas': n, 'sin_parseo': sin_parseo,
                      'f1_macro': round(f1_macro, 4), 'precision_macro': round(p_macro, 4), 'recall_macro': round(r_macro, 4),
                      'f1_micro_accuracy': round(acc, 4), 'latencia_mediana_s': round(statistics.median(lat), 2),
                      'latencia_p95_s': round(statistics.quantiles(lat, n=20)[18], 2), 'tokens_entrada_media': round(ent),
                      'tokens_salida_media': round(sal, 1), 'costo_total_usd': round(cos, 4), 'costo_por_llamada_usd': round(cos / len(rs), 6),
                      'costo_por_1000_citas_usd': round(cos / len(rs) * 1000, 3), 'f1_macro_repo': round(float(reg['f1_macro']), 4),
                      'diferencia_con_repo': round(dif, 6)})
        for k in range(9):
            clases.append({'proveedor': modelo, 'prompt': prompt, 'clase': CL[k], 'soporte': sum(mat[k]), 'precision': round(por[k][0], 4),
                           'recall': round(por[k][1], 4), 'f1': round(por[k][2], 4)})
        with open(DESTINO / 'matrices' / f'{modelo}__{prompt}.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(['gold \\ prediccion'] + CL)
            for k in range(9): w.writerow([CL[k]] + mat[k])
        resumen[f'{modelo}|{prompt}'] = {'mat': mat}
for nombre, datos, campos in (('resumen.csv', filas, list(filas[0])), ('por_clase.csv', clases, list(clases[0]))):
    with open(DESTINO / nombre, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos); w.writeheader(); w.writerows(datos)
json.dump({'resumen': filas}, open(DESTINO / 'resumen.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"{'modelo':22s} {'prompt':20s} {'F1 mac':>7s} {'P mac':>6s} {'R mac':>6s} {'acc':>6s} {'lat med':>7s} {'p95':>5s} {'USD/1000':>8s} {'dif repo':>9s}")
for x in filas:
    print(f"{x['modelo']:22s} {x['prompt']:20s} {x['f1_macro']:7.3f} {x['precision_macro']:6.3f} {x['recall_macro']:6.3f} {x['f1_micro_accuracy']:6.3f} {x['latencia_mediana_s']:7.2f} {x['latencia_p95_s']:5.2f} {x['costo_por_1000_citas_usd']:8.3f} {x['diferencia_con_repo']:9.6f}")
print('sin parseo:', sum(x['sin_parseo'] for x in filas), '| costo total USD:', round(sum(x['costo_total_usd'] for x in filas), 3))
