"""Hybrid retrieval: dense + BM25 combined with Reciprocal Rank Fusion (RRF).

RRF only uses each method's *rank*, so it avoids comparing cosine scores with
unbounded BM25 scores. A chunk counts as relevant if either method judges it
relevant by its own threshold.
"""
from __future__ import annotations

import numpy as np

from ..config import settings
from .base import Retriever
from .bm25 import BM25Retriever
from .dense import DenseRetriever


def _ranks(scores: np.ndarray) -> np.ndarray:
    ranks = np.empty(len(scores), dtype="float32")
    ranks[np.argsort(-scores, kind="stable")] = np.arange(1, len(scores) + 1)
    return ranks


class HybridRetriever(Retriever):
    name = "hybrid"

    def __init__(
        self,
        dense: DenseRetriever | None = None,
        bm25: BM25Retriever | None = None,
        rrf_k: int | None = None,
    ) -> None:
        super().__init__()
        self.dense = dense or DenseRetriever()
        self.bm25 = bm25 or BM25Retriever()
        self.rrf_k = settings.rrf_k if rrf_k is None else rrf_k

    def build(self, chunks: list[dict], rebuild: bool = False) -> None:
        self.chunks = chunks
        self.dense.build(chunks, rebuild=rebuild)
        self.bm25.build(chunks, rebuild=rebuild)

    def score(self, query: str) -> tuple[np.ndarray, np.ndarray]:
        dense_scores, dense_rel = self.dense.score(query)
        bm25_scores, bm25_rel = self.bm25.score(query)
        fused = 1.0 / (self.rrf_k + _ranks(dense_scores))
        # Only chunks sharing at least one term with the query get BM25 credit.
        fused += np.where(bm25_scores > 0, 1.0 / (self.rrf_k + _ranks(bm25_scores)), 0.0)
        return fused, dense_rel | bm25_rel
