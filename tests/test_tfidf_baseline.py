import pytest

from src.models.tfidf_baseline import (
    TfidfBaseline,
    build_paper_text,
    clean_context_text,
)


PAPERS = {
    "paper-nlp": {
        "title": "Neural machine translation",
        "abstract": "A study about translation using neural networks and attention.",
    },
    "paper-bio": {
        "title": "Protein folding prediction",
        "abstract": "Predicting protein structures from amino acid sequences.",
    },
    "paper-vision": {
        "title": "Image classification with convolutions",
        "abstract": "Convolutional networks applied to image recognition tasks.",
    },
}


def test_build_paper_text_joins_title_and_abstract():
    result = build_paper_text(PAPERS["paper-nlp"])

    assert "Neural machine translation" in result
    assert "attention" in result


def test_build_paper_text_tolerates_missing_fields():
    assert build_paper_text({"title": "Solo titulo"}) == "Solo titulo"
    assert build_paper_text({}) == ""


def test_clean_context_text_removes_citation_markers():
    text = "Following TARGETCIT and also OTHERCIT we propose a method."

    result = clean_context_text(text)

    assert "TARGETCIT" not in result
    assert "OTHERCIT" not in result
    assert "we propose a method" in result


def test_rank_puts_the_topically_closest_paper_first():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(PAPERS)

    rankings = baseline.rank(
        ["We use neural networks with attention for translation TARGETCIT"],
        top_k=3,
    )

    assert rankings[0][0] == "paper-nlp"


def test_rank_returns_requested_number_of_results():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(PAPERS)

    rankings = baseline.rank(["protein sequences"], top_k=2)

    assert len(rankings[0]) == 2


def test_rank_caps_top_k_at_corpus_size():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(PAPERS)

    # Se piden más artículos de los que existen: debe devolver todos, sin
    # fallar por índices fuera de rango.
    rankings = baseline.rank(["neural networks"], top_k=50)

    assert len(rankings[0]) == len(PAPERS)


def test_rank_processes_all_queries_across_batches():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(PAPERS)

    queries = ["neural translation", "protein folding", "image recognition"]

    # batch_size menor que el número de consultas fuerza varios lotes: es el
    # camino que se usa con el conjunto real de validación.
    rankings = baseline.rank(queries, top_k=1, batch_size=2)

    assert len(rankings) == 3
    assert rankings[0][0] == "paper-nlp"
    assert rankings[1][0] == "paper-bio"
    assert rankings[2][0] == "paper-vision"


def test_rank_requires_fit_first():
    baseline = TfidfBaseline()

    with pytest.raises(RuntimeError):
        baseline.rank(["cualquier texto"], top_k=1)


def test_fit_rejects_empty_corpus():
    with pytest.raises(ValueError):
        TfidfBaseline().fit({})


def test_rank_rejects_non_positive_top_k():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(PAPERS)

    with pytest.raises(ValueError):
        baseline.rank(["texto"], top_k=0)
