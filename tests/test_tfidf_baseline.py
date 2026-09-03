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


# --------------------------------------------------------------------------
# Pruebas sobre un corpus grande, contra una implementacion de referencia.
#
# Las pruebas de arriba usan 3 articulos y miran solo la primera posicion: un
# error de indices entre lotes podria pasar desapercibido. Las de aqui abajo
# comparan el resultado de rank() contra el calculo ingenuo (todas las
# similitudes, ordenadas), sobre un corpus lo bastante grande como para que un
# desplazamiento de indices cambie el resultado.
# --------------------------------------------------------------------------

# Cada articulo tiene un termino propio ("tema-N") repetido, de modo que las
# similitudes con cada consulta son distintas entre si y el orden esperado no
# depende de desempates.
CORPUS_GRANDE = {
    f"paper-{i:02d}": {
        "title": f"Estudio sobre tema{i}",
        "abstract": " ".join([f"tema{i}"] * (i % 5 + 1) + [f"comun{i % 3}", "analisis"]),
    }
    for i in range(40)
}


def _similitudes(baseline, consulta):
    """Similitudes de una consulta contra todo el corpus, sin truncar."""
    vector = baseline.vectorizer.transform([clean_context_text(consulta)])
    return (vector @ baseline._paper_matrix.T).toarray()[0]


def test_rank_devuelve_exactamente_las_mejores_k_similitudes():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(CORPUS_GRANDE)
    consulta = "tema7 analisis comun1"
    top_k = 8

    ranking = baseline.rank([consulta], top_k=top_k)[0]

    sims = _similitudes(baseline, consulta)
    posicion = {pid: i for i, pid in enumerate(baseline.paper_ids)}

    obtenidas = [sims[posicion[pid]] for pid in ranking]
    esperadas = sorted(sims, reverse=True)[:top_k]

    # Comparar los VALORES de similitud (no los ids) hace la prueba inmune a
    # empates, pero sigue detectando cualquier error de seleccion o de indice.
    assert obtenidas == pytest.approx(esperadas)


def test_rank_devuelve_el_ranking_en_orden_descendente():
    # Este caso necesita un corpus grande a proposito. ``np.argpartition`` no
    # garantiza orden dentro del top-K, pero en arreglos pequenos suele
    # devolverlo ordenado de todos modos: con 40 articulos la prueba pasaria
    # aunque se eliminara el ordenamiento final, dando confianza falsa.
    # Verificado empiricamente: con 2.000 articulos y K=100 si queda
    # desordenado, y la prueba detecta la ausencia del ordenamiento.
    corpus = {
        f"p{i:04d}": {
            "title": f"Documento {i}",
            "abstract": " ".join(["objetivo"] * (i % 97 + 1) + [f"relleno{i}"] * 15),
        }
        for i in range(2000)
    }
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(corpus)
    consulta = "objetivo"

    ranking = baseline.rank([consulta], top_k=100)[0]

    sims = _similitudes(baseline, consulta)
    posicion = {pid: i for i, pid in enumerate(baseline.paper_ids)}
    obtenidas = [sims[posicion[pid]] for pid in ranking]

    assert obtenidas == sorted(obtenidas, reverse=True)


def test_rank_por_lotes_da_el_mismo_resultado_que_sin_lotes():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(CORPUS_GRANDE)

    consultas = [f"tema{i} analisis" for i in range(13)]

    # Un solo lote que abarca todo, contra lotes pequenos que no dividen
    # exactamente el numero de consultas (13 = 5 + 5 + 3): asi el ultimo lote
    # queda incompleto, que es donde suelen romperse los indices.
    sin_lotes = baseline.rank(consultas, top_k=6, batch_size=len(consultas))
    con_lotes = baseline.rank(consultas, top_k=6, batch_size=5)

    assert con_lotes == sin_lotes


def test_rank_asigna_cada_ranking_a_su_propia_consulta():
    baseline = TfidfBaseline(max_features=None, min_df=1).fit(CORPUS_GRANDE)

    # Cada consulta nombra un tema distinto, asi que su articulo homonimo debe
    # quedar primero. Si los lotes mezclaran los resultados entre consultas,
    # esta correspondencia se romperia.
    indices = [2, 9, 17, 23, 31, 38]
    consultas = [f"tema{i}" for i in indices]

    rankings = baseline.rank(consultas, top_k=1, batch_size=4)

    assert [r[0] for r in rankings] == [f"paper-{i:02d}" for i in indices]


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
