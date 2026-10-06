"""Question-answering pipeline: rewrite query -> retrieve -> generate."""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict

from .citations import repair_citations
from .club_names import ClubNameMatcher
from .config import settings
from .data_loader import load_clubs
from .followups import suggest_follow_ups
from .generator import MODE_RAG, cited_numbers, generate_answer
from .knowledge_base import load_chunks
from .query_hints import asks_about_computing_clubs, expand_query, is_broad_social, put_open_clubs_first
from .retrievers import Retriever, create_retriever

log = logging.getLogger(__name__)

_retriever: Retriever | None = None
_matcher: ClubNameMatcher | None = None
_club_records: dict[str, dict] = {}
_club_links: dict[str, list[dict]] = {}

# Links shown on each source card, in this order (label, field in the club data).
LINK_FIELDS = [
    ("Club page", "rubric_url"), ("Website", "website"), ("Join", "join_url"),
    ("Discord", "discord"), ("Instagram", "instagram"), ("Linktree", "linktree"),
    ("LinkedIn", "linkedin"), ("Facebook", "facebook"),
]


def build_club_links(clubs: list[dict]) -> dict[str, list[dict]]:
    links = {}
    for club in clubs:
        seen, items = set(), []
        for label, field in LINK_FIELDS:
            url = (club.get(field) or "").strip()
            if url.startswith(("http://", "https://")) and url not in seen:
                seen.add(url)
                items.append({"label": label, "url": url})
        email = (club.get("email") or "").strip()
        if "@" in email and " " not in email:
            items.append({"label": "Email", "url": f"mailto:{email}"})
        links[club["id"]] = items
    return links


def init(rebuild: bool = False, retriever_name: str | None = None) -> Retriever:
    """Load the knowledge base and build the configured retriever."""
    global _retriever, _matcher, _club_records, _club_links
    name = retriever_name or settings.retriever
    started = time.perf_counter()
    chunks = load_chunks()
    retriever = create_retriever(name)
    retriever.build(chunks, rebuild=rebuild)
    _retriever = retriever
    _matcher = ClubNameMatcher(chunks)
    _club_records = build_club_records(chunks)
    _club_links = build_club_links(load_clubs(settings.data_path))
    log.info("Retriever %s ready: %d chunks in %.1fs", name, len(chunks), time.perf_counter() - started)
    return retriever


def get_retriever() -> Retriever:
    return _retriever or init()


