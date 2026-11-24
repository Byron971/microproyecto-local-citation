"""Offline resumable SciBERT title+abstract index; no labels or classifier logits."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from recuperacion_densa.codificador_torch import TorchSciBERTEncoder
from recuperacion_densa.revision import REVISION_SCIBERT

PROFILE = 'scibert-title-abstract-windows-mean-cosine-v1'


def build(source, output, batch_size, device='cpu'):
    raw = source.read_bytes()
    records = json.loads(raw)
    papers = [{'paper_id': pid, 'titulo': ' '.join(p.get('title', '').split()),
               'resumen': ' '.join(p.get('abstract', '').split())} for pid, p in sorted(records.items())]
    texts = ['\n'.join(filter(None, [p['titulo'], p['resumen']])) for p in papers]
    if not all(texts):
        raise ValueError('El catálogo contiene artículos sin título ni resumen')
    identity = {'perfil': PROFILE, 'revision_scibert': REVISION_SCIBERT,
                'sha256_papers_origen': hashlib.sha256(raw).hexdigest(),
                'total_articulos': len(papers), 'dimension': 768, 'batch_size': batch_size, 'device': device}
    output.mkdir(parents=True, exist_ok=True)
    state = output / 'preparacion.json'
    if state.exists() and json.loads(state.read_text()) != identity:
        raise ValueError('El directorio contiene un índice de otra configuración')
    state.write_text(json.dumps(identity, indent=2))
    encoder = None
    start = time.monotonic()
    for offset in range(0, len(texts), batch_size):
        path = output / f'batch-{offset:06}.npy'
        count = min(batch_size, len(texts) - offset)
        if path.is_file():
            vectors = np.load(path, allow_pickle=False)
            if (vectors.shape != (count, 768) or vectors.dtype != np.float32
                    or not np.isfinite(vectors).all()
                    or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)):
                raise ValueError('Lote existente inválido')
        else:
            if encoder is None:
                encoder = TorchSciBERTEncoder(REVISION_SCIBERT, device=device, batch_size=batch_size,
                    manifiesto=Path('proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json'))
            vectors = np.asarray(encoder.encode(texts[offset:offset + count]), dtype=np.float32)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if not np.isfinite(vectors).all() or np.any(norms <= 0):
                raise ValueError('Embeddings inválidos')
            vectors /= norms
            partial = path.with_suffix('.partial')
            with partial.open('wb') as stream:
                np.save(stream, vectors, allow_pickle=False)
            partial.replace(path)
        progress = {**identity, 'completados': offset + count, 'segundos': round(time.monotonic()-start, 1)}
        (output / 'progreso.json').write_text(json.dumps(progress, indent=2))
        print(f'{offset+count}/{len(texts)} artículos · {progress["segundos"]} s', flush=True)
    matrix = np.concatenate([np.load(p, allow_pickle=False) for p in sorted(output.glob('batch-*.npy'))])
    assert matrix.shape == (len(papers), 768)
    np.save(output / 'embeddings.npy', matrix, allow_pickle=False)
    (output / 'papers.json').write_text(json.dumps(papers, ensure_ascii=False))
    manifest = {**identity, 'files': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                   for name in ['papers.json', 'embeddings.npy']}}
    (output / 'indice.json').write_text(json.dumps(manifest, indent=2))
    print('ÍNDICE COMPLETO', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--papers', type=Path, default=Path('data/raw/papers.json'))
    parser.add_argument('--salida', type=Path, default=Path('artifacts/scientific_search'))
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--device', choices=['cpu', 'mps'], default='cpu')
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 64:
        parser.error('batch-size debe estar entre 1 y 64')
    build(args.papers, args.salida, args.batch_size, args.device)
