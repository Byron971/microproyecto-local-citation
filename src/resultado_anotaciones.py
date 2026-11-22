"""Completa una copia de la plantilla original, sin alterar filas, hojas ni formatos."""
import argparse
import csv
import json
from pathlib import Path

from notebooks.anotacion_asistida import HEADER, LABELS, digest, fill_workbook, read_template, _write_atomic

CSV_FIELDS = ['context_id', *HEADER[7:11]]
PRIORITY = ['claude-opus-5-5','gpt-6-sol','claude-sonnet-5-5','gpt-5.4-mini','gpt-6-luna','gpt-4o-mini']
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / 'tmp/Tanda 1/TestGold_T1_v2_Zambrana.xlsx'


def human_results(path, allowed_ids):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError('El CSV debe tener exactamente los encabezados de revisión de la plantilla.')
        results = {}
        for r in reader:
            cid = r['context_id']
            if cid not in allowed_ids or cid in results:
                raise ValueError(f'ID ajeno a las pendientes o duplicado: {cid}')
            ev, function, confidence, reason = [r.get(k,'') or '' for k in CSV_FIELDS[1:]]
            if ev not in LABELS['evaluabilidad'] or confidence not in LABELS['confianza'] or not reason.strip():
                raise ValueError(f'Respuesta incompleta: {cid}')
            if (ev=='Evaluable' and function not in LABELS['funcion']) or (ev!='Evaluable' and function):
                raise ValueError(f'Función incompatible con evaluabilidad: {cid}')
            results[cid] = dict(evaluabilidad=ev,funcion=function,confianza=confidence,justificacion=reason)
    return results


def build_result(dataset, output, *, template=DEFAULT_TEMPLATE, reviews_csv=None):
    dataset, output, template = map(Path, (dataset, output, template))
    if output.resolve() == template.resolve():
        raise ValueError('No sobrescribir la plantilla original.')
    source = read_template(template)
    rows = json.loads(dataset.read_text(encoding='utf-8'))
    index = {r['context_id']:r for r in rows}
    if len(index)!=len(rows) or set(index)!={c['context_id'] for c in source['cases']}:
        raise ValueError('El consolidado no corresponde a las entradas de la plantilla.')
    if any(c['has_answers'] or not c['valid_target'] for c in source['cases']):
        raise ValueError('Usar plantilla original vacía y contextos TARGETCIT válidos.')
    results, selection = {}, {}
    for case in source['cases']:
        r=index[case['context_id']]
        if r['contexto_original']!=case['contexto'] or r['titulo_citado']!=case['titulo'] or r['resumen_citado']!=case['resumen']:
            raise ValueError('Textos distintos entre consolidado y plantilla.')
        if r['requiere_revision']:
            continue
        label=r['funcion_consenso']
        if label not in LABELS['funcion']:
            raise ValueError('Consenso sin función válida.')
        selected=next((m for m in PRIORITY if r.get(m+'__evaluabilidad')=='Evaluable'
                       and r.get(m+'__funcion')==label and r.get(m+'__confianza') in LABELS['confianza']
                       and r.get(m+'__justificacion','').strip()),None)
        if not selected:
            raise ValueError('No hay respuesta original de apoyo al consenso.')
        results[case['context_id']] = dict(evaluabilidad='Evaluable',funcion=label,
            confianza=r[selected+'__confianza'],justificacion=r[selected+'__justificacion'])
        selection[case['context_id']] = {'modelo_confianza_y_justificacion':selected,'regla':r['regla_aceptacion']}
    pending = {r['context_id'] for r in rows if r['requiere_revision']}
    imported = human_results(reviews_csv,pending) if reviews_csv else {}
    results.update(imported)
    # Parche XML acotado: el resto del archivo se copia intacto. No hay un motor
    # de edición de libros instalado; se reutiliza el escritor del proyecto.
    data,stats = fill_workbook(template,source['cases'],results)
    if output.exists():
        backup=output.with_name(output.stem+'.anterior.xlsx')
        if backup.exists():
            raise FileExistsError('Ya existe un respaldo anterior; elegir otro nombre de salida.')
        backup.write_bytes(output.read_bytes())
    output.parent.mkdir(parents=True,exist_ok=True)
    _write_atomic(output,data)
    metadata={'template':str(template.resolve()),'template_sha256':source['sha256'],
              'dataset':str(dataset.resolve()),'dataset_sha256':digest(dataset.read_bytes()),
              'automaticas':len(selection),'humanas_importadas':len(imported),
              'pendientes':len(pending)-len(imported),'orden':'plantilla_original',
              'selection':selection,'output_sha256':digest(data),
              'nota':'Confianza y justificación se copian de una respuesta que apoya el consenso, '
                     'en prioridad Opus, Sol, Sonnet, GPT-5.4 mini, Luna, GPT-4o mini. '
                     'No son confianza calibrada ni revisión humana. Excel recalcula Estado/Control al abrir.'}
    _write_atomic(output.with_suffix('.procedencia.json'),json.dumps(metadata,ensure_ascii=False,indent=2).encode())
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--template',default=DEFAULT_TEMPLATE,type=Path)
    parser.add_argument('--csv',type=Path)
    args=parser.parse_args()
    result=build_result(args.dataset,args.output,template=args.template,reviews_csv=args.csv)
    print(f"Automáticas: {result['automaticas']}; humanas importadas: {result['humanas_importadas']}; pendientes: {result['pendientes']}")


if __name__=='__main__':
    main()
