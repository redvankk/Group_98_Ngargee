from .base import Retriever
from .bm25 import BM25Retriever
from .dense import DenseRetriever
from .hybrid import HybridRetriever


def create_retriever(name: str) -> Retriever:
    if name == "dense":
        return DenseRetriever()
    if name == "bm25":
        return BM25Retriever()
    if name == "hybrid":
        return HybridRetriever()
    raise ValueError(f"Unknown retriever {name!r}; use dense, bm25 or hybrid")


__all__ = ["Retriever", "DenseRetriever", "BM25Retriever", "HybridRetriever", "create_retriever"]
