"""Corpus sintético para probar el paquete sin depender del dataset real."""

import pytest

from modelo_citas.config.core import config
from modelo_citas.models.citation_model import CitationArtifact
from modelo_citas.models.linear_reranker import LinearReranker
from modelo_citas.models.tfidf_baseline import TfidfBaseline
from modelo_citas.processing.data_manager import paper_metadata
from modelo_citas.processing.features import PairFeatureExtractor
from modelo_citas.processing.pairs import build_pairs

PAPERS = {
    "p1": {
        "title": "neural machine translation",
        "abstract": "neural language translation models",
    },
    "p2": {"title": "protein folding", "abstract": "protein biological folding structure"},
    "p3": {"title": "language models", "abstract": "language neural models attention"},
    "p4": {"title": "cell biology", "abstract": "cell protein biology structure"},
}

CONTEXTS = {
    "q1": {"masked_text": "neural translation TARGETCIT", "citing_id": "p3"},
    "q2": {"masked_text": "protein folding structure", "citing_id": "p4"},
}

SPLIT = [
    {"context_id": "q1", "positive_ids": ["p1"]},
    {"context_id": "q2", "positive_ids": ["p2"]},
]


@pytest.fixture
def artifact() -> CitationArtifact:
    """Artefacto entrenado en memoria, igual al que produce train_pipeline."""
    retriever = TfidfBaseline(max_features=100, min_df=1).fit(PAPERS)
    extractor = PairFeatureExtractor(max_features=100, min_df=1).fit(PAPERS)
    pairs = build_pairs(SPLIT, list(PAPERS), negatives_per_positive=1, random_state=42)
    reranker = LinearReranker(c=1.0, random_state=42).fit(
        extractor.transform(pairs, CONTEXTS), [pair["label"] for pair in pairs]
    )

    return CitationArtifact(
        retriever=retriever,
        extractor=extractor,
        reranker=reranker,
        papers=paper_metadata(PAPERS),
        settings=config.model_settings.model_dump(mode="json") | {"top_n": 4},
        metadata={"entrenado_en": "prueba"},
    )
