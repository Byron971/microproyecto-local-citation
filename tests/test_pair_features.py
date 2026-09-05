import numpy as np
import pytest

from src.features.pair_features import FEATURE_NAMES, PairFeatureExtractor, word_count


PAPERS = {
    "nlp": {
        "title": "Neural machine translation",
        "abstract": "Attention models improve translation systems.",
    },
    "bio": {
        "title": "Protein folding",
        "abstract": "Amino acid sequences determine protein structures.",
    },
}

CONTEXTS = {
    "c1": {"masked_text": "Neural attention for translation TARGETCIT"},
    "c2": {"masked_text": "Protein structures from amino acids"},
}


def test_word_count_tolerates_empty_values():
    assert word_count("one two three") == 3
    assert word_count("") == 0
    assert word_count(None) == 0


def test_feature_names_match_matrix_columns():
    pairs = [{"context_id": "c1", "paper_id": "nlp", "label": 1}]
    extractor = PairFeatureExtractor(max_features=None, min_df=1)

    features = extractor.fit_transform(PAPERS, pairs, CONTEXTS)

    assert features.shape == (1, len(FEATURE_NAMES))


def test_related_pair_has_greater_title_and_abstract_similarity():
    pairs = [
        {"context_id": "c1", "paper_id": "nlp", "label": 1},
        {"context_id": "c1", "paper_id": "bio", "label": 0},
    ]
    extractor = PairFeatureExtractor(max_features=None, min_df=1)

    features = extractor.fit_transform(PAPERS, pairs, CONTEXTS)

    title_column = FEATURE_NAMES.index("similarity_title")
    abstract_column = FEATURE_NAMES.index("similarity_abstract")
    assert features[0, title_column] > features[1, title_column]
    assert features[0, abstract_column] > features[1, abstract_column]


def test_context_markers_do_not_count_as_words():
    pairs = [{"context_id": "c1", "paper_id": "nlp", "label": 1}]
    extractor = PairFeatureExtractor(max_features=None, min_df=1)

    features = extractor.fit_transform(PAPERS, pairs, CONTEXTS)

    context_length_column = FEATURE_NAMES.index("context_length")
    assert features[0, context_length_column] == 4


def test_transform_preserves_pair_order():
    pairs = [
        {"context_id": "c2", "paper_id": "bio", "label": 1},
        {"context_id": "c1", "paper_id": "nlp", "label": 1},
    ]
    extractor = PairFeatureExtractor(max_features=None, min_df=1).fit(PAPERS)

    features = extractor.transform(pairs, CONTEXTS)

    assert features.shape == (2, len(FEATURE_NAMES))
    assert not np.array_equal(features[0], features[1])


def test_transform_requires_fit():
    with pytest.raises(RuntimeError):
        PairFeatureExtractor().transform([], CONTEXTS)


def test_transform_rejects_unknown_ids():
    extractor = PairFeatureExtractor(max_features=None, min_df=1).fit(PAPERS)

    with pytest.raises(KeyError, match="Contextos no encontrados"):
        extractor.transform([{"context_id": "missing", "paper_id": "nlp"}], CONTEXTS)

    with pytest.raises(KeyError, match="Artículos no encontrados"):
        extractor.transform([{"context_id": "c1", "paper_id": "missing"}], CONTEXTS)
