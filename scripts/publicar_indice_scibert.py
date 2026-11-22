"""Publish a completed index, verify S3 bytes, then publish the release inventory."""
import argparse
import hashlib
import json
from pathlib import Path


def publicar(root, client, bucket):
    index = json.loads((root / 'indice.json').read_text())
    if index['total_articulos'] != 19776:
        raise ValueError('El índice debe cubrir los 19.776 artículos del catálogo')
    files = []
    for name in ['papers.json', 'embeddings.npy', 'indice.json']:
        path = root / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if name != 'indice.json' and index['files'][name] != digest:
            raise ValueError('El índice local no supera sus hashes')
        files.append({'path': 'artifacts/scientific_search/' + name,
                      'bytes': path.stat().st_size, 'sha256': digest})
    release_id = 'search-scibert-' + hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {'schema_version': 1, 'scibert_revision': index['revision_scibert'],
                'perfil': index['perfil'], 'total_articulos': index['total_articulos'],
                'files': files, 'release_id': release_id, 'bucket': bucket, 'prefix': 'releases/' + release_id + '/'}
    for item in files:
        key = manifest['prefix'] + item['path']
        try:
            previous = client.get_object(Bucket=bucket, Key=key)['Body'].read()
            if hashlib.sha256(previous).hexdigest() != item['sha256']:
                raise ValueError('La release remota existente tiene contenido distinto')
        except client.exceptions.NoSuchKey:
            client.upload_file(str(root / Path(item['path']).name), bucket, key,
                               ExtraArgs={'ServerSideEncryption': 'AES256'})
        remote = client.get_object(Bucket=bucket, Key=key)['Body'].read()
        if len(remote) != item['bytes'] or hashlib.sha256(remote).hexdigest() != item['sha256']:
            raise ValueError('No se pudo verificar el índice desde S3')
    inventory = {k: v for k, v in manifest.items() if k not in ['bucket', 'prefix']}
    key = manifest['prefix'] + 'release.json'
    try:
        previous = json.loads(client.get_object(Bucket=bucket, Key=key)['Body'].read())
        if previous != inventory:
            raise ValueError('El inventario remoto existente difiere')
    except client.exceptions.NoSuchKey:
        client.put_object(Bucket=bucket, Key=key, Body=json.dumps(inventory).encode(),
                          ContentType='application/json', ServerSideEncryption='AES256')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directorio', type=Path, default=Path('artifacts/scientific_search'))
    parser.add_argument('--bucket', default='citas-api-models-646941583111-us-east-1')
    parser.add_argument('--salida', type=Path, default=Path('config/search_release.json'))
    args = parser.parse_args()
    import boto3
    client = boto3.client('s3', region_name='us-east-1')
    manifest = publicar(args.directorio, client, args.bucket)
    args.salida.write_text(json.dumps(manifest, indent=2))
    print(manifest['release_id'], sum(f['bytes'] for f in manifest['files']), 'bytes verificados desde S3')
