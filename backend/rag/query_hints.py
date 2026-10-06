"""Team-written rules that shape retrieval for broad or identity-related questions.

1. Search hints: vague social questions ("I'm new and want to make friends")
   get extra search terms that describe clubs open to everyone, so general
   social clubs are found, not only clubs whose blurb says "make friends".

2. Background-specific clubs: clubs for a particular culture, religion or
   political view are only put forward when the student mentions that
   background or topic. Otherwise they move behind open clubs, so the
   assistant doesn't assume where someone is from or what they believe.

Edit the lists below to change the behaviour; no model call is involved.
"""
from __future__ import annotations

import re

# --- 1. search hints -------------------------------------------------------

BROAD_SOCIAL = re.compile(
    r"\b(make (new )?friends|meet (new )?people|meeting people|new to (melbourne|rmit|uni|"
    r"university|australia|the city)|first[- ]year|lonely|socialis|social life|hang out|"
    r"fit in|get involved|something fun|fun clubs?)\b",
    re.IGNORECASE,
)
SOCIAL_HINT = "everyone welcome all students fun social hangouts board games chess anime movie nights"

# Questions about "the computing clubs" as a group get every club the team
# tagged as Computing, so counting and listing questions see all of them.
COMPUTING_GROUP = re.compile(r"\b(computing|computer science|tech(nology)?|it) (clubs?|societies|society)\b", re.I)


def asks_about_computing_clubs(question: str) -> bool:
    return bool(COMPUTING_GROUP.search(question))


# --- 2. background-specific clubs ------------------------------------------

BACKGROUND_CATEGORIES = {"Cultural & International", "Spiritual & Religious", "Political"}

# Mentioning any of these opens up the matching category.
CATEGORY_WORDS = {
    "Cultural & International": re.compile(r"\b(cultur\w*|international|heritage|language|homesick|my country)\b", re.I),
    "Spiritual & Religious": re.compile(r"\b(religio\w*|faith|spiritual|church|mosque|temple|pray\w*|god|bible)\b", re.I),
    "Political": re.compile(r"\b(politic\w*|activis\w*|campaign\w*|party|election|left[- ]wing|right[- ]wing)\b", re.I),
}

# Words that appear in many club texts but say nothing about a background.
NOT_IDENTITY = {
    "rmit", "melbourne", "australia", "university", "campus", "club", "clubs", "society",
    "association", "student", "students", "community", "group", "union", "network", "we",
    "we're", "our", "join", "hello", "welcome", "hi", "the", "this", "official", "rusu",
    "cultural", "international", "events", "event", "a", "an", "and", "of", "at", "in",
    # record labels and category words
    "category", "description", "campus", "type", "notes", "listed", "usual", "activities",
    "academic", "professional", "spiritual", "religious", "political", "special", "interest",
    "social", "website", "discord", "instagram", "facebook", "linkedin", "email", "membership",
    "page", "link", "rubric", "free", "past", "upcoming", "join", "sign", "please", "contact",
}


# Words that don't narrow a social question down to a particular interest.
_FILLER = {
    "i'm", "im", "am", "i", "a", "an", "the", "and", "to", "of", "in", "at", "for", "with", "some",
    "want", "would", "like", "love", "really", "just", "here", "new", "melbourne", "rmit", "uni",
    "university", "australia", "city", "student", "students", "people", "friends", "make",
    "meet", "meeting", "other", "get", "involved", "fun", "something", "clubs", "club", "any",
    "are", "there", "is", "what", "which", "how", "can", "do", "where", "should", "join", "my",
    "me", "first", "year", "lonely", "feel", "feeling", "bit", "life", "social", "hang", "out",
    "fit", "recommend", "good", "best", "find", "help", "please", "know", "anyone",
}


def is_broad_social(question: str) -> bool:
    """True for social questions with no particular interest or background named,
    e.g. "I'm new to Melbourne and want to make friends" (but not "...from
    Singapore and want to make friends" or "meet people who like anime")."""
    if not BROAD_SOCIAL.search(question):
        return False
    words = re.findall(r"[a-z']+", question.lower())
    return not [w for w in words if w not in _FILLER and len(w) > 2]


def expand_query(query: str, question: str) -> str:
    return f"{query} {SOCIAL_HINT}" if is_broad_social(question) else query


def _identity_terms(club: dict) -> set[str]:
    """Words that identify who a background-specific club is for: its name, its
    type, and capitalised words in its description (e.g. "Singapore", "Filipino").
    Event and notes text is ignored, so "Game Night" doesn't count."""
    text = club.get("text", "")
    lines = re.findall(r"^(?:Type|Description): (.*)$", text, flags=re.M)
    lines.append(club.get("description", ""))
    words = re.findall(r"[A-Za-z]{4,}", club.get("name", "") + " " + club.get("tags", ""))
    for line in lines:
        words += re.findall(r"\b[A-Z][a-z]{3,}\w*", re.sub(r"https?://\S+", " ", line))
    return {w.lower()[:6] for w in words if w.lower() not in NOT_IDENTITY}


def mentions_background(question: str, club: dict) -> bool:
    pattern = CATEGORY_WORDS.get(club.get("category", ""))
    if pattern and pattern.search(question):
        return True
    asked = {w.lower()[:6] for w in re.findall(r"[A-Za-z]{4,}", question)}
    return bool(asked & _identity_terms(club))


def put_open_clubs_first(question: str, clubs: list[dict]) -> list[dict]:
    """Move background-specific clubs the student didn't ask about to the end.

    For broad "meet people" questions, interest clubs anyone can join
    (Social & Special Interest) also go ahead of course-specific clubs.
    """
    broad = is_broad_social(question)

    def rank(club: dict) -> int:
        if club.get("category") in BACKGROUND_CATEGORIES and not club.get("named"):
            return 0 if mentions_background(question, club) else 2
        if broad and club.get("category") != "Social & Special Interest":
            return 1
        return 0

    return sorted(clubs, key=rank)  # stable: keeps retrieval order within each group
