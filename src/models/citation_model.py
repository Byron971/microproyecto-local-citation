"""Artefacto completo de inferencia: recuperación, características y ranking."""

from dataclasses import dataclass

from src.config import ModelConfig
from src.features.pair_features import PairFeatureExtractor
from src.models.linear_reranker import LinearReranker, rerank_candidate_records
from src.models.tfidf_baseline import TfidfBaseline


@dataclass
class CitationModel:
    """Agrupa componentes ajustados y la configuración que los produjo."""

    config: ModelConfig
    retriever: TfidfBaseline
    extractor: PairFeatureExtractor
    reranker: LinearReranker
    data_hashes: dict[str, str]
    training_run_id: str

    def candidates(self, contexts: dict, split: list[dict]) -> list[dict]:
        return retrieve_candidates(self.retriever, contexts, split, self.config.top_n)

    def rank(self, records: list[dict], contexts: dict) -> list[list[str]]:
        pairs = [
            {"context_id": row["context_id"], "paper_id": paper_id}
            for row in records
            for paper_id in row["candidate_ids"]
        ]
        scores = self.reranker.predict_scores(self.extractor.transform(pairs, contexts))
        return rerank_candidate_records(records, scores)


def retrieve_candidates(
    retriever: TfidfBaseline, contexts: dict, split: list[dict], top_n: int
) -> list[dict]:
    """Recupera con el modelo ajustado, excluyendo el artículo citante."""
    rankings = retriever.rank(
        [contexts[row["context_id"]]["masked_text"] for row in split],
        top_k=top_n + 1,
    )
    return [
        {
            "context_id": row["context_id"],
            "positive_ids": row["positive_ids"],
            "candidate_ids": [
                paper_id
                for paper_id in ranking
                if paper_id != contexts[row["context_id"]].get("citing_id")
            ][:top_n],
        }
        for row, ranking in zip(split, rankings, strict=True)
    ]
