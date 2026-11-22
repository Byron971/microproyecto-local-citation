"""Descarga pública de la base fijada; no carga modelos ni ejecuta código remoto."""
import hashlib
import json
import re
import shutil
import urllib.request
from pathlib import Path

MODEL = 'Qwen/Qwen2.5-7B-Instruct'
ROOT = Path('/opt/citas/qlora/base')

def get(url):
    return urllib.request.urlopen(url, timeout=120)

def digest(path, algorithm='sha256', git=False):
    h = hashlib.new(algorithm)
    if git:
        h.update(f'blob {path.stat().st_size}\0'.encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

ROOT.mkdir(parents=True, exist_ok=True)
pin = ROOT / 'revision.json'
if pin.exists():
    metadata = json.loads(pin.read_text())
else:
    with get(f'https://huggingface.co/api/models/{MODEL}?blobs=true') as response:
        metadata = json.load(response)
    assert re.fullmatch(r'[0-9a-f]{40}', metadata['sha'])
    pin.write_text(json.dumps(metadata, indent=2))
revision = metadata['sha']
assert re.fullmatch(r'[0-9a-f]{40}', revision)
files = [f for f in metadata['siblings'] if re.fullmatch(
    r'(model(?:-\d+-of-\d+)?\.safetensors|model\.safetensors\.index\.json|config\.json|generation_config\.json|tokenizer(?:_config)?\.json|special_tokens_map\.json|added_tokens\.json|vocab\.json|merges\.txt|chat_template\.jinja)', f['rfilename'])]
names = {f['rfilename'] for f in files}
assert {'config.json', 'tokenizer.json', 'tokenizer_config.json', 'model.safetensors.index.json'} <= names
folder = ROOT / revision
folder.mkdir(exist_ok=True)
required = sum(f.get('lfs', {}).get('size', f.get('size', 0)) for f in files if not (folder / f['rfilename']).exists())
assert shutil.disk_usage(folder).free > required + 2 * 1024**3, 'Espacio insuficiente'
print(json.dumps({'model': MODEL, 'revision': revision, 'historical_revision_confirmed': False, 'download_bytes': required, 'files': len(files)}), flush=True)
report = []
for f in files:
    name = f['rfilename']
    path = folder / name
    lfs = f.get('lfs')
    expected = lfs['sha256'] if lfs else f['blobId']
    def valid(p):
        return p.exists() and digest(p, 'sha256' if lfs else 'sha1', not bool(lfs)) == expected
    if not valid(path):
        partial = path.with_name(name + '.partial')
        with get(f'https://huggingface.co/{MODEL}/resolve/{revision}/{name}') as source, partial.open('wb') as target:
            shutil.copyfileobj(source, target, 8 * 1024 * 1024)
        assert valid(partial), f'Hash incorrecto: {name}'
        partial.replace(path)
    report.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest(path), 'upstream_hash_verified': True})
    print('Verificado: ' + name, flush=True)
index = json.loads((folder / 'model.safetensors.index.json').read_text())
assert set(index['weight_map'].values()) <= names
result = {'model': MODEL, 'revision': revision, 'historical_revision_confirmed': False, 'root': str(folder), 'files': report, 'inference_verified': False}
(ROOT / 'manifest.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'status': 'verified', 'revision': revision, 'bytes': sum(f['bytes'] for f in report)}), flush=True)
