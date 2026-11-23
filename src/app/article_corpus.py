"""Validated immutable article corpus. No network access during requests."""
from functools import lru_cache
import hashlib
import json
import os
import sqlite3
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


@lru_cache(maxsize=4)
def load_indexed_corpus(manifest_path: str, database_path: str):
    from src.app.corpus_store import IndexedCorpus
    try:
        raw = Path(manifest_path).read_bytes()
        manifest = json.loads(raw)
        if manifest['corpus_schema'] != 2 or len(manifest['files']) != 1:
            raise ValueError('Inventario del corpus incompatible')
        docs = IndexedCorpus(database_path, manifest['files'][0]['sha256'], manifest['total_articulos'])
        return dict(version=2, documentos=docs, licencia=manifest['licencia'],
                    fragmentacion=manifest['fragmentacion'], revision_ocl=manifest['revision_ocl']), hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        raise CorpusUnavailable('El corpus indexado no está disponible o no supera la validación.') from None


def corpus_metadata(data):
    docs = data['documentos']
    return docs.metadata() if hasattr(docs, 'metadata') else docs.items()


def preparar_corpus_release(client=None, root=None):
    manifest_path = Path(__file__).resolve().parents[2] / 'config/corpus_release.json'
    if not manifest_path.exists() or os.environ.get('MS_CORPUS_PATH'):
        return
    import boto3
    from botocore.config import Config
    from scripts.iniciar_ciencia import preparar
    manifest = json.loads(manifest_path.read_text())
    client = client or boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                                   config=Config(connect_timeout=5, read_timeout=30, retries={'max_attempts': 2}))
    root = Path(root or os.environ.get('MS_CORPUS_ROOT', '/tmp/citas-corpus'))
    preparar(client, manifest, root)
    os.environ['MS_CORPUS_DB'] = str(root / manifest['files'][0]['path'])


def corpus():
    root = Path(__file__).resolve().parents[2]
    release = root / 'config/corpus_release.json'
    if release.exists() and not os.environ.get('MS_CORPUS_PATH'):
        return load_indexed_corpus(str(release), os.environ.get('MS_CORPUS_DB', str(root / 'artifacts/coverage_expansion/corpus.sqlite')))
    default = Path(__file__).resolve().parents[2] / 'config/corpus_ms.json'
    return load_corpus(os.environ.get('MS_CORPUS_PATH', str(default)))
