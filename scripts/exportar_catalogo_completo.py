"""Exporta títulos e IDs del índice existente; no genera embeddings."""
import hashlib
import json
from pathlib import Path


def export(source=Path('artifacts/scientific_search'), destination=Path('frontend/src/fullArticleCatalog.json')):
    raw = (source / 'papers.json').read_bytes()
    metadata = json.loads((source / 'indice.json').read_text())
    if hashlib.sha256(raw).hexdigest() != metadata['files']['papers.json']:
        raise ValueError('El catálogo no coincide con el índice')
    papers = json.loads(raw)
    prepared = json.loads(Path('frontend/src/articleCatalog.json').read_text())
    from src.app.article_corpus import corpus
    data, version = corpus()
    ready = set(data['documentos'])
    by_id = {p['paper_id']: p for p in prepared['articulos']}
    if not set(by_id).issubset(ready):
        raise ValueError('El corpus ampliado no conserva los artículos iniciales')
    if len(papers) != metadata['total_articulos'] or len({p['paper_id'] for p in papers}) != len(papers):
        raise ValueError('Catálogo incompleto o duplicado')
    if not set(by_id).issubset({p['paper_id'] for p in papers}):
        raise ValueError('Faltan artículos preparados')
    # Prepared first preserves the useful initial page; every other article is searchable.
    rows = [dict(p, preparado=True) for p in by_id.values()] + [dict(preparado=p['paper_id'] in ready, paper_id=p['paper_id'], titulo=p['titulo'], resumen='',
             publicacion=f"https://aclanthology.org/{p['paper_id']}/") for p in papers if p['paper_id'] not in by_id]
    destination.write_text(json.dumps(dict(source_sha256=hashlib.sha256(raw).hexdigest(), version_contenido=version, articulos=rows), ensure_ascii=False, separators=(',', ':')) + '\n')
    prepared['version_contenido'] = version
    prepared['total_preparados'] = len(ready)
    Path('frontend/src/articleCatalog.json').write_text(json.dumps(prepared, ensure_ascii=False, indent=2)+'\n')
    print(len(rows), 'artículos exportados;',len(ready),'con texto preparado; sin recalcular embeddings')


if __name__ == '__main__':
    export()
