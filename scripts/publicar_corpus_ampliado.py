"""Publica un corpus validado e inmutable; no modifica recursos de infraestructura."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from src.app.corpus_store import IndexedCorpus
from scripts.ampliar_cobertura_corpus import preparar_documento


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def manifest_for(root, bucket):
    report = json.loads((root/'cobertura.json').read_text())
    if report['procesados'] != report['total_catalogo'] or sum(report['estados'].get(s, 0) for s in ['error_red','error_fuente']):
        raise ValueError('La cobertura debe estar auditada para todo el catálogo y sin errores de red pendientes')
    path = root/'corpus.sqlite'
    digest = sha256(path)
    store = IndexedCorpus(path, digest, report['preparados'])
    papers = json.loads(Path('data/raw/papers.json').read_text())
    if {r['paper_id'] for r in report['resultados']} != set(papers) or hashlib.sha256(Path('data/raw/papers.json').read_bytes()).hexdigest() != report['sha256_papers']:
        raise ValueError('El informe no cubre el catálogo de origen')
    base = json.loads(Path('config/corpus_ms.json').read_text())['documentos']
    for pid, metadata in store.metadata():
        if metadata['titulo'] != papers[pid]['title'] or metadata['abstract'] != papers[pid]['abstract']:
            raise ValueError('Metadatos de catálogo distintos: '+pid)
    for number, pid in enumerate(store, 1):
        doc = store[pid]  # Validar también cada cuerpo, no solo metadatos.
        raw_source = (root/'cache'/report['revision_ocl']/(pid+'.json')).read_bytes()
        if hashlib.sha256(raw_source).hexdigest() != doc['sha256_ocl'] or preparar_documento(pid, papers[pid], raw_source) != doc:
            raise ValueError('El artículo no coincide con sus párrafos/secciones de origen: '+pid)
        if pid in base and doc != base[pid]:
            raise ValueError('El corpus inicial fue modificado: '+pid)
        if number % 2000 == 0:
            print(f'Auditados {number}/{len(store)} artículos frente a la fuente', flush=True)
    inventory = dict(schema_version=1, corpus_schema=2, total_articulos=len(store), total_catalogo=report['total_catalogo'],
                total_recortados=report.get('recortados', 0), ejemplos_recortados=report.get('ejemplos_recortados', []),
                revision_ocl=report['revision_ocl'], licencia='CC-BY-NC-4.0', fragmentacion=report['fragmentacion'],
                source_papers_sha256=report['sha256_papers'], preparation_sha256=report['preparation_sha256'],
                fragmentation_sha256=report['fragmentation_sha256'],
                files=[dict(path='artifacts/coverage_expansion/corpus.sqlite',bytes=path.stat().st_size,sha256=digest)])
    rid = 'corpus-ms-'+hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()[:16]
    return {**inventory,'release_id':rid,'bucket':bucket,'prefix':'releases/'+rid+'/'}



def publish(root, manifest, client):
    bucket = manifest['bucket']; prefix=manifest['prefix']
    for item in manifest['files']:
        key=prefix+item['path']
        try:
            remote=client.get_object(Bucket=bucket,Key=key)
        except client.exceptions.NoSuchKey:
            client.upload_file(str(root/Path(item['path']).name),bucket,key,ExtraArgs={'ServerSideEncryption':'AES256'})
            remote=client.get_object(Bucket=bucket,Key=key)
        digest=hashlib.sha256(); size=0
        for chunk in remote['Body'].iter_chunks(1024*1024):
            digest.update(chunk);size+=len(chunk)
        remote['Body'].close()
        if digest.hexdigest()!=item['sha256'] or size!=item['bytes']:
            raise ValueError('El artefacto remoto no coincide con el inventario')
    inventory={k:v for k,v in manifest.items() if k not in ['bucket','prefix']}
    key=prefix+'release.json'
    try:
        previous=json.loads(client.get_object(Bucket=bucket,Key=key)['Body'].read())
        if previous!=inventory:
            raise ValueError('Existe otra release con ese identificador')
    except client.exceptions.NoSuchKey:
        client.put_object(Bucket=bucket,Key=key,Body=json.dumps(inventory).encode(),ContentType='application/json',ServerSideEncryption='AES256')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('artifacts/coverage_expansion'))
    p.add_argument('--bucket',default='citas-api-models-646941583111-us-east-1')
    p.add_argument('--output',type=Path,default=Path('config/corpus_release.json'))
    p.add_argument('--local-only',action='store_true')
    args=p.parse_args()
    manifest=manifest_for(args.root,args.bucket)
    print(f'Auditoría completa: {manifest["total_articulos"]} artículos', flush=True)
    if not args.local_only:
        print('Publicando y verificando el artefacto remoto...', flush=True)
        import boto3
        from botocore.config import Config
        publish(args.root,manifest,boto3.client('s3',region_name='us-east-1',config=Config(connect_timeout=5,read_timeout=30,retries={'max_attempts':2})))
    args.output.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'articulos':manifest['total_articulos'],'bytes':manifest['files'][0]['bytes'],'release':manifest['release_id'],'publicado':not args.local_only}))


if __name__=='__main__':
    main()
