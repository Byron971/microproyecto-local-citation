"""Artefacto de inferencia: recuperación, características, reordenamiento y metadatos."""

from dataclasses import dataclass, field
from typing import Any

from modelo_citas.models.linear_reranker import LinearReranker, rerank_candidate_records
from modelo_citas.models.tfidf_baseline import TfidfBaseline, clean_context_text
from modelo_citas.processing.features import PairFeatureExtractor

# Identificador sintético del contexto que llega por API: el extractor trabaja
# con pares (context_id, paper_id) y una sola consulta no tiene ID propio.
QUERY_ID = "__query__"


@dataclass
class CitationArtifact:
    """Todo lo necesario para recomendar sin volver a leer el dataset."""

    retriever: TfidfBaseline
    extractor: PairFeatureExtractor
    reranker: LinearReranker
    papers: dict[str, dict[str, str]]
    settings: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def top_n(self) -> int:
        """Cantidad de candidatos que recupera la primera etapa."""
        return int(self.settings["top_n"])

    def recommend(self, context: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Recupera candidatos con TF-IDF y los reordena con el modelo lineal."""
        if top_k <= 0:
            raise ValueError("top_k debe ser un entero positivo.")

        cleaned = clean_context_text(context)

        # Un contexto vacío da un vector nulo y un orden arbitrario entre
        # artículos con similitud cero: es preferible no devolver nada.
        if not cleaned:
            return []

        candidates = self.retriever.rank_with_scores(cleaned, top_k=self.top_n)

        if not candidates:
            return []

        tfidf_scores = dict(candidates)
        candidate_ids = [paper_id for paper_id, _score in candidates]
        record = {"context_id": QUERY_ID, "candidate_ids": candidate_ids}
        pairs = [
            {"context_id": QUERY_ID, "paper_id": paper_id}
            for paper_id in candidate_ids
        ]
        features = self.extractor.transform(pairs, {QUERY_ID: {"masked_text": cleaned}})
        scores = self.reranker.predict_scores(features)
        reranked = rerank_candidate_records([record], scores)[0]
        by_paper = dict(zip(candidate_ids, scores, strict=True))

        return [
            self._build_recommendation(
                paper_id, position, float(by_paper[paper_id]), tfidf_scores[paper_id]
            )
            for position, paper_id in enumerate(reranked[:top_k], start=1)
        ]

    def describe(self) -> dict[str, Any]:
        """Ficha técnica del modelo que se está sirviendo."""
        vectorizer = self.retriever.vectorizer

        return {
            "modelo": "TF-IDF + reordenador lineal",
            "articulos": len(self.retriever.paper_ids),
            "vocabulario": len(vectorizer.vocabulary_) if vectorizer else 0,
            "top_n": self.top_n,
            "k": int(self.settings["k"]),
            "max_features": self.settings["max_features"],
            "min_df": self.settings["min_df"],
            **self.metadata,
        }

    def _build_recommendation(
        self,
        paper_id: str,
        position: int,
        score: float,
        tfidf_score: float,
    ) -> dict[str, Any]:
        """Arma el registro de una recomendación con los metadatos del artículo."""
        paper = self.papers.get(paper_id, {})

        return {
            "posicion": position,
            "paper_id": paper_id,
            "titulo": paper.get("title", ""),
            "resumen": paper.get("abstract", ""),
            "similitud": round(score, 4),
            "similitud_tfidf": round(tfidf_score, 4),
        }
