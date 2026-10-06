"""Check the model's citations against the clubs it names.

A small model sometimes writes about one club but cites another club's number
(e.g. "Board Game Association [2]" when [2] is Matcha Club). After each answer,
every citation is compared with the nearest club named before it in the same
sentence:
  - named club is among the sources under another number -> number corrected
  - named club is not among the sources                   -> citation removed
  - no club named nearby ("their Discord [1]")            -> left as it is
No model call is involved.
"""
from __future__ import annotations

import logging
import re

from .club_names import ClubNameMatcher

log = logging.getLogger(__name__)
_CITATION = re.compile(r"\[(\d+)\]")
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*\n?|\n")


def repair_citations(answer: str, source_ids: list[str], matcher: ClubNameMatcher) -> tuple[str, int]:
    """Returns (answer with corrected citations, number of changes)."""
    number_of = {club_id: n for n, club_id in enumerate(source_ids, 1)}
    changes = 0
    out = []
    for sentence in _SENTENCE.findall(answer):
        spans = matcher.find_spans(sentence)
        if not spans:
            out.append(sentence)
            continue

        def fix(m: re.Match) -> str:
            nonlocal changes
            cited = int(m.group(1))
            before = [club for start, end, club in spans if end <= m.start()]
            if not before:
                return m.group(0)
            named = before[-1]
            right = number_of.get(named)
            if right is None:
                changes += 1
                log.info("Removed citation [%d]: %s is not among the sources", cited, named)
                return ""
            if right != cited:
                changes += 1
                log.info("Citation [%d] corrected to [%d] for %s", cited, right, named)
                return f"[{right}]"
            return m.group(0)

        out.append(_CITATION.sub(fix, sentence))
    repaired = re.sub(r"[ \t]+([.,;:!?])", r"\1", "".join(out))
    repaired = re.sub(r"(\S)[ \t]{2,}(\S)", r"\1 \2", repaired)
    return repaired, changes
