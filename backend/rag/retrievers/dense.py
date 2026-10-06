"""Dense (semantic) retrieval with Sentence Transformers + cosine similarity.

Embeddings are cached in ``index/``. The cache is keyed on the embedding model
and the exact chunk texts, so it rebuilds automatically when the data changes.
"""
from __future__ import annotations

import hashlib
import json
import logging

import numpy as np

from ..config import settings
from .base import Retriever

log = logging.getLogger(__name__)


def _fingerprint(model_name: str, texts: list[str]) -> str:
    digest = hashlib.sha256(model_name.encode())
    for text in texts:
        digest.update(b"\x00" + text.encode("utf-8"))
    return digest.hexdigest()


class DenseRetriever(Retriever):
    name = "dense"

    def __init__(self, model_name: str | None = None, min_score: float | None = None) -> None:
        super().__init__()
        self.model_name = model_name or settings.embedding_model
        self.min_score = settings.dense_min_score if min_score is None else min_score
        self._model = None
        self.embeddings: np.ndarray | None = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("Loading embedding model %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def build(self, chunks: list[dict], rebuild: bool = False) -> None:
        self.chunks = chunks
        texts = [c["text"] for c in chunks]
        fingerprint = _fingerprint(self.model_name, texts)

        emb_path = settings.index_dir / "embeddings.npy"
        manifest_path = settings.index_dir / "manifest.json"

        if not rebuild and emb_path.exists() and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("fingerprint") == fingerprint:
                self.embeddings = np.load(emb_path)
                log.info("Loaded cached embeddings for %d chunks", len(chunks))
                return
            log.info("Data or embedding model changed; re-embedding")

        self.embeddings = self.model.encode_document(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype("float32")

        settings.index_dir.mkdir(parents=True, exist_ok=True)
        np.save(emb_path, self.embeddings)
        manifest_path.write_text(
            json.dumps(
                {
                    "fingerprint": fingerprint,
                    "embedding_model": self.model_name,
                    "chunks": len(chunks),
                    "dimensions": int(self.embeddings.shape[1]),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("Embedded %d chunks", len(chunks))

    def score(self, query: str) -> tuple[np.ndarray, np.ndarray]:
        query_vec = self.model.encode_query(
            [query], normalize_embeddings=True, convert_to_numpy=True
        )[0].astype("float32")
        scores = self.embeddings @ query_vec  # normalised, so dot product == cosine
        return scores, scores >= self.min_score
