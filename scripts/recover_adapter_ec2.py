"""Extrae el adaptador descargado, verifica CRC y registra hashes sin entrenar."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import types
import zipfile

root = Path('/opt/citas/qlora')
archive = Path('/home/ubuntu/Downloads/qlora/qlora_citas_adapter_v1.zip')
notebook = archive.parent / 'finetune_qlora_citas.ipynb'
with archive.open('rb') as stream:
    archive_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
destination = root / 'adapters' / archive_sha
destination.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as zipped:
    items = zipped.infolist()
    if len(items) > 1000 or sum(x.file_size for x in items) > 2 * 1024**3:
        raise ValueError('Archivo fuera del tamaño previsto; revisar antes de extraer')
    names = [x.filename for x in items]
    if len(names) != len(set(names)):
        raise ValueError('Entradas duplicadas en el ZIP')
    for item in items:
        path = PurePosixPath(item.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
            raise ValueError('Ruta insegura en el ZIP')
    if zipped.testzip() is not None:
        raise ValueError('Error CRC del ZIP')
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix='extract-', dir=destination.parent) as directory:
            temporary = Path(directory)
            zipped.extractall(temporary)
            temporary.rename(destination)
configs = list(destination.rglob('adapter_config.json'))
inner_sha = None
nested_archives = list(destination.rglob('*.zip'))
if not configs and len(nested_archives) == 1:
    inner = nested_archives[0]
    with inner.open('rb') as stream:
        inner_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    inner_root = root / 'nested' / inner_sha
    inner_root.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(inner) as zipped:
        members = zipped.infolist()
        if len(members) > 1000 or sum(x.file_size for x in members) > 2 * 1024**3:
            raise ValueError('ZIP interior fuera del tamaño previsto')
        member_names = [x.filename for x in members]
        if len(member_names) != len(set(member_names)):
            raise ValueError('Entradas interiores duplicadas')
        for item in members:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Ruta insegura en ZIP interior')
        if zipped.testzip() is not None:
            raise ValueError('CRC del ZIP interior incorrecto')
        if not inner_root.exists():
            with tempfile.TemporaryDirectory(prefix='extract-', dir=inner_root.parent) as directory:
                temporary = Path(directory)
                zipped.extractall(temporary)
                temporary.rename(inner_root)
    configs = list(inner_root.rglob('adapter_config.json'))

if len(configs) != 1:
    print(json.dumps({'zip_entries': names, 'config_count': len(configs)}, indent=2), flush=True)
    raise ValueError('Se requiere exactamente un adapter_config.json')
adapter_root = configs[0].parent
module = types.ModuleType('adapter_audit')
exec(AUDITOR_SOURCE, module.__dict__)
report = module.auditar(adapter_root)
report.update({'archive_bytes': archive.stat().st_size, 'archive_sha256': archive_sha,
               'archive_crc_verified': True, 'adapter_root': str(adapter_root),
               'source': 'SharePoint -> Firefox en EC2', 'downloaded_in_ec2': True,
               'nested_archive_sha256': inner_sha})
if notebook.exists():
    with notebook.open('rb') as stream:
        report['notebook_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    data = json.loads(notebook.read_text())
    source = '\n'.join(''.join(c.get('source', [])) for c in data['cells'] if c['cell_type'] == 'code')
    report['notebook_base_model_literals'] = sorted(set(re.findall(r"BASE_MODEL\s*=\s*['\"]([^'\"]+)['\"]", source)))
    report['notebook_revision_explicitly_configured'] = bool(re.search(r'\brevision\s*=', source))
(root / 'recovered-adapter.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
