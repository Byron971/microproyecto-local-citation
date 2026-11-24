"""Recupera la release M/S de S3 y prepara el bundle privado en EC2."""
import json
from pathlib import Path
import sys

import boto3

REPO = Path('/opt/citas/microproyecto-local-citation')
sys.path.insert(0, str(REPO))
from scripts.iniciar_ciencia import preparar, sha256
from scripts.empaquetar_serverless_ms import empaquetar
from scripts.iniciar_serverless_ms import validar


def main():
    session = boto3.Session(region_name='us-east-1')
    if session.client('sts').get_caller_identity()['Account'] != '646941583111':
        raise RuntimeError('Cuenta AWS inesperada')
    manifest = json.loads((REPO / 'config/ms_release.json').read_text())
    if manifest['release_id'] != 'ms-scibert-b8ee47317c29afbc':
        raise RuntimeError('Release inesperada')
    root = Path('/opt/citas/models') / manifest['release_id']
    root.mkdir(parents=True, exist_ok=True)
    preparar(session.client('s3'), manifest, root)
    payload = {k: v for k, v in manifest.items() if k not in ('bucket', 'prefix')}
    (root / 'release.json').write_text(json.dumps(payload, indent=2) + '\n')
    validar(root, manifest)
    bundle = root.parent / (manifest['release_id'] + '.tar.gz')
    expected_sha = 'b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f'
    if bundle.exists():
        if sha256(bundle) != expected_sha:
            raise RuntimeError('Bundle existente distinto; no se reemplaza')
        result = {'release_id': manifest['release_id'], 'files': len(manifest['files']),
                  'uncompressed_bytes': sum(f['bytes'] for f in manifest['files']),
                  'tar_bytes': bundle.stat().st_size, 'sha256': expected_sha}
    else:
        result = empaquetar(root, manifest, bundle)
    result.update({'root': str(root), 'bundle': str(bundle), 'files_verified': True,
                   'matches_local_bundle': result['sha256'] == expected_sha,
                   'source': 'S3 -> EC2', 'uploaded': False})
    (root.parent / 'prepared-models.json').write_text(json.dumps(result, indent=2))
    if not result['matches_local_bundle']:
        raise RuntimeError('Los archivos son correctos, pero el tar difiere del paquete local; revisar informe')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
