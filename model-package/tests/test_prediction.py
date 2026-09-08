import pytest

from modelo_citas import __version__
from modelo_citas.predict import make_prediction
from modelo_citas.processing.data_manager import artifact_file_name, paper_metadata


def test_recommend_orders_and_completes_metadata(artifact):
    recomendaciones = artifact.recommend("neural machine translation", top_k=2)

    assert len(recomendaciones) == 2
    assert [r["posicion"] for r in recomendaciones] == [1, 2]
    assert recomendaciones[0]["titulo"]
    assert 0.0 <= recomendaciones[0]["similitud"] <= 1.0
    puntajes = [r["similitud"] for r in recomendaciones]
    assert puntajes == sorted(puntajes, reverse=True)


def test_recommend_returns_nothing_for_empty_context(artifact):
    assert artifact.recommend("TARGETCIT   ", top_k=5) == []


def test_recommend_rejects_non_positive_top_k(artifact):
    with pytest.raises(ValueError, match="top_k"):
        artifact.recommend("neural translation", top_k=0)


def test_describe_reports_corpus_and_settings(artifact):
    ficha = artifact.describe()

    assert ficha["modelo"] == "TF-IDF + reordenador lineal"
    assert ficha["articulos"] == 4
    assert ficha["vocabulario"] > 0


def test_make_prediction_reports_errors_instead_of_raising():
    resultado = make_prediction(context="", top_k=5)

    assert resultado["predictions"] is None
    assert resultado["errors"] is not None
    assert resultado["version"] == __version__


def test_paper_metadata_truncates_long_abstracts():
    largo = {"p": {"title": "t", "abstract": "x" * 900}}

    resumen = paper_metadata(largo, preview_chars=600)["p"]["abstract"]

    assert len(resumen) == 601 and resumen.endswith("…")


def test_artifact_file_name_follows_package_version():
    assert artifact_file_name() == f"modelo-citas-output{__version__}.pkl"
