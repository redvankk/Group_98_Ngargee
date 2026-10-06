"""Common interface shared by all retrievers.

Every retriever indexes the same chunk list and returns results in the same
shape, so the service, API and evaluation scripts never need to know which
retrieval method is running.

A result is the chunk dict plus:
    score     retriever-specific score (higher is better; scales differ)
    relevant  True if the score passes this retriever's relevance threshold
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Retriever(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.chunks: list[dict] = []

    @abstractmethod
    def build(self, chunks: list[dict], rebuild: bool = False) -> None:
        """Index the chunks (``rebuild`` forces any on-disk cache to refresh)."""

    @abstractmethod
    def score(self, query: str) -> tuple[np.ndarray, np.ndarray]:
        """Return (scores, relevant_mask) with one entry per chunk."""

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        if not self.chunks:
            raise RuntimeError(f"{self.name} retriever has not been built")
        scores, relevant = self.score(query)
        return top_per_club(self.chunks, scores, relevant, top_k)


def top_per_club(
    chunks: list[dict],
    scores: np.ndarray,
    relevant: np.ndarray,
    top_k: int,
) -> list[dict]:
    """Best-scoring chunks, keeping only the highest chunk from each club."""
    results: list[dict] = []
    seen: set[str] = set()
    for idx in np.argsort(-scores, kind="stable"):
        chunk = chunks[int(idx)]
        if chunk["club_id"] in seen:
            continue
        seen.add(chunk["club_id"])
        results.append({**chunk, "score": float(scores[idx]), "relevant": bool(relevant[idx])})
        if len(results) >= top_k:
            break
    return results
