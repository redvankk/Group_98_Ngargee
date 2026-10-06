"""Central configuration for the RAG backend.

Every setting can be overridden with an environment variable, usually via
``backend/.env`` (copy ``.env.example`` to get started). The ``.env`` file is
loaded here, so every entry point (API, build script, evaluation) sees the
same settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

RETRIEVERS = ("dense", "bm25", "hybrid")


def _str(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _path(name: str, default: Path) -> Path:
    path = Path(os.getenv(name, str(default)))
    return path if path.is_absolute() else BASE_DIR / path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Knowledge base and index
    data_path: Path
    index_dir: Path

    # Retrieval
    retriever: str
    embedding_model: str
    dense_min_score: float
    bm25_min_score: float
    bm25_k1: float
    bm25_b: float
    rrf_k: int

    # Generation (Ollama)
    ollama_enabled: bool
    ollama_host: str
    ollama_model: str
    ollama_temperature: float
    ollama_num_ctx: int
    ollama_timeout: float
    ollama_keep_alive: str
    max_context_chars: int
    history_turns: int

    # API
    cors_origins: tuple[str, ...]
    allow_reindex: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        retriever = _str("RETRIEVER", "dense").lower()
        if retriever not in RETRIEVERS:
            raise ValueError(f"RETRIEVER must be one of {RETRIEVERS}, got {retriever!r}")

        origins = _str(
            "CORS_ORIGINS",
            "http://localhost:8443,http://127.0.0.1:8443,http://localhost:5173,http://127.0.0.1:5173",
        )

        return cls(
            data_path=_path("RAG_DATA_PATH", BASE_DIR / "data" / "clubs_master.csv"),
            index_dir=_path("RAG_INDEX_DIR", BASE_DIR / "index"),
            retriever=retriever,
            embedding_model=_str("EMBEDDING_MODEL", "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"),
            # MIN_SIMILARITY is the old name for DENSE_MIN_SCORE; still accepted.
            dense_min_score=_float("DENSE_MIN_SCORE", _float("MIN_SIMILARITY", 0.24)),
            bm25_min_score=_float("BM25_MIN_SCORE", 4.0),
            bm25_k1=_float("BM25_K1", 1.2),
            bm25_b=_float("BM25_B", 0.75),
            rrf_k=_int("RRF_K", 60),
            ollama_enabled=_bool("OLLAMA_ENABLED", True),
            ollama_host=_str("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=_str("OLLAMA_MODEL", "llama3.2:3b"),
            ollama_temperature=_float("OLLAMA_TEMPERATURE", 0.1),
            ollama_num_ctx=_int("OLLAMA_NUM_CTX", 4096),
            ollama_timeout=_float("OLLAMA_TIMEOUT", 90),
            ollama_keep_alive=_str("OLLAMA_KEEP_ALIVE", "10m"),
            max_context_chars=_int("MAX_CONTEXT_CHARS", 6000),
            history_turns=_int("HISTORY_TURNS", 6),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            allow_reindex=_bool("ALLOW_REINDEX", False),
            log_level=_str("LOG_LEVEL", "INFO").upper(),
        )


settings = Settings.from_env()
