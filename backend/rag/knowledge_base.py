"""Turns the club spreadsheet into the chunk list every retriever indexes."""
from __future__ import annotations

from pathlib import Path

from .chunking import club_to_chunks
from .config import settings
from .data_loader import load_clubs


def load_chunks(data_path: Path | None = None) -> list[dict]:
    clubs = load_clubs(data_path or settings.data_path)
    return [chunk for club in clubs for chunk in club_to_chunks(club)]
