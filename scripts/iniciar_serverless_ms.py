"""Validate the pre-extracted SageMaker bundle, then serve without AWS credentials."""
import json
import os
from pathlib import Path, PurePosixPath
import sys

from scripts.iniciar_ciencia import sha256


def validar(root: Path, expected: dict) -> None:
    root = root.resolve()
    payload = {key: value for key, value in expected.items() if key not in ('bucket', 'prefix')}
    if json.loads((root / 'release.json').read_text()) != payload:
        raise RuntimeError('El bundle no corresponde a la release fijada en la imagen')
    for entry in expected['files']:
        relative = PurePosixPath(entry['path'])
        target = root / str(relative)
        if relative.is_absolute() or '..' in relative.parts or not target.resolve().is_relative_to(root):
            raise ValueError('Ruta fuera del bundle')
        if not target.is_file() or target.stat().st_size != entry['bytes'] or sha256(target) != entry['sha256']:
            raise RuntimeError('Artefacto ausente o corrupto: ' + entry['path'])


def main():
    if sys.argv[1:] not in ([], ['serve']):
        raise SystemExit('Este contenedor solo admite serve')
    root = Path(os.environ.get('MS_MODEL_ROOT', '/opt/ml/model'))
    manifest = json.loads(Path('/app/config/ms_release.json').read_text())
    validar(root, manifest)
    os.environ.update({
        'HF_HOME': str(root / 'artifacts/huggingface'),
        'MS_ARTIFACTS_DIR': str(root / 'proyecto_de_grado/artifacts/experimentos_10'),
        'MS_RELEASE_ID': manifest['release_id'], 'MS_ENABLE_GLOBAL_SEARCH': '0',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
    })
    os.execvp('python', ['python', '-m', 'uvicorn', 'src.app.serverless_main:app',
                        '--host', '0.0.0.0', '--port', '8080', '--workers', '1', '--no-access-log'])


if __name__ == '__main__':
    main()
