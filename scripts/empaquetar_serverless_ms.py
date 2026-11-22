"""Build a deterministic private SageMaker tarball from the fixed M/S allowlist.

Local only: never uploads, deploys or includes corpus annotations.
"""
import argparse
import gzip
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

from scripts.iniciar_ciencia import sha256

ROOT = Path(__file__).resolve().parents[1]


def empaquetar(root: Path, manifest: dict, output: Path) -> dict:
    root = root.resolve()
    files = manifest['files']
    names = [item['path'] for item in files]
    if len(names) != len(set(names)) or not files:
        raise ValueError('Inventario vacío o duplicado')
    for item in files:
        relative = PurePosixPath(item['path'])
        source = root / str(relative)
        if relative.is_absolute() or '..' in relative.parts or not source.resolve().is_relative_to(root):
            raise ValueError('Ruta fuera del repositorio')
        if source.stat().st_size != item['bytes'] or sha256(source) != item['sha256']:
            raise ValueError('Tamaño o SHA256 incorrecto: ' + item['path'])
    output = output.resolve()
    if any((root / name).resolve() == output for name in names):
        raise ValueError('La salida no puede reemplazar un artefacto')
    if output.exists():
        raise FileExistsError('La salida ya existe; no se reemplaza')
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: value for key, value in manifest.items() if key not in ('bucket', 'prefix')}
    partial = output.with_name(output.name + '.partial')
    try:
        with partial.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=1) as zipped:
            with tarfile.open(fileobj=zipped, mode='w|', dereference=True) as archive:
                for item in sorted(files, key=lambda entry: entry['path']):
                    source = root / item['path']
                    info = tarfile.TarInfo(item['path'])
                    info.size, info.mode, info.mtime = item['bytes'], 0o644, 0
                    with source.open('rb') as stream:
                        archive.addfile(info, stream)
                data = (json.dumps(payload, indent=2) + '\n').encode()
                info = tarfile.TarInfo('release.json')
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                archive.addfile(info, io.BytesIO(data))
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    return {'release_id': manifest['release_id'], 'files': len(files),
            'uncompressed_bytes': sum(item['bytes'] for item in files),
            'tar_bytes': output.stat().st_size, 'sha256': sha256(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = empaquetar(args.root, json.loads((args.root / 'config/ms_release.json').read_text()), args.output)
    print(json.dumps(result, indent=2))
