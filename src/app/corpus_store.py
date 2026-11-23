"""Read-only indexed corpus. Reads only the selected article into Python memory."""
from collections.abc import Mapping
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

from src.app.ms_router import ConsultaMS


class IndexedCorpus(Mapping):
    def __init__(self, path, expected_sha256, count):
        self.path = Path(path).resolve()
        digest = hashlib.sha256()
        with self.path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('El corpus no coincide con el SHA256 fijado')
        self.count = count
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise ValueError('Versión SQLite del corpus incompatible')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Índice del corpus corrupto')
            if db.execute('SELECT count(*) FROM documentos').fetchone()[0] != count:
                raise ValueError('Cantidad de artículos del corpus incorrecta')
            invalid = db.execute('SELECT count(*) FROM documentos WHERE total_fragmentos < 3 OR total_fragmentos > 100 OR length(titulo) < 1 OR length(abstract) < 1 OR length(sha256_json) != 64').fetchone()[0]
            if invalid:
                raise ValueError('Metadatos del corpus inválidos')

    def connect(self):
        # immutable disables journals/locks; the deployment never mutates this file.
        return closing(sqlite3.connect(self.path.as_uri() + '?mode=ro&immutable=1', uri=True))

    def __len__(self):
        return self.count

    def __iter__(self):
        with self.connect() as db:
            yield from (r[0] for r in db.execute('SELECT paper_id FROM documentos ORDER BY paper_id'))

    def __contains__(self, key):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM documentos WHERE paper_id=?', (key,)).fetchone() is not None

    def __getitem__(self, key):
        from src.app.article_corpus import CorpusUnavailable
        try:
            with self.connect() as db:
                row = db.execute('SELECT documento, sha256_json, total_fragmentos, titulo, abstract FROM documentos WHERE paper_id=?', (key,)).fetchone()
            if row is None:
                raise KeyError(key)
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(row[0])) as source:
                raw = source.read(2_000_001)
            if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != row[1]:
                raise ValueError('Artículo del corpus corrupto')
            doc = json.loads(raw)
            if doc['paper_id'] != key or doc['publicacion'] != f'https://aclanthology.org/{key}/':
                raise ValueError('Identidad de artículo distinta')
            if len(bytes.fromhex(doc['sha256_ocl'])) != 32 or len(doc['candidatos']) != row[2]:
                raise ValueError('Procedencia o cantidad de fragmentos inválida')
            if doc['titulo'] != row[3] or doc['abstract'] != row[4]:
                cut = doc.get('truncamiento', {})
                if not cut.get('aplicado') or cut.get('sha256_titulo_original') != hashlib.sha256(row[3].encode()).hexdigest() or cut.get('sha256_resumen_original') != hashlib.sha256(row[4].encode()).hexdigest():
                    raise ValueError('Metadatos de artículo distintos')
            ConsultaMS(contexto='Earlier work TARGETCIT.', titulo=doc['titulo'], abstract=doc['abstract'], candidatos=doc['candidatos'])
            return doc
        except KeyError:
            if row is None:
                raise
            raise CorpusUnavailable('El artículo preparado no supera la validación.') from None
        except (ValueError, TypeError, OSError, sqlite3.Error, EOFError):
            raise CorpusUnavailable('El artículo preparado no supera la validación.') from None

    def metadata(self):
        with self.connect() as db:
            for pid, title, abstract, count in db.execute('SELECT paper_id, titulo, abstract, total_fragmentos FROM documentos ORDER BY paper_id'):
                yield pid, dict(titulo=title, abstract=abstract, total_fragmentos=count)
