"""Prepara en EC2 dos ZIP públicos y los publica bajo models/ del sitio.

Allowlist: un clasificador, su manifiesto de entrenamiento, snapshot SciBERT
fijado y manifiesto del encoder por archivo. Nunca incluye corpus ni predicciones.
Ejecutar en el constructor autorizado; sus credenciales proceden del rol EC2.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

RELEASE = 'ms-scibert-b8ee47317c29afbc'
SNAPSHOT = 'artifacts/huggingface/hub/models--allenai--scibert_scivocab_uncased/snapshots/24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1/'
WEB_BUCKET = 'citas-api-web-646941583111-us-east-1'
ENCODER = 'proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != name:
        raise ValueError('Ruta inválida en el inventario')
    return p


def package(root, files, destination, metadata):
    """ZIP reproducible, con rutas relativas y manifiesto SHA-256 por modelo."""
    inventory = []
    for name in sorted(files):
        safe_relative(name)
        file = root / name
        if file.is_symlink() or not file.is_file():
            raise ValueError('Archivo ausente o enlace simbólico: ' + name)
        inventory.append({'path': name, 'bytes': file.stat().st_size, 'sha256': sha256(file)})
    partial = destination.with_suffix('.zip.partial')
    payload = {**metadata, 'files': inventory}
    with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for item in inventory:
            info = zipfile.ZipInfo(item['path'], date_time=(2026, 11, 23, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info._compresslevel = 1
            info.external_attr = 0o100644 << 16
            with (root / item['path']).open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
                shutil.copyfileobj(source, target, 8 * 1024 * 1024)
        info = zipfile.ZipInfo('config/public_model_' + metadata['track'] + '.json', date_time=(2026, 11, 23, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(partial) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP corrupto')
    partial.replace(destination)
    return {'track': metadata['track'], 'file': destination.name, 'bytes': destination.stat().st_size,
            'sha256': sha256(destination), 'uncompressed_bytes': sum(i['bytes'] for i in inventory), 'files': inventory}


def index_html(reports):
    rows = ''.join('<tr><td>Modelo ' + r['track'] + '</td><td><a href="' + html.escape(r['path']) + '">Descargar ZIP</a></td><td>'
                   + f"{r['bytes'] / 1e6:.1f} MB" + '</td><td><code>' + r['sha256'] + '</code></td></tr>' for r in reports)
    return '''<!doctype html><html lang="es"><meta charset="utf-8"><base href="/models/"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modelos M/S · Grupo 19</title><style>body{font:17px/1.6 system-ui,sans-serif;max-width:1100px;margin:3rem auto;padding:0 1rem;color:#17263b}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ccd3dd}code{font-size:12px;overflow-wrap:anywhere}a{color:#244bc3}.scroll{overflow-x:auto}</style>
<h1>Descarga de modelos M/S</h1><p>Clasificadores de función de cita del Grupo 19, Maestría en Inteligencia Artificial, Universidad de los Andes.</p>
<p>Cada ZIP contiene el checkpoint de una pista, su manifiesto de entrenamiento y el snapshot SciBERT fijado, con sus archivos de configuración y vocabulario. Los archivos compartidos son idénticos en ambos ZIP. No se incluyen corpus ni anotaciones individuales.</p>
<div class="scroll"><table><thead><tr><th>Clasificador</th><th>Archivo</th><th>Tamaño</th><th>SHA-256 del ZIP</th></tr></thead><tbody>''' + rows + '''</tbody></table></div>
<p><a href="releases/''' + RELEASE + '''/manifest.json">Inventario y hashes</a> · <a href="releases/''' + RELEASE + '''/SHA256SUMS">SHA256SUMS</a></p>
<h2>Uso</h2><p>Descargar los dos ZIP y extraerlos en la raíz del repositorio. Verificar los hashes antes de cargar los modelos. Las instrucciones de entorno, corpus y ejecución están en el <a href="https://github.com/Byron971/microproyecto-local-citation">README del proyecto</a>.</p>
<p>Se conserva el README del modelo base SciBERT dentro del snapshot. Los resultados son predicciones académicas y no sustituyen la revisión de las fuentes.</p><p><a href="/">Volver a la aplicación</a></p></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', type=Path, default=Path('/opt/citas/microproyecto-local-citation'))
    parser.add_argument('--root', type=Path, default=Path('/opt/citas/models') / RELEASE)
    parser.add_argument('--output', type=Path, default=Path('/opt/citas/public-models') / RELEASE)
    parser.add_argument('--encoder-sha256', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    import boto3
    session = boto3.Session(region_name='us-east-1')
    if session.client('sts').get_caller_identity()['Account'] != '646941583111':
        raise RuntimeError('Cuenta AWS inesperada')
    manifest = json.loads((args.repo / 'config/ms_release.json').read_text())
    if manifest['release_id'] != RELEASE:
        raise ValueError('Release inesperada')
    s3 = session.client('s3')
    remote = json.loads(s3.get_object(Bucket=manifest['bucket'], Key=manifest['prefix'] + 'release.json')['Body'].read())
    if remote != {k: v for k, v in manifest.items() if k not in ('bucket', 'prefix')}:
        raise ValueError('Inventario remoto diferente')
    args.root.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    for item in manifest['files']:
        name = item['path']
        safe_relative(name)
        if not (name.startswith(SNAPSHOT) or name in [f'proyecto_de_grado/artifacts/experimentos_10/{t}/{n}' for t in ['M', 'S'] for n in ['model.safetensors', 'manifiesto_entrenamiento.json']]):
            raise ValueError('Archivo fuera de la allowlist')
        target = args.root / name
        if not target.is_file() or target.stat().st_size != item['bytes'] or sha256(target) != item['sha256']:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.partial')
            s3.download_file(manifest['bucket'], manifest['prefix'] + name, str(temporary))
            if temporary.stat().st_size != item['bytes'] or sha256(temporary) != item['sha256']:
                raise ValueError('Artefacto descargado diferente del manifiesto')
            temporary.replace(target)
    encoder_source = args.repo / ENCODER
    if sha256(encoder_source) != args.encoder_sha256:
        raise ValueError('Manifiesto de recuperación diferente del revisado')
    (args.root / ENCODER).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(encoder_source, args.root / ENCODER)
    reports = []
    for track in ['M', 'S']:
        names = [x['path'] for x in manifest['files'] if x['path'].startswith(SNAPSHOT) or x['path'].startswith(f'proyecto_de_grado/artifacts/experimentos_10/{track}/')]
        names.append(ENCODER)
        result = package(args.root, names, args.output / ('modelo-' + track + '.zip'),
                         {'release_id': RELEASE, 'track': track, 'scibert_revision': manifest['scibert_revision']})
        result['path'] = 'releases/' + RELEASE + '/' + result['file']
        reports.append(result)
        print(json.dumps({'prepared': track, 'bytes': result['bytes'], 'sha256': result['sha256']}), flush=True)
    summary = {'release_id': RELEASE, 'source': 'S3 -> EC2 -> S3/CloudFront', 'models': reports}
    (args.output / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'SHA256SUMS').write_text(''.join(r['sha256'] + '  ' + r['file'] + '\n' for r in reports))
    (args.output / 'index.html').write_text(index_html(reports))
    if args.publish:
        from boto3.s3.transfer import TransferConfig
        transfer = TransferConfig(multipart_threshold=64*1024*1024, multipart_chunksize=32*1024*1024, max_concurrency=4)
        for name in ['modelo-M.zip', 'modelo-S.zip', 'manifest.json', 'SHA256SUMS']:
            file = args.output / name
            key = 'models/releases/' + RELEASE + '/' + name
            metadata = {'sha256': sha256(file)}
            extra = {'ContentType': 'application/zip' if name.endswith('.zip') else ('application/json' if name.endswith('.json') else 'text/plain; charset=utf-8'),
                     'CacheControl': 'public,max-age=31536000,immutable', 'Metadata': metadata}
            if name.endswith('.zip'):
                extra['ContentDisposition'] = 'attachment; filename="' + name + '"'
            s3.upload_file(str(file), WEB_BUCKET, key, ExtraArgs=extra, Config=transfer)
            head = s3.head_object(Bucket=WEB_BUCKET, Key=key)
            if head['ContentLength'] != file.stat().st_size or head['Metadata'].get('sha256') != metadata['sha256']:
                raise ValueError('Publicación no coincide con el archivo local')
        # Publicar el índice solo después de verificar los dos ZIP.
        s3.upload_file(str(args.output / 'index.html'), WEB_BUCKET, 'models/index.html',
                       ExtraArgs={'ContentType': 'text/html; charset=utf-8', 'CacheControl': 'no-cache,max-age=0,must-revalidate'})
        summary['published'] = True
    (args.output / 'publication.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print('PUBLICATION=' + json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
