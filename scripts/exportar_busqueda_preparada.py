"""Extrae embeddings existentes de los artículos preparados; no ejecuta ni entrena modelos."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def export(source: Path, destination: Path, catalog_path: Path):
    metadata_raw = (source / 'indice.json').read_bytes()
    metadata = json.loads(metadata_raw)
    for name, digest in metadata['files'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Índice de origen con hash incorrecto: ' + name)
    corpus_raw = Path('config/corpus_ms.json').read_bytes()
    corpus = json.loads(corpus_raw)['documentos']
    version = hashlib.sha256(corpus_raw).hexdigest()
    catalog = json.loads(catalog_path.read_text())
    release = json.loads(Path('config/ms_release.json').read_text())
    if metadata['revision_scibert'] != release['scibert_revision']:
        raise ValueError('El índice no corresponde al encoder existente')
    if catalog['version_contenido'] != version or {a['paper_id'] for a in catalog['articulos']} != set(corpus):
        raise ValueError('Catálogo y corpus distintos')
    papers = json.loads((source / 'papers.json').read_text())
    by_id = {p['paper_id']: index for index, p in enumerate(papers)}
    rows, indices = [], []
    for article in catalog['articulos']:
        pid = article['paper_id']
        paper = papers[by_id[pid]]
        doc = corpus[pid]
        if paper['titulo'] != ' '.join(doc['titulo'].split()) or paper['resumen'] != ' '.join(doc['abstract'].split()):
            raise ValueError('Metadatos de origen diferentes: ' + pid)
        rows.append(paper)
        indices.append(by_id[pid])
        article['resumen'] = paper['resumen']
    vectors = np.load(source / 'embeddings.npy', allow_pickle=False)[indices]
    if vectors.shape != (len(rows), 768) or vectors.dtype != np.float32 or not np.isfinite(vectors).all():
        raise ValueError('Embeddings de origen incompatibles')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'papers.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    np.save(destination / 'embeddings.npy', vectors, allow_pickle=False)
    manifest = {k: metadata[k] for k in ['perfil', 'revision_scibert', 'dimension']}
    manifest.update(total_articulos=len(rows), version_contenido=version,
                    source_index_sha256=hashlib.sha256(metadata_raw).hexdigest(),
                    files={name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                           for name in ['papers.json', 'embeddings.npy']})
    (destination / 'indice.json').write_text(json.dumps(manifest, indent=2) + '\n')
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'articulos': len(rows), 'bytes_embeddings': (destination / 'embeddings.npy').stat().st_size,
                      'version_contenido': version, 'embeddings_reutilizados_sin_cambios': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('artifacts/scientific_search'))
    parser.add_argument('--destination', type=Path, default=Path('config/prepared_article_search'))
    parser.add_argument('--catalog', type=Path, default=Path('frontend/src/articleCatalog.json'))
    args = parser.parse_args()
    export(args.source, args.destination, args.catalog)
