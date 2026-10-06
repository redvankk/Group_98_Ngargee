"""Suggested next questions shown under each answer.

The templates are a short, team-written list (as agreed in the PRD), filled in
with the clubs the answer actually cited. No extra LLM call is needed, and each
suggestion names its club, so it works as a stand-alone question.
"""
from __future__ import annotations

import re

# Team-written templates. Edit freely; {a} and {b} are club names.
SINGLE_CLUB = [
    ("join", "How do I join {a}?"),
    ("contact", "How can I contact {a}?"),
    ("similar", "Are there other clubs like {a}?"),
]
TWO_CLUBS = ("compare", "What's the difference between {a} and {b}?")

# Used when nothing relevant was found.
GENERAL = [
    "Are there any technology or computing clubs?",
    "Which clubs are good for meeting new people?",
    "Are there cultural clubs for international students?",
]

# Used after broad "meet people" questions, to narrow down by interest.
INTERESTS = [
    "Are there clubs for board games or video games?",
    "Are there tech or coding clubs?",
    "Are there arts, music or creative clubs?",
]

# Skip a suggestion if the question already asked that kind of thing.
ASKED = {
    "join": re.compile(r"\b(join|sign up|membership|member)\b", re.I),
    "contact": re.compile(r"\b(contact|email|reach|instagram|discord)\b", re.I),
    "compare": re.compile(r"\b(difference|compare|versus|vs)\b", re.I),
    "similar": re.compile(r"\b(other|similar|like)\b", re.I),
}


def suggest_follow_ups(question: str, sources: list[dict], limit: int = 3, broad: bool = False) -> list[str]:
    if broad:
        return INTERESTS[:limit]
    names = []
    for s in sources:
        if s["name"] not in names:
            names.append(s["name"])

    if not names:
        return GENERAL[:limit]

    a = names[0]
    candidates: list[tuple[str, str]] = []
    if len(names) > 1:
        kind, template = TWO_CLUBS
        candidates.append((kind, template.format(a=a, b=names[1])))
    candidates += [(kind, template.format(a=a)) for kind, template in SINGLE_CLUB]

    suggestions = [text for kind, text in candidates if not ASKED[kind].search(question)]
    return suggestions[:limit]
