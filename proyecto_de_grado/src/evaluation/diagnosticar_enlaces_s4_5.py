"""S4.5: segunda auditoria de citas en ACL OCL, exclusivamente sobre VAL ya expuesto.

No reconstruye, no etiqueta y no modifica textos fuente ni archivos Gold.
Su CSV local informa spans bibliograficos candidatos en el parrafo y en el citante.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from proyecto_de_grado.src.data.validar_splits import load_split_index
from proyecto_de_grado.src.data.reconstruir_oraciones import grupo_ambiguo
from proyecto_de_grado.src.data.auditar_corpus import referencias_candidatas

BASE = Path('proyecto_de_grado/artifacts/evaluacion_s4/muestra_val_12_v1')
CACHE = Path('proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl')
RAW = Path('data/raw')
FIELDS = (
    'context_id', 'citing_id', 'cited_id', 'estado_s4_5', 'motivo_s4_5',
    'score_texto', 'parrafo_indice', 'refs_bibliografia',
    'spans_total_parrafo', 'spans_de_ref_en_parrafo',
    'spans_de_ref_en_todo_citante', 'otros_parrafos_con_ref',
    'spans_ref_en_parrafo_detalle', 'spans_ref_fuera_parrafo_detalle',
    'refs_de_todas_las_citas_en_parrafo', 'target_cerca_othercit_heuristica',
    'othercit_mismo_parentesis_visible', 'estado_parentesis',
    'nota_diagnostico',
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parentesis_target(masked: str) -> tuple[str, str]:
    """Solo inspecciona texto VISIBLE: un parentesis cortado no permite decidir."""
    if not isinstance(masked, str) or masked.count('TARGETCIT') != 1:
        raise ValueError('TARGETCIT debe aparecer exactamente una vez')
    pos = masked.index('TARGETCIT')
    izq = masked.rfind('(', 0, pos)
    der = masked.find(')', pos + len('TARGETCIT'))
    if izq < 0 or der < 0:
        return 'desconocido', 'parentesis_no_completo_en_contexto'
    # Si otro parentesis cierra antes del TARGET, no cubre necesariamente la cita.
    cierre_anterior = masked.rfind(')', 0, pos)
    apertura_siguiente = masked.find('(', pos + len('TARGETCIT'), der)
    if cierre_anterior > izq or apertura_siguiente >= 0:
        return 'desconocido', 'estructura_parentesis_ambigua'
    region = masked[izq:der+1]
    return ('si' if 'OTHERCIT' in region else 'no'), 'parentesis_visible'


def spans_por_ref(doc: dict, refs: set[str], pidx: int):
    cuerpo = (doc.get('pdf_parse') or {}).get('body_text')
    if not isinstance(cuerpo, list) or not 0 <= pidx < len(cuerpo):
        raise ValueError('parrafo fuera de rango')
    encontrados, todos_parrafo, ref_en_otros = [], [], []
    for j, p in enumerate(cuerpo):
        if not isinstance(p, dict) or not isinstance(p.get('text'), str):
            continue
        texto = p['text']
        for s in p.get('cite_spans') or []:
            if not isinstance(s, dict):
                continue
            ref = s.get('ref_id')
            ini, fin = s.get('start'), s.get('end')
            valido = (type(ini) is int and type(fin) is int
                      and 0 <= ini < fin <= len(texto))
            item = {'parrafo': j, 'ref_id': ref,
                    'start': ini, 'end': fin,
                    'offset_valido': valido,
                    'span_coincide_texto': bool(valido and texto[ini:fin] == s.get('text'))}
            if j == pidx:
                todos_parrafo.append(item)
            if isinstance(ref, str) and ref in refs:
                encontrados.append(item)
                if j != pidx:
                    ref_en_otros.append(item)
    return encontrados, todos_parrafo, ref_en_otros


def resumen_spans(items: list[dict], limite: int = 14) -> str:
    resultado = []
    for x in items[:limite]:
        resultado.append(f"p{x['parrafo']}:{x['ref_id']}@{x['start']}-{x['end']}"
                         f"[offset={'ok' if x['offset_valido'] else 'error'},"
                         f"texto={'ok' if x['span_coincide_texto'] else 'distinto'}]")
    if len(items) > limite:
        resultado.append(f'... {len(items)-limite} spans adicionales')
    return '; '.join(resultado)


def verificar_fuentes(manifiesto: dict, raw: Path):
    hashes = manifiesto.get('sha256_fuentes')
    if not isinstance(hashes, dict):
        raise ValueError('Manifiesto sin huellas de origen')
    for file in ('contexts.json', 'papers.json', 'train.json', 'val.json', 'test.json'):
        expected = hashes.get(file)
        if not isinstance(expected, str) or sha(raw/file) != expected:
            raise ValueError(f'La fuente {file} no coincide con el manifiesto')


def diagnosticar(base: Path, raw: Path, cache: Path) -> list[dict]:
    manifiesto = json.loads((base/'manifiesto.json').read_text(encoding='utf-8-sig'))
    verificar_fuentes(manifiesto, raw)
    ids = manifiesto.get('ids_preseleccionados', [])
    if len(ids) != 12 or len(set(ids)) != 12:
        raise ValueError('Se esperaban doce contextos VAL distintos')
    index = load_split_index(raw)
    papers = json.loads((raw/'papers.json').read_text(encoding='utf-8-sig'))
    previo_path = base/'reconstrucciones_preliminares_s4_5.jsonl'
    previos = [json.loads(linea) for linea in previo_path.read_text(encoding='utf-8-sig').splitlines() if linea.strip()]
    if len(previos) != 12 or {x['context_id'] for x in previos} != set(ids):
        raise ValueError('El reporte S4.5 no coincide con la muestra')
    por_id = {x['context_id']: x for x in previos}
    filas = []
    for cid in ids:
        if index.by_context.get(cid) != 'val':
            raise ValueError(f'No pertenece a val: {cid}')
        ctx = index.contexts[cid]
        previo = por_id[cid]
        if (previo.get('citing_id'), previo.get('cited_id'), previo.get('contexto_acl200')) != (
            ctx['citing_id'], ctx['refid'], ctx['masked_text']):
            raise ValueError(f'Incoherencia ACL-200: {cid}')
        path_doc = cache/f"{ctx['citing_id']}.json"
        doc = json.loads(path_doc.read_text(encoding='utf-8-sig'))
        if doc.get('paper_id') != ctx['citing_id']:
            raise ValueError(f'ID citante invalido: {cid}')
        pidx = previo.get('parrafo_indice')
        if type(pidx) is not int:
            raise ValueError(f'Parrafo S4.5 no disponible: {cid}')
        titulo = (papers.get(ctx['refid']) or {}).get('title') or ''
        refs = set(referencias_candidatas(doc, titulo))
        spans_ref, spans_parrafo, externos = spans_por_ref(doc, refs, pidx)
        same_p = [s for s in spans_ref if s['parrafo'] == pidx]
        contiene_other, estado_par = parentesis_target(ctx['masked_text'])
        filas.append({
            'context_id': cid, 'citing_id': ctx['citing_id'], 'cited_id': ctx['refid'],
            'estado_s4_5': previo.get('estado'), 'motivo_s4_5': previo.get('motivo'),
            'score_texto': previo.get('score_texto'), 'parrafo_indice': pidx,
            'refs_bibliografia': ';'.join(sorted(refs)),
            'spans_total_parrafo': len(spans_parrafo),
            'spans_de_ref_en_parrafo': len(same_p),
            'spans_de_ref_en_todo_citante': len(spans_ref),
            'otros_parrafos_con_ref': len(set(s['parrafo'] for s in externos)),
            'spans_ref_en_parrafo_detalle': resumen_spans(same_p),
            'spans_ref_fuera_parrafo_detalle': resumen_spans(externos),
            'refs_de_todas_las_citas_en_parrafo': ';'.join(sorted(set(str(x['ref_id']) for x in spans_parrafo))),
            'target_cerca_othercit_heuristica': 'si' if grupo_ambiguo(ctx['masked_text']) else 'no',
            'othercit_mismo_parentesis_visible': contiene_other,
            'estado_parentesis': estado_par,
            'nota_diagnostico': 'No se adjudica correspondencia ni funcion de cita; requiere contraste humano con ACL OCL.',
        })
    return filas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=BASE)
    ap.add_argument('--raw', type=Path, default=RAW)
    ap.add_argument('--cache', type=Path, default=CACHE)
    ap.add_argument('--out', type=Path, default=BASE/'diagnostico_spans_s4_5_v1.csv')
    args = ap.parse_args(argv)
    if args.out.exists():
        ap.error('El CSV de salida ya existe; nunca se sobrescribe')
    try:
        filas = diagnosticar(args.base, args.raw, args.cache)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(filas)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        ap.exit(2, f'S4.5 DIAGNOSTICO: {e}\n')
    print('=== S4.5 SEGUNDA AUDITORIA — NO GOLD ===')
    for x in filas:
        print(f"{x['context_id']} | {x['motivo_s4_5'] or 'candidata'} | "
              f"spans_ref_parrafo={x['spans_de_ref_en_parrafo']} | "
              f"spans_ref_doc={x['spans_de_ref_en_todo_citante']} | "
              f"OTHERCIT_mismo_parentesis_visible={x['othercit_mismo_parentesis_visible']}")
    print('=== RESUMEN ===')
    print('Casos:', len(filas))
    print('Con spans bib candidatos en el parrafo:', sum(x['spans_de_ref_en_parrafo']>0 for x in filas))
    print('Sin spans bib candidatos en el parrafo:', sum(x['spans_de_ref_en_parrafo']==0 for x in filas))
    print('CSV:', args.out)
    print('No se alteraron datos de entrenamiento, val, test, Gold ni anotaciones.')

if __name__ == '__main__':
    main()
