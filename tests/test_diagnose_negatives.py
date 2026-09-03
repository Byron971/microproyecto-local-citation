import pytest

from src.evaluation.diagnose_negatives import (
    hard_negatives_from_ranking,
    random_negatives_by_context,
    separability_auc,
)
from src.models.tfidf_baseline import TfidfBaseline


# --------------------------------------------------------------------------
# hard_negatives_from_ranking
# --------------------------------------------------------------------------

RANKING = ["p1", "p2", "p3", "p4", "p5"]


def test_hard_negatives_descarta_los_positivos():
    resultado = hard_negatives_from_ranking(RANKING, {"p2", "p4"})

    assert resultado == ["p1", "p3", "p5"]


def test_hard_negatives_conserva_el_orden_del_ranking():
    # El orden importa: un negativo duro lo es por haber quedado ARRIBA en la
    # primera etapa, asi que reordenar la lista perderia esa informacion.
    resultado = hard_negatives_from_ranking(RANKING, {"p1"})

    assert resultado == ["p2", "p3", "p4", "p5"]


def test_hard_negatives_recorta_a_n_hard_tomando_los_mas_similares():
    resultado = hard_negatives_from_ranking(RANKING, {"p1"}, n_hard=2)

    # Debe quedarse con los dos primeros disponibles, no con dos cualesquiera.
    assert resultado == ["p2", "p3"]


def test_hard_negatives_sin_n_hard_devuelve_todos():
    resultado = hard_negatives_from_ranking(RANKING, set(), n_hard=None)

    assert resultado == RANKING


def test_hard_negatives_con_n_hard_mayor_que_los_disponibles():
    resultado = hard_negatives_from_ranking(RANKING, {"p1", "p2", "p3"}, n_hard=99)

    assert resultado == ["p4", "p5"]


def test_hard_negatives_cuando_todo_el_ranking_es_positivo():
    resultado = hard_negatives_from_ranking(RANKING, set(RANKING))

    assert resultado == []


def test_hard_negatives_ignora_positivos_ausentes_del_ranking():
    # Un positivo puede no haber sido recuperado por la primera etapa; eso no
    # debe alterar los negativos que si aparecen.
    resultado = hard_negatives_from_ranking(RANKING, {"p2", "no-recuperado"})

    assert resultado == ["p1", "p3", "p4", "p5"]


def test_hard_negatives_acepta_un_iterable_consumible():
    # positive_ids se declara como Iterable: si se recorriera mas de una vez,
    # un generador quedaria vacio en la segunda pasada y los positivos se
    # colarian como negativos.
    positivos = (pid for pid in ["p2", "p4"])

    resultado = hard_negatives_from_ranking(RANKING, positivos)

    assert resultado == ["p1", "p3", "p5"]


def test_hard_negatives_rechaza_n_hard_negativo():
    with pytest.raises(ValueError):
        hard_negatives_from_ranking(RANKING, set(), n_hard=-1)


# --------------------------------------------------------------------------
# separability_auc
# --------------------------------------------------------------------------


def test_auc_es_uno_cuando_los_positivos_puntuan_siempre_mas_alto():
    assert separability_auc([0.8, 0.9, 1.0], [0.1, 0.2, 0.3]) == pytest.approx(1.0)


def test_auc_es_cero_cuando_el_orden_esta_invertido():
    # No se toma valor absoluto a proposito: un AUC por debajo de 0,5 es un
    # hallazgo interpretable -el puntaje ordena al reves- y no un error.
    assert separability_auc([0.1, 0.2], [0.8, 0.9]) == pytest.approx(0.0)


def test_auc_es_un_medio_cuando_las_poblaciones_son_indistinguibles():
    assert separability_auc([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.5)


def test_auc_rechaza_una_poblacion_vacia():
    with pytest.raises(ValueError):
        separability_auc([0.5], [])

    with pytest.raises(ValueError):
        separability_auc([], [0.5])


# --------------------------------------------------------------------------
# random_negatives_by_context
# --------------------------------------------------------------------------

PARES = [
    {"context_id": "c1", "paper_id": "p1", "label": 1},
    {"context_id": "c1", "paper_id": "p7", "label": 0},
    {"context_id": "c1", "paper_id": "p9", "label": 0},
    {"context_id": "c2", "paper_id": "p2", "label": 1},
    {"context_id": "c2", "paper_id": "p8", "label": 0},
]


def test_random_negatives_agrupa_solo_los_de_etiqueta_cero():
    resultado = random_negatives_by_context(PARES)

    assert resultado == {"c1": ["p7", "p9"], "c2": ["p8"]}


def test_random_negatives_omite_los_contextos_sin_negativos():
    solo_positivos = [{"context_id": "c3", "paper_id": "p3", "label": 1}]

    assert random_negatives_by_context(solo_positivos) == {}


def test_random_negatives_con_lista_vacia():
    assert random_negatives_by_context([]) == {}


# --------------------------------------------------------------------------
# paper_matrix (propiedad publica agregada para este diagnostico)
# --------------------------------------------------------------------------

PAPERS = {
    "a": {"title": "Redes neuronales", "abstract": "atencion y traduccion"},
    "b": {"title": "Plegamiento de proteinas", "abstract": "secuencias de aminoacidos"},
}


def test_paper_matrix_tiene_una_fila_por_articulo():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(PAPERS)

    assert baseline.paper_matrix.shape[0] == len(baseline.paper_ids)


def test_paper_matrix_exige_fit_previo():
    with pytest.raises(RuntimeError):
        TfidfBaseline().paper_matrix
