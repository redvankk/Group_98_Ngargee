"""Okapi BM25 lexical retrieval (pure Python + NumPy, no extra dependency).

Chunk texts look like ``"Label: value"`` lines. The labels ("Club", "Category",
"Instagram", ...) appear in almost every chunk, so they are stripped before
indexing; only the values are searchable. Scores are unbounded, so BM25 has
its own relevance threshold (``BM25_MIN_SCORE``), separate from the cosine
threshold used by dense retrieval. Tune it on unanswerable questions.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

from ..config import settings
from .base import Retriever

STOPWORDS = frozenset(
    """a about an and any are as at be been but by can could do does for from
    get has have how i if in into is it its just like me more my of on or our
    so some that the their them there these they this to up us was we what
    when where which who whom why will with would you your want wanna im am
    interested interest interesting looking find anything something any
    much very really stuff things thing lot lots kinda sorta pretty quite also
    enjoy fan big huge love loves loved""".split()
)

_LABEL = re.compile(r"^[A-Za-z /]+:\s*", re.MULTILINE)
_TOKEN = re.compile(r"[a-z0-9]+")
_URL_QUERY = re.compile(r"\?\S*")  # drop ?locale=..&hl=.. noise from links


def tokenize(text: str) -> list[str]:
    text = _URL_QUERY.sub(" ", text.lower())
    return [_stem(t) for t in _TOKEN.findall(text) if len(t) > 1 and t not in STOPWORDS]


def _stem(token: str) -> str:
    """Very light stemming so plurals match: games -> game, filipinos -> filipino."""
    if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def strip_labels(text: str) -> str:
    return _LABEL.sub("", text)


class BM25Retriever(Retriever):
    name = "bm25"

    def __init__(
        self,
        k1: float | None = None,
        b: float | None = None,
        min_score: float | None = None,
    ) -> None:
        super().__init__()
        self.k1 = settings.bm25_k1 if k1 is None else k1
        self.b = settings.bm25_b if b is None else b
        self.min_score = settings.bm25_min_score if min_score is None else min_score
        self._tf: list[Counter] = []
        self._lengths = np.zeros(0)
        self._idf: dict[str, float] = {}

    def build(self, chunks: list[dict], rebuild: bool = False) -> None:
        # BM25 indexes ~150 chunks in milliseconds, so there is nothing to cache.
        self.chunks = chunks
        docs = [tokenize(strip_labels(c["text"])) for c in chunks]
        self._tf = [Counter(d) for d in docs]
        self._lengths = np.array([len(d) for d in docs], dtype="float32")
        self._avg_len = float(self._lengths.mean()) if len(docs) else 0.0

        n = len(docs)
        df = Counter(term for tf in self._tf for term in tf)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: str) -> tuple[np.ndarray, np.ndarray]:
        scores = np.zeros(len(self.chunks), dtype="float32")
        norm = self.k1 * (1 - self.b + self.b * self._lengths / (self._avg_len or 1.0))
        for term in set(tokenize(query)):
            idf = self._idf.get(term)
            if idf is None:
                continue
            tf = np.array([d.get(term, 0) for d in self._tf], dtype="float32")
            scores += idf * tf * (self.k1 + 1) / (tf + norm)
        return scores, scores >= self.min_score
