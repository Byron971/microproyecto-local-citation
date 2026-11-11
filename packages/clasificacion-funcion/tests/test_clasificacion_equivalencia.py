"""Las metricas propias coinciden con `paired_benchmark.model_metrics` (scikit-learn)."""
import random

import pytest

from clasificacion_funcion import dominio as d

paired = pytest.importorskip("src.evaluation.commercial.paired_benchmark")


def test_categorias_identicas_y_en_el_mismo_orden():
    assert d.CATEGORIAS == paired.CATEGORIES


@pytest.mark.parametrize("semilla", [0, 1, 2])
def test_metricas_equivalen_a_model_metrics(semilla):
    rng = random.Random(semilla)
    # Sesgado y con clases sin soporte/sin predicciones para ejercitar zero_division.
    verdad = [rng.choice([0, 0, 0, 1, 2, 3, 6]) for _ in range(120)]
    predicho = [v if rng.random() < 0.6 else rng.choice([0, 1, 4, 5]) for v in verdad]
    propio, ref = d.metricas(verdad, predicho), paired.model_metrics(verdad, predicho)
    assert propio.keys() == ref.keys()
    for k, v in ref.items():
        if isinstance(v, float):
            assert propio[k] == pytest.approx(v, abs=1e-12), k
    assert propio["n"] == ref["n"]
    assert propio["confusion_matrix"] == ref["confusion_matrix"]
    for a, b in zip(propio["per_class"], ref["per_class"]):
        assert a["label"] == b["label"] and a["support"] == b["support"]
        for k in ("precision", "recall", "f1"):
            assert a[k] == pytest.approx(b[k], abs=1e-12)
