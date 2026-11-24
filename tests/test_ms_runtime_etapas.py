"""Dividir la inferencia M/S en etapas no cambia el resultado."""
import pytest

torch = pytest.importorskip('torch')


class Tokenizador:
    cls_token_id, sep_token_id = 1, 2

    def __call__(self, texto, add_special_tokens=False):
        return {'input_ids': [3 + (sum(map(ord, w)) % 90) for w in texto.split()]}


class Recuperador:
    method = 'scibert_base_mean_pooling_cosine'

    def top3(self, contexto, candidatos):
        return [{**c, 'similitud_coseno': 1 - i / 10} for i, c in enumerate(candidatos[:3])]


class Clasificador(torch.nn.Module):
    def __init__(self, semilla):
        super().__init__()
        torch.manual_seed(semilla)
        self.embedding = torch.nn.Embedding(100, 9)

    def forward(self, input_ids, attention_mask):
        return self.embedding(input_ids).mean(dim=1)


def servicio():
    from src.app.ms_runtime import CLASES, ServicioMS
    s = ServicioMS.__new__(ServicioMS)
    s.device = torch.device('cpu')
    s.recuperador = Recuperador()
    s.tokenizador = Tokenizador()
    s.modelos = {'M': Clasificador(1).eval(), 'S': Clasificador(2).eval()}
    s.manifiestos = {'M': {}, 'S': {'sesgos_ph': [0.1 * i for i in range(len(CLASES))]}}
    return s


def test_etapas_equivalentes_y_tres_envolturas():
    s = servicio()
    candidatos = [{'chunk_id': f'c{i}', 'texto': f'fragmento numero {i} sobre metodos',
                   'seccion': 'Method'} for i in range(5)]
    args = ('Earlier work TARGETCIT proposed methods.', 'Titulo', 'Resumen breve', candidatos)
    base = s.analizar(*args)
    etapas = []

    def envolver(funcion):
        etapas.append(1)
        return funcion()

    assert s.analizar(*args, por_etapa=envolver) == base
    assert len(etapas) == 3  # recuperación, M y S
    assert set(base['clasificadores']) == {'M', 'S'} and len(base['top3']) == 3


def test_error_de_recuperacion_se_propaga_desde_la_etapa():
    s = servicio()
    s.recuperador.top3 = lambda contexto, candidatos: []
    with pytest.raises(ValueError):
        s.analizar('A TARGETCIT b', 't', 'a', [], por_etapa=lambda f: f())
