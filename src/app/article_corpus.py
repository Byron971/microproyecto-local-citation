"""Validated immutable article corpus. No network access during requests."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

from src.app.ms_router import ConsultaMS


class CorpusUnavailable(ValueError):
    pass


@lru_cache(maxsize=4)
def load_corpus(path: str):
    try:
        raw = Path(path).read_bytes()
        data = json.loads(raw)
        if data['version'] != 1 or not isinstance(data['documentos'], dict) or not data['documentos']:
            raise ValueError('Empty/unsupported corpus')
        for pid, doc in data['documentos'].items():
            if doc['paper_id'] != pid or doc['publicacion'] != f'https://aclanthology.org/{pid}/':
                raise ValueError('Article identity mismatch')
            if len(bytes.fromhex(doc['sha256_ocl'])) != 32:
                raise ValueError('Invalid source checksum')
            ConsultaMS(contexto='Earlier work TARGETCIT.', titulo=doc['titulo'],
                       abstract=doc['abstract'], candidatos=doc['candidatos'])
        return data, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CorpusUnavailable('El corpus de artículos no está disponible o no supera la validación.') from exc


def corpus():
    default = Path(__file__).resolve().parents[2] / 'config/corpus_ms.json'
    return load_corpus(os.environ.get('MS_CORPUS_PATH', str(default)))
