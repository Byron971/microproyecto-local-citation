import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.app.ms_router import router
from src.app.article_corpus import load_corpus


class ArticleCorpusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'corpus.json'
        self.doc = {'paper_id': 'P14-2008', 'titulo': 'Invented title', 'abstract': 'Invented abstract',
                    'publicacion': 'https://aclanthology.org/P14-2008/',
                    'fuente': 'https://example.org/public-article', 'sha256_ocl': 'a' * 64,
                    'candidatos': [{'chunk_id': str(i), 'texto': f'Invented paragraph {i}.'} for i in range(3)]}
        self.data = {'version': 1, 'documentos': {'P14-2008': self.doc}, 'licencia': 'CC-BY-NC-4.0', 'fragmentacion': 'V1'}
        self.write()
        self.env = patch.dict(os.environ, {'MS_CORPUS_PATH': str(self.path)})
        self.env.start()
        app = FastAPI(); app.include_router(router)
        self.client = TestClient(app)

    def write(self):
        self.path.write_text(json.dumps(self.data))
        load_corpus.cache_clear()

    def tearDown(self):
        self.env.stop(); self.directory.cleanup(); load_corpus.cache_clear()

    def test_article_resolved_server_side_and_provenance_returned(self):
        with patch('src.app.ms_router.analisis_cita_ms', return_value={'top3': []}) as infer:
            response = self.client.post('/api/analisis-cita-ms/articulo', json={'paper_id': 'P14-2008', 'contexto': 'Previous work TARGETCIT.'})
        self.assertEqual(response.status_code, 200)
        entrada = infer.call_args.args[0]
        self.assertEqual(entrada.titulo, self.doc['titulo'])
        self.assertEqual([c.texto for c in entrada.candidatos], [c['texto'] for c in self.doc['candidatos']])
        self.assertEqual(response.json()['articulo']['paper_id'], 'P14-2008')
        self.assertEqual(len(response.json()['articulo']['version_contenido']), 64)

    def test_absent_article_and_missing_marker_never_infer(self):
        with patch('src.app.ms_router.analisis_cita_ms') as infer:
            for pid, ctx, status in [('P14-9999', 'X TARGETCIT', 404), ('P14-2008', 'No marker', 422)]:
                response = self.client.post('/api/analisis-cita-ms/articulo', json={'paper_id': pid, 'contexto': ctx})
                self.assertEqual(response.status_code, status)
            infer.assert_not_called()

    def test_corruption_fails_closed(self):
        for mutate in [lambda d: d.update(paper_id='P14-9999'), lambda d: d.update(candidatos=d['candidatos'][:2]),
                       lambda d: d.update(abstract=''), lambda d: d['candidatos'][1].update(chunk_id='0')]:
            self.data['documentos']['P14-2008'] = copy.deepcopy(self.doc)
            mutate(self.data['documentos']['P14-2008']); self.write()
            response = self.client.post('/api/analisis-cita-ms/disponibilidad', json={'paper_ids': ['P14-2008']})
            self.assertEqual(response.status_code, 503)

    def test_partial_coverage_explicit(self):
        response = self.client.post('/api/analisis-cita-ms/disponibilidad', json={'paper_ids': ['P14-2008', 'P14-9999']})
        self.assertEqual([a['disponible'] for a in response.json()['articulos']], [True, False])


if __name__ == '__main__':
    unittest.main()


def test_sin_credenciales_aws_usa_el_corpus_incluido(monkeypatch):
    """CI y desarrollo local no tienen credenciales: arrancar con el corpus del repo."""
    import boto3
    from src.app import article_corpus
    monkeypatch.delenv('MS_CORPUS_PATH', raising=False)
    monkeypatch.setattr(boto3.Session, 'get_credentials', lambda self: None)
    article_corpus.preparar_corpus_release()
    import os
    assert os.environ['MS_CORPUS_PATH'].endswith('config/corpus_ms.json')
    data, version = article_corpus.corpus()
    assert data['documentos'] and len(version) == 64


def test_con_cliente_explicito_no_hay_alternativa(monkeypatch, tmp_path):
    """El servicio científico pasa su cliente S3: sin descarga válida debe fallar."""
    import boto3
    from src.app import article_corpus
    monkeypatch.delenv('MS_CORPUS_PATH', raising=False)
    monkeypatch.setattr(boto3.Session, 'get_credentials', lambda self: None)

    class Roto:
        def get_object(self, **kwargs):
            raise OSError('sin acceso')

    import pytest
    with pytest.raises(OSError):
        article_corpus.preparar_corpus_release(client=Roto(), root=tmp_path)
    import os
    assert 'MS_CORPUS_PATH' not in os.environ
