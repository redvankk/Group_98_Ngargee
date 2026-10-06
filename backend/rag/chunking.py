from __future__ import annotations

import re

# "On Rubric since 2025" tells a student nothing and distracts the model.
_RUBRIC_SINCE = re.compile(r"(club has been |listed )?on rubric since \d{4}[.;,]?\s*", re.I)


def _tidy_notes(text: str) -> str:
    return _RUBRIC_SINCE.sub("", text or "").strip(" ;.")


def _line(label: str, value: str) -> str:
    value = (value or "").strip()
    return f"{label}: {value}\n" if value else ""


def club_to_chunks(club: dict) -> list[dict]:
    """Split one club record into retrieval chunks.

    overview            what the club is about (matched by interest questions)
    membership_contact  who can join, contacts and links ("how do I join X?")
    activities          listed events, usual activities and notes ("events", "trivia")
    """
    common = f"Club: {club['name']}\n" + _line("Category", club.get("category", ""))

    description = club.get("description", "")
    overview = (
        common
        + _line("Also known as", club.get("also_known_as", ""))
        + _line("Type", club.get("tags", ""))
        + _line("Description", description or "No detailed description published yet.")
        + _line("Campus", club.get("campus", ""))
    )

    membership_contact = (
        common
        + _line("Who can join", club.get("membership", ""))
        + _line("Full membership", club.get("membership_full", ""))
        + _line("Associate membership", club.get("membership_associate", ""))
        + _line("Social membership", club.get("membership_social", ""))
        + _line("Under 18 membership", club.get("membership_under_18", ""))
        + _line("Club email", club.get("email", ""))
        + _line("Contact / committee", club.get("committee", ""))
        + _line("Instagram", club.get("instagram", ""))
        + _line("Facebook", club.get("facebook", ""))
        + _line("Discord", club.get("discord", ""))
        + _line("LinkedIn", club.get("linkedin", ""))
        + _line("Linktree", club.get("linktree", ""))
        + _line("Website", club.get("website", ""))
        + _line("Membership / join link", club.get("join_url", ""))
        + _line("Club page", club.get("rubric_url", ""))
    )

    event_bits = ""
    if club.get("event_name"):
        checked = club.get("events_checked", "")
        event_bits = (
            _line(f"Listed event{f' (as listed on {checked})' if checked else ''}", club["event_name"])
            + _line("Event date", club.get("event_date", ""))
            + _line("Event location", club.get("event_location", ""))
            + _line("Event type", club.get("event_type", ""))
        )
    activities = (
        common
        + event_bits
        + _line("Usual activities", club.get("event_frequency", ""))
        + _line("Notes", _tidy_notes(club.get("notes", "")))
    )

    chunks = [("overview", overview.strip())]
    for kind, text in (("membership_contact", membership_contact), ("activities", activities)):
        if text.strip() != common.strip():
            chunks.append((kind, text.strip()))

    return [
        {
            "chunk_id": f"{club['id']}::{i}",
            "club_id": club["id"],
            "name": club["name"],
            "category": club.get("category", "Uncategorised"),
            "url": club.get("url", ""),
            "chunk_type": chunk_type,
            "text": text,
        }
        for i, (chunk_type, text) in enumerate(chunks)
    ]
