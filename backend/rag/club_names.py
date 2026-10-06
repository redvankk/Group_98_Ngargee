"""Recognise clubs named in a question, including acronyms like CSIT or REECE.

Retrieval alone can't connect "CSIT" to "Computer Science and Information
Technology Society": the acronym appears nowhere in that club's text. So we
build an alias list from the data itself (full names, bracketed acronyms,
initials, and the first part of the club email, e.g. csit.society@ -> csit).
Aliases shared by more than one club are dropped to avoid wrong matches.

Extra aliases can be added in data/club_aliases.csv (columns: club, alias).
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from .config import BASE_DIR

ALIAS_FILE = BASE_DIR / "data" / "club_aliases.csv"

SKIP_WORDS = {"and", "of", "the", "for", "in", "at", "&", "a"}
GENERIC = {
    "club", "clubs", "society", "association", "students", "student", "network",
    "collective", "union", "rmit", "info", "contact", "admin", "hello", "president",
    "secretary", "team", "group", "the", "university",
}
_PAREN = re.compile(r"\(([^()]{2,60})\)")
_EMAIL = re.compile(r"([a-z0-9._-]+)@", re.I)


def _initials(words: list[str]) -> str:
    return "".join(w[0] for w in words if w.lower() not in SKIP_WORDS and w[0].isalnum()).lower()


def _club_aliases(name: str, text: str) -> tuple[set[str], set[str]]:
    """Returns (aliases, initials). Initials like "free" or "ups" can be real
    words, so they only match when the question writes them in capitals."""
    aliases: set[str] = set()
    initials_found: set[str] = set()
    base = _PAREN.sub("", name).strip()
    aliases.update({name.lower(), base.lower()})
    if base.lower().startswith("rmit "):
        aliases.add(base[5:].lower())

    # Bracketed names/acronyms in the club name or description, e.g. "(RISC)"
    for inner in _PAREN.findall(name) + _PAREN.findall(text):
        inner = inner.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9+&]{2,9}", inner) or len(inner.split()) >= 3 and inner.lower() in text.lower()[:400]:
            aliases.add(inner.lower())

    # Names the team recorded, e.g. "Also known as: RISC; Information Security Collective"
    for line in re.findall(r"^Also known as: (.*)$", text, flags=re.M):
        for alias in line.split(";"):
            if len(alias.strip()) >= 3:
                aliases.add(alias.strip().lower())

    # Initials, with and without a leading "RMIT" and a trailing generic word
    words = re.findall(r"[A-Za-z0-9+]+|&", base)
    variants = [words]
    if words and words[0].lower() == "rmit":
        variants.append(words[1:])
    for v in list(variants):
        if v and v[-1].lower() in GENERIC:
            variants.append(v[:-1])
    for v in variants:
        initials = _initials(v)
        if len(initials) >= 3:
            initials_found.add(initials)

    # First part of the club email: csit.society@ -> csit, reece.club@ -> reece.
    # Only kept if it is a word from the name or matches the club's initials,
    # so an address like "drawn@" can't hijack ordinary questions.
    name_words = set(re.findall(r"[a-z0-9]+", base.lower()))
    for local in _EMAIL.findall(text):
        first = re.split(r"[._-]", local.lower())[0]
        if len(first) >= 3 and first not in GENERIC and (
            first in name_words or first in initials_found or first in aliases
        ):
            aliases.add(first)

    aliases = {a for a in aliases if a and a not in GENERIC}
    return aliases, initials_found - aliases - GENERIC


class ClubNameMatcher:
    def __init__(self, chunks: list[dict]) -> None:
        texts: dict[str, list[str]] = defaultdict(list)
        names: dict[str, str] = {}
        for c in chunks:
            texts[c["club_id"]].append(c["text"])
            names[c["club_id"]] = c["name"]

        owners: dict[str, set[str]] = defaultdict(set)
        upper_only: set[str] = set()
        for club_id, name in names.items():
            aliases, initials = _club_aliases(name, "\n".join(texts[club_id]))
            for alias in aliases | initials:
                owners[alias].add(club_id)
            upper_only |= initials

        for alias, club_id in self._extra_aliases(names).items():
            owners[alias] = {club_id}

        # Keep only unambiguous aliases; match longest first.
        self.aliases = {a: next(iter(ids)) for a, ids in owners.items() if len(ids) == 1}
        self._patterns = []
        for a, club_id in sorted(self.aliases.items(), key=lambda kv: -len(kv[0])):
            if a in upper_only:
                pattern = re.compile(rf"(?<![\w]){re.escape(a.upper())}(?![\w])")
            else:
                pattern = re.compile(rf"(?<![\w]){re.escape(a)}(?![\w])", re.I)
            self._patterns.append((pattern, club_id))

    @staticmethod
    def _extra_aliases(names: dict[str, str]) -> dict[str, str]:
        if not ALIAS_FILE.exists():
            return {}
        by_name = {n.lower(): cid for cid, n in names.items()}
        extra = {}
        with ALIAS_FILE.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                club_id = by_name.get((row.get("club") or "").strip().lower())
                alias = (row.get("alias") or "").strip().lower()
                if club_id and alias:
                    extra[alias] = club_id
        return extra

    def find_spans(self, text: str) -> list[tuple[int, int, str]]:
        """(start, end, club_id) for every club mention, longest names first."""
        spans: list[tuple[int, int, str]] = []
        for pattern, club_id in self._patterns:
            for m in pattern.finditer(text):
                if not any(m.start() < e and s < m.end() for s, e, _ in spans):
                    spans.append((m.start(), m.end(), club_id))
        return sorted(spans)

    def find(self, text: str) -> list[str]:
        """Club ids named in the text, in the order they appear."""
        found: list[tuple[int, str]] = []
        taken: list[range] = []
        for pattern, club_id in self._patterns:
            for m in pattern.finditer(text):
                span = range(m.start(), m.end())
                if any(span.start < t.stop and t.start < span.stop for t in taken):
                    continue  # part of a longer name already matched
                taken.append(span)
                if club_id not in {cid for _, cid in found}:
                    found.append((m.start(), club_id))
        return [cid for _, cid in sorted(found)]
