"""Prepare a bounded, reproducible public ACL-OCL subset; never fetch in HTTP requests."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar, fragmentar_v2


def fragmentar_ms(paragraphs, version='v2'):
    chunks = (fragmentar_v2 if version == 'v2' else fragmentar)(paragraphs)
    # Same deduplication as notebook 10; preserve the smallest chunk ID in source order.
    best = {}
    for c in chunks:
        text = ' '.join(c['texto'].split())
        best[text] = min(best.get(text, c['chunk_id']), c['chunk_id'])
    fields = ['chunk_id', 'texto', 'seccion', 'paragraph_indices', 'palabras']
    return [{k: c[k] for k in fields} for c in chunks
            if best[' '.join(c['texto'].split())] == c['chunk_id']]


def preparar(papers, ids, cache, revision, version='v2'):
    documentos, excluidos = {}, {}
    for pid in ids:
        if not re.fullmatch(r"[A-Z][0-9]{2}-[0-9]{4}", pid) or pid not in papers:
            raise ValueError("ID fuera del catálogo: " + pid)
        url = f"https://huggingface.co/datasets/WINGNUS/ACL-OCL/resolve/{revision}/Base_JSON/prefix{pid[0]}/json/{pid[:3]}/{pid}.json"
        path = cache / f"{pid}.json"
        try:
            if not path.exists():
                with urllib.request.urlopen(url, timeout=45) as response:
                    raw = response.read(10_000_001)
                if len(raw) > 10_000_000:
                    raise ValueError("Documento demasiado grande")
                path.write_bytes(raw)
            raw = path.read_bytes()
            doc = json.loads(raw)
            if doc.get("paper_id") != pid:
                raise ValueError("Identidad OCL incorrecta")
            paragraphs = [
                {"numero": i, "texto": p["text"].strip(), "seccion": str(p.get("section") or "").strip()}
                for i, p in enumerate(doc.get("pdf_parse", {}).get("body_text", []))
                if isinstance(p.get("text"), str) and p["text"].strip()
            ]
            chunks = fragmentar_ms(paragraphs, version)
            meta = papers[pid]
            if not meta.get("title", "").strip() or not meta.get("abstract", "").strip():
                raise ValueError("Metadatos insuficientes")
            if not 3 <= len(chunks) <= 100:
                raise ValueError("Número de fragmentos fuera de 3–100")
            if len(meta['title']) > 600 or len(meta['abstract']) > 12000:
                raise ValueError("Metadatos exceden contrato M/S")
            if sum(len(c['texto']) for c in chunks) + len(meta['title']) + len(meta['abstract']) > 56000:
                raise ValueError("Texto excede presupuesto M/S, sin truncar")
            documentos[pid] = {"paper_id": pid, "titulo": meta['title'], "abstract": meta['abstract'],
                               "candidatos": chunks, "fuente": url,
                               "publicacion": f"https://aclanthology.org/{pid}/",
                               "sha256_ocl": hashlib.sha256(raw).hexdigest()}
        except (ValueError, KeyError, urllib.error.URLError, TimeoutError) as exc:
            excluidos[pid] = str(exc)
        print(pid, 'listo' if pid in documentos else excluidos[pid], flush=True)
    return {"version": 1, "revision_ocl": revision, "licencia": "CC-BY-NC-4.0",
            "documentos": documentos, "excluidos": excluidos, "ids_solicitados": ids,
            "fragmentacion": f"notebook 10: {version}, 300 palabras, sin truncar, deduplicación por texto normalizado"}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids', required=True, type=Path)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--fragmentacion', choices=['v1', 'v2'], default='v2')
    parser.add_argument('--salida', required=True, type=Path)
    parser.add_argument('--cache', type=Path, default=Path('artifacts/corpus_ms/cache'))
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.revision):
        parser.error('Use una revisión HF completa, no main')
    args.cache.mkdir(parents=True, exist_ok=True)
    papers = json.loads(Path('data/raw/papers.json').read_text())
    result = preparar(papers, json.loads(args.ids.read_text()), args.cache, args.revision, args.fragmentacion)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(result, ensure_ascii=False, indent=2))