def build_club_records(chunks: list[dict]) -> dict[str, dict]:
    """One full record per club (all its chunks joined, repeated headers removed).

    Retrieval matches individual chunks, but the model is given the whole club
    record, so "how do I join X?" gets the contact details even when the
    overview chunk was the one that matched.
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        grouped[c["club_id"]].append(c)
    records = {}
    for club_id, parts in grouped.items():
        lines, seen = [], set()
        for part in parts:
            for line in part["text"].splitlines():
                if line.strip() and line not in seen:
                    seen.add(line)
                    lines.append(line)
        records[club_id] = {**parts[0], "text": "\n".join(lines)}
    return records


_GENERIC_NAME_WORDS = {"rmit", "club", "society", "association", "students", "student", "the", "and", "of", "at", "in"}


def is_near_empty(record: dict) -> bool:
    """No real description and nothing about activities: little to tell a student."""
    text = record.get("text", "")
    has_description = "No detailed description published yet." not in text
    has_activities = any(f"{label}:" in text for label in ("Notes", "Usual activities", "Event date"))
    return not has_description and not has_activities


def _name_in_question(record: dict, question: str) -> bool:
    words = {w for w in re.findall(r"[a-z]{3,}", record.get("name", "").lower()) if w not in _GENERIC_NAME_WORDS}
    asked = {w[:6] for w in re.findall(r"[a-z]{3,}", question.lower())}
    return any(w[:6] in asked for w in words)


def gather_clubs(query: str, top_k: int, question: str | None = None) -> list[dict]:
    """Clubs named in the query first, then the best retrieval matches.

    Background-specific clubs (cultural, religious, political) the student
    didn't ask about are moved behind open clubs; see query_hints.py.
    """
    get_retriever()
    question = question or query
    named = _matcher.find(query) if _matcher else []
    if asks_about_computing_clubs(question):
        named += [cid for cid, rec in _club_records.items() if "Type: Computing" in rec["text"] and cid not in named]
    search_query = expand_query(query, question)
    results = _retriever.search(search_query, top_k=top_k * 3 + len(named))
    by_id = {r["club_id"]: r for r in results}
    top_score = max((r["score"] for r in results), default=1.0)

    clubs = []
    for club_id in named:
        hit = by_id.get(club_id, {"score": top_score})
        clubs.append({**_club_records[club_id], "score": hit["score"], "relevant": True, "named": True})
    others = []
    for r in results:
        if r["club_id"] not in named:
            record = _club_records.get(r["club_id"], r)
            # Near-empty clubs only go to the model when the student names them
            # (or a word of their name); otherwise they invite wrong citations.
            if is_near_empty(record) and not _name_in_question(record, question):
                continue
            others.append({**record, "score": r["score"], "relevant": r["relevant"]})
    clubs += put_open_clubs_first(question, others)
    return clubs[: max(top_k, len(named))]


# Words that show a question refers back to the previous turn.
_REFERS_BACK = re.compile(
    r"\b(they|them|their|theirs|it|its|those|these|this one|that one|this club|that club|"
    r"the club|which one|either|both)\b|^(and|also|what about|how about)\b"
    # questions with no subject of their own, e.g. "how do I join?"
    r"|^(how|where|when) (do|can|does|should) (i|we|you) \w+( up| in| involved)?\W*$",
    re.IGNORECASE,
)


def rewrite_query(question: str, history: list[dict]) -> str:
    """Add the previous user question to follow-ups that refer back to it.

    "How do I contact them?" after "any chess clubs?" retrieves chess clubs,
    while a new topic ("I'm new to Melbourne") is searched on its own.
    No extra LLM call is needed.
    """
    previous = next((h["content"] for h in reversed(history) if h["role"] == "user"), None)
    if previous and len(question.split()) <= 12 and _REFERS_BACK.search(question):
        return f"{question} {previous}"
    return question


def answer_question(question: str, history: list[dict], top_k: int = 4) -> dict:
    started = time.perf_counter()
    retrieval_query = rewrite_query(question, history)
    results = gather_clubs(retrieval_query, top_k, question)
    retrieved = time.perf_counter()

    generation = generate_answer(question, history, results)
    finished = time.perf_counter()

    citation_fixes = 0
    if generation.mode == MODE_RAG and _matcher:
        repaired, citation_fixes = repair_citations(
            generation.answer, [item["club_id"] for item in generation.sources], _matcher
        )
        generation.answer = repaired

    # Show only the sources the answer cites, keeping their numbers so [n]
    # still matches. An LLM answer that cites nothing is a decline, so it
    # gets no sources (and general follow-up suggestions).
    numbered = list(enumerate(generation.sources, 1))
    if generation.mode == MODE_RAG:
        cited = cited_numbers(generation.answer)
        numbered = [(n, item) for n, item in numbered if n in cited]

    sources = [
        {
            "number": number,
            "id": item["club_id"],
            "name": item["name"],
            "url": item.get("url", ""),
            "category": item.get("category", ""),
            "score": round(item["score"], 4),
            "excerpt": item["text"][:260],
            "links": _club_links.get(item["club_id"], []),
        }
        for number, item in numbered
    ]

    timings = {
        "retrieval_ms": round((retrieved - started) * 1000),
        "generation_ms": round((finished - retrieved) * 1000),
        "total_ms": round((finished - started) * 1000),
    }
    log.info("mode=%s sources=%d total_ms=%d q=%r", generation.mode, len(sources), timings["total_ms"], question)

    return {
        "answer": generation.answer,
        "sources": sources,
        "mode": generation.mode,
        "retriever": get_retriever().name,
        "retrieval_query": retrieval_query,
        "citation_fixes": citation_fixes,
        "follow_ups": suggest_follow_ups(question, sources, broad=is_broad_social(question)),
        "timings": timings,
    }
