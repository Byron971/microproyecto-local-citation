"""Experimental article retrieval; separate from the notebook-10 M/S classifiers."""
import hashlib
import json
from pathlib import Path

import numpy as np

MODEL_ID = 'scibert-articulos-v1'
PROFILE = 'scibert-title-abstract-windows-mean-cosine-v1'


class ArticleSearch:
    def __init__(self, directory, encoder):
        directory = Path(directory)
        metadata = json.loads((directory / 'indice.json').read_text())
        if (metadata['perfil'] != PROFILE or metadata['revision_scibert'] != encoder.revision
                or metadata['dimension'] != 768):
            raise ValueError('Índice SciBERT de perfil o revisión incompatible')
        for name in ['papers.json', 'embeddings.npy']:
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != metadata['files'][name]:
                raise ValueError('El índice no coincide con su SHA256')
        self.papers = json.loads((directory / 'papers.json').read_text())
        self.vectors = np.load(directory / 'embeddings.npy', allow_pickle=False)
        self.ids = np.asarray([p['paper_id'] for p in self.papers])
        if (len(set(self.ids)) != len(self.ids) or len(self.ids) != metadata['total_articulos']
                or self.vectors.shape != (len(self.papers), metadata['dimension'])
                or self.vectors.dtype != np.float32 or not np.isfinite(self.vectors).all()
                or not np.allclose(np.linalg.norm(self.vectors, axis=1), 1, atol=1e-5)):
            raise ValueError('Identidad o embeddings del índice inválidos')
        self.encoder, self.metadata = encoder, metadata
        self.version = hashlib.sha256((directory / 'indice.json').read_bytes()).hexdigest()

    def recommend(self, context, top_k):
        query = ' '.join(context.replace('TARGETCIT', ' ').replace('OTHERCIT', ' ').split())
        if not query:
            raise ValueError('Escribe un contexto con texto además del marcador de cita')
        vector = np.asarray(self.encoder.encode([query])[0], dtype=np.float32)
        if vector.shape != (self.vectors.shape[1],) or not np.isfinite(vector).all() or np.linalg.norm(vector) <= 0:
            raise ValueError('Embedding de consulta inválido')
        vector /= np.linalg.norm(vector)
        scores = np.round(np.clip(self.vectors @ vector, -1, 1), 6)
        order = np.lexsort((self.ids, -scores))[:top_k]
        rows = [{**self.papers[int(i)], 'posicion': rank, 'similitud': float(scores[i])}
                for rank, i in enumerate(order, 1)]
        return {'consulta': context, 'modelo': MODEL_ID, 'total': len(rows),
                'recomendaciones': rows, 'revision_scibert': self.encoder.revision,
                'version_indice': self.version, 'total_catalogo': len(self.papers),
                'metodo': PROFILE,
                'aviso': 'Búsqueda semántica experimental por título y resumen; no evaluada como recomendador en el notebook 10. M/S clasifican la función de cita por separado.'}
