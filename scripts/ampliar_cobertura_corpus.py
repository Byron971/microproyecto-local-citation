"""Prepara cobertura del catálogo completo, sin modelos ni anotaciones.

Reanudable por revisión OCL y hashes; conserva íntegros los 37 artículos iniciales.
Procesa un snapshot local verificado, sin peticiones HTTP. Nunca se invoca desde peticiones HTTP.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time

from scripts.preparar_corpus_ms import fragmentar_ms

REVISION = '300ee6c5e5629d042bfc07cbc406e2f330b53659'
FRAGMENTACION = 'notebook 10: v2, 300 palabras, deduplicación; recorte posterior del prefijo a 100 fragmentos y 56000 caracteres incluyendo metadatos'


def recortar_texto(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if cut and limit < len(text) and not text[limit].isspace() and not cut[-1].isspace():
        boundary = cut.rfind(' ')
        if boundary >= limit // 2:
            cut = cut[:boundary].rstrip()
    return cut


def preparar_documento(pid, meta, raw, recortar=True):
    source = json.loads(raw)
    if not isinstance(source, dict) or source.get('paper_id') != pid:
        raise ValueError('Identidad OCL incorrecta')
    pdf = source.get('pdf_parse') or {}
    if not isinstance(pdf, dict):
        raise ValueError('Texto completo sin estructura de párrafos')
    body = pdf.get('body_text') or []
    if not isinstance(body, list) or any(not isinstance(p, dict) for p in body):
        raise ValueError('Estructura de párrafos inválida')
    paragraphs = [{'numero': i, 'texto': p['text'].strip(), 'seccion': str(p.get('section') or '').strip()}
                  for i, p in enumerate(body)
                  if isinstance(p.get('text'), str) and p['text'].strip()]
    if not paragraphs:
        raise ValueError('Sin párrafos de texto completo')
    chunks = fragmentar_ms(paragraphs)
    if not isinstance(meta.get('title'), str) or not isinstance(meta.get('abstract'), str) or not meta['title'].strip() or not meta['abstract'].strip():
        raise ValueError('Metadatos insuficientes')
    if len(chunks) < 3:
        raise ValueError('Menos de tres fragmentos distintos')
    title, abstract = meta['title'], meta['abstract']
    original_chunks = chunks
    original_chars = len(title) + len(abstract) + sum(len(c['texto']) for c in chunks)
    reasons = []
    if len(chunks) > 100: reasons.append('fragmentos')
    if original_chars > 56000: reasons.append('caracteres')
    if len(title) > 600: reasons.append('titulo')
    if len(abstract) > 12000: reasons.append('resumen')
    if any(len(c['seccion']) > 200 for c in chunks): reasons.append('seccion')
    if reasons and not recortar:
        raise ValueError('Excede el contrato sin recorte: '+','.join(reasons))
    if reasons:
        title, abstract = recortar_texto(title, 600), recortar_texto(abstract, 12000)
        budget = 56000 - len(title) - len(abstract)
        chunks = []
        for original in original_chunks[:100]:
            if budget <= 0: break
            text = recortar_texto(original['texto'], budget)
            if not text.strip(): break
            chunk = {**original, 'texto': text, 'seccion': recortar_texto(original['seccion'], 200), 'palabras': len(text.split())}
            if text != original['texto']:
                chunk['recortado'] = True
            chunks.append(chunk); budget -= len(text)
            if chunk.get('recortado'):
                break  # Never skip the remainder to append letters from later paragraphs.
    if len(chunks) < 3:
        raise ValueError('El presupuesto no permite tres fragmentos')
    result = dict(paper_id=pid, titulo=title, abstract=abstract, candidatos=chunks,
                fuente=f'https://huggingface.co/datasets/WINGNUS/ACL-OCL/resolve/{REVISION}/Base_JSON/prefix{pid[0]}/json/{pid[:3]}/{pid}.json',
                publicacion=f'https://aclanthology.org/{pid}/', sha256_ocl=hashlib.sha256(raw).hexdigest())
    if reasons:
        result['truncamiento'] = dict(aplicado=True, motivos=reasons, criterio='prefijo_en_orden_original',
            fragmentos_originales=len(original_chunks), fragmentos_analizados=len(chunks),
            caracteres_originales=original_chars, caracteres_analizados=len(title)+len(abstract)+sum(len(c['texto']) for c in chunks),
            texto_recortado=len(chunks)<len(original_chunks) or any(c.get('recortado') for c in chunks),
            sha256_titulo_original=hashlib.sha256(meta['title'].encode()).hexdigest(),
            sha256_resumen_original=hashlib.sha256(meta['abstract'].encode()).hexdigest())
    return result


def fetch(pid, meta, cache, source_directory, source_files, recortar=True):
    relative = f'Base_JSON/prefix{pid[0]}/json/{pid[:3]}/{pid}.json'
    if relative not in source_files:
        return dict(paper_id=pid, estado='no_encontrado'), None
    path = cache / (pid + '.json')
    if not path.exists():
        path = source_directory / relative
    try:
        if path.is_symlink() or path.stat().st_size > 10_000_000:
            raise ValueError('Documento demasiado grande o ruta insegura')
        raw = path.read_bytes()
        doc = preparar_documento(pid, meta, raw, recortar)
        return dict(paper_id=pid, estado='preparado', sha256_ocl=doc['sha256_ocl'],
                    recortado=bool(doc.get('truncamiento')), texto_recortado=bool(doc.get('truncamiento', {}).get('texto_recortado')),
                    fragmentos=len(doc['candidatos']), caracteres=sum(len(c['texto']) for c in doc['candidatos'])), doc
    except OSError as exc:
        return dict(paper_id=pid, estado='error_fuente', detalle=type(exc).__name__), None
    except (ValueError, KeyError, TypeError) as exc:
        return dict(paper_id=pid, estado='excluido', detalle=str(exc)), None


def guardar(db, doc, metadata=None):
    raw = json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode()
    digest = hashlib.sha256(raw).hexdigest()
    previous = db.execute('SELECT sha256_json FROM documentos WHERE paper_id=?', (doc['paper_id'],)).fetchone()
    if previous and previous[0] == digest:
        return
    db.execute('INSERT OR REPLACE INTO documentos VALUES (?,?,?,?,?,?)',
               (doc['paper_id'], (metadata or {}).get('title', doc['titulo']), (metadata or {}).get('abstract', doc['abstract']), len(doc['candidatos']),
                digest, gzip.compress(raw, mtime=0)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=8, choices=range(1, 9))
    parser.add_argument('--limit', type=int)
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--no-truncate', action='store_true')
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/coverage_expansion'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / 'cache' / REVISION
    cache.mkdir(parents=True, exist_ok=True)
    papers_raw = Path('data/raw/papers.json').read_bytes()
    papers = json.loads(papers_raw)
    source_files = None
    if args.source_directory:
        head = subprocess.check_output(['git', '-C', str(args.source_directory), 'rev-parse', 'HEAD'], text=True).strip()
        if head != REVISION:
            raise ValueError('El snapshot Git no corresponde a la revisión fijada')
        source_files = set(subprocess.check_output(['git', '-C', str(args.source_directory), 'ls-tree', '-r', '--name-only', 'HEAD', 'Base_JSON'], text=True).splitlines())
    base = json.loads(Path('config/corpus_ms.json').read_text())
    if base.get('revision_ocl') != REVISION:
        raise ValueError('Revisión de origen distinta')
    db = sqlite3.connect(args.output / 'corpus.sqlite')
    schema_version = db.execute('PRAGMA user_version').fetchone()[0]
    if schema_version not in (0, 1):
        raise ValueError('Esquema de corpus reanudado incompatible')
    if schema_version == 0:
        db.execute('PRAGMA user_version=1')
    db.execute('CREATE TABLE IF NOT EXISTS procedencia (nombre TEXT PRIMARY KEY, valor TEXT NOT NULL)')
    expected_source = {'revision_ocl': REVISION, 'sha256_papers': hashlib.sha256(papers_raw).hexdigest()}
    previous_source = dict(db.execute('SELECT nombre, valor FROM procedencia'))
    if previous_source and previous_source != expected_source:
        raise ValueError('La base reanudada pertenece a otra fuente o catálogo')
    if not previous_source:
        db.executemany('INSERT INTO procedencia VALUES (?,?)', expected_source.items())
    db.execute('CREATE TABLE IF NOT EXISTS documentos (paper_id TEXT PRIMARY KEY, titulo TEXT NOT NULL, abstract TEXT NOT NULL, total_fragmentos INTEGER NOT NULL, sha256_json TEXT NOT NULL, documento BLOB NOT NULL)')
    results_path = args.output / 'resultados.jsonl'
    previous = {}
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            try:
                row = json.loads(line); previous[row['paper_id']] = row
            except json.JSONDecodeError:
                pass
    for pid in papers:
        if not re.fullmatch(r'[A-Z][0-9]{2}-[0-9]{4}', pid):
            previous[pid] = dict(paper_id=pid, estado='excluido', detalle='ID fuera del formato de artículo admitido')
    prepared_ids = {r[0] for r in db.execute('SELECT paper_id FROM documentos')}
    for pid, doc in base['documentos'].items():
        guardar(db, doc, papers[pid])
        previous[pid] = dict(paper_id=pid, estado='preparado', sha256_ocl=doc['sha256_ocl'], fragmentos=len(doc['candidatos']), origen='corpus_inicial')
    db.commit()
    todo = [pid for pid in sorted(papers) if pid not in base['documentos'] and
            (args.reprocess or pid not in previous or previous[pid]['estado'] in ('error_red', 'error_fuente') or
             (previous[pid]['estado'] == 'preparado' and pid not in prepared_ids))]
    if args.limit:
        todo = todo[:args.limit]
    started = time.monotonic()
    with results_path.open('a') as report, ThreadPoolExecutor(max_workers=args.workers) as pool:
        processed = 0
        # Keep only a small number of decoded articles in memory.
        for offset in range(0, len(todo), args.workers * 2):
            futures = {pool.submit(fetch, pid, papers[pid], cache, args.source_directory, source_files, not args.no_truncate): pid for pid in todo[offset:offset + args.workers * 2]}
            for future in as_completed(futures):
                row, doc = future.result()
                futures.pop(future)
                if doc is not None:
                    guardar(db, doc, papers[row['paper_id']])
                else:
                    db.execute('DELETE FROM documentos WHERE paper_id=?', (row['paper_id'],))
                previous[row['paper_id']] = row
                report.write(json.dumps(row, ensure_ascii=False) + '\n'); report.flush()
                processed += 1
                if processed % 100 == 0:
                    db.commit()
                    print(json.dumps(dict(procesados=len(previous), pendientes=len(todo)-processed, estados=dict(Counter(r['estado'] for r in previous.values())), segundos=round(time.monotonic()-started))), flush=True)
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    count = db.execute('SELECT count(*) FROM documentos').fetchone()[0]
    db.close()
    results = dict(total_catalogo=len(papers), revision_ocl=REVISION, sha256_papers=hashlib.sha256(papers_raw).hexdigest(),
                   procesados=len(previous), preparados=count, estados=dict(Counter(r['estado'] for r in previous.values())),
                   recortados=sum(bool(r.get('recortado')) for r in previous.values()),
                   ejemplos_recortados=[pid for pid in sorted(previous) if previous[pid].get('texto_recortado')][:5],
                   motivos=dict(Counter(r.get('detalle','') for r in previous.values() if r['estado']=='excluido')),
                   preparation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   fragmentation_sha256=hashlib.sha256(Path('proyecto_de_grado/src/data/exportar_corpus_top3.py').read_bytes()).hexdigest(),
                   fragmentacion=FRAGMENTACION, resultados=[previous[p] for p in sorted(previous)])
    (args.output / 'cobertura.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in results.items() if k!='resultados'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
