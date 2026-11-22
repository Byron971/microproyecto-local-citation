"""Inventario verificable de un adaptador existente; no carga ni entrena modelos."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def auditar(root):
    root = root.resolve(strict=True)
    config_path = root / 'adapter_config.json'
    config = json.loads(config_path.read_text())
    base = config.get('base_model_name_or_path')
    if base != 'Qwen/Qwen2.5-7B-Instruct':
        raise ValueError('Base distinta de la esperada: revisar sin sustituirla')
    if config.get('peft_type') != 'LORA':
        raise ValueError('El adaptador no declara LORA')
    weights = root / 'adapter_model.safetensors'
    with weights.open('rb') as stream:
        raw = stream.read(8)
        if len(raw) != 8:
            raise ValueError('Cabecera safetensors incompleta')
        header_size = struct.unpack('<Q', raw)[0]
        if not 0 < header_size < min(weights.stat().st_size - 8, 16 * 1024 * 1024):
            raise ValueError('Tamaño de cabecera safetensors inválido')
        header = json.loads(stream.read(header_size))
    tensors = {k: v for k, v in header.items() if k != '__metadata__'}
    if not tensors or not any('lora_A' in k for k in tensors) or not any('lora_B' in k for k in tensors):
        raise ValueError('No hay matrices LoRA A/B verificables')
    data_size = weights.stat().st_size - 8 - header_size
    for name, info in tensors.items():
        start, end = info['data_offsets']
        if not (0 <= start <= end <= data_size):
            raise ValueError('Tensor fuera del archivo: ' + name)
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Revisar enlace simbólico antes de inventariar')
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        files.append({'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': digest})
    return {'base_model_name_or_path': base, 'base_revision_declared': config.get('revision'),
            'base_revision_confirmed': False, 'peft_type': config['peft_type'],
            'rank_declared': config.get('r'), 'lora_alpha_declared': config.get('lora_alpha'),
            'target_modules_declared': config.get('target_modules'), 'tensor_count': len(tensors),
            'tensor_dtypes': sorted({x['dtype'] for x in tensors.values()}),
            'tokenizer_files_present': [x['path'] for x in files if Path(x['path']).name in
                {'tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','special_tokens_map.json'}],
            'files': files, 'inference_verified': False,
            'note': 'Integridad y metadatos; no acredita revisión histórica, carga ni inferencia.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        raise ValueError('Guardar el informe fuera de la carpeta auditada')
    report = auditar(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'files': len(report['files']), 'tensor_count': report['tensor_count'],
                      'base': report['base_model_name_or_path'], 'inference_verified': False}))


if __name__ == '__main__':
    main()
