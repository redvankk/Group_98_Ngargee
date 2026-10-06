"""Build the tidy club dataset from the two raw sources.

Inputs (unchanged, kept for traceability):
  data/Clubs.csv                              team's manual spreadsheet (Windows-1252,
                                              event columns shifted on some rows)
  scraper/club_profiles_structured.csv        Rubric scrape (all clubs, source URLs)

  data/five_clubs/*.csv                       team's detailed files for the five computing
                                              clubs (club, membership, social, executive)

Outputs (UTF-8 with BOM so Excel opens them correctly):
  data/clubs_master.csv        one tidy row per club; the app's knowledge base
  data/collection.csv          Walert-format passages: passage_id, passage
  data/collection.jsonl        Walert/Pyserini format: {"id", "contents"}
  data/build_report.csv        how each club was matched and which fields came from where

Run from backend/:  python data/build_dataset.py
"""
from __future__ import annotations

import csv
import difflib
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
MANUAL = DATA / "Clubs.csv"
SCRAPED = BACKEND / "scraper" / "club_profiles_structured.csv"
FIVE_CLUBS = DATA / "five_clubs"

PLACEHOLDERS = {
    "", "-", "—", "–", "n/a", "na", "none", "nil", "nan", "not available", "not listed",
    "not publicly listed", "not specified", "none listed", "no upcoming events listed",
    "no upcoming events shown", "no events listed", "date not provided", "rubric",
    "rubric events", "tbc", "tba",
}
NAME_FIXES = {
    "International Studies Associaiton": "International Studies Association",
    "Pspchology Student Society": "Psychology Student Society",
    "RMIT Engineers Austrila Student Society": "RMIT Engineers Australia Student Society",
    "Women in Built Envirnoments": "Women in Built Environments",
    "Laboratory Medicine association": "Laboratory Medicine Association",
    "Student Osteopathic Medicine association": "Student Osteopathic Medicine Association",
}
CATEGORIES = {
    "academic and professional": "Academic & Professional",
    "cultural and international": "Cultural & International",
    "social and special interest": "Social & Special Interest",
    "spiritual and religious": "Spiritual & Religious",
    "political": "Political",
}
PLACEHOLDER_DESCRIPTION = re.compile(r"check out our events, merch,? and memberships", re.I)
EVENT_BLOCK = [
    "Upcoming Event", "Event Date", "Event Location", "Event Type",
    "Event Frequency", "Other Contact / Notes", "Source", "Last Checked",
]
LAST_CHECKED = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2,4}$")
EVENT_DATE = re.compile(r"^\d{1,2} [A-Z][a-z]{2} \d{4}")

COLUMNS = [
    "club_id", "name", "category", "tags", "description", "description_quality",
    "who_can_join", "campus", "email", "instagram", "facebook", "discord", "linkedin",
    "website", "join_url", "rubric_url", "events_url",
    "event_name", "event_date", "event_location", "event_type", "event_frequency",
    "notes", "events_checked", "sources", "last_checked",
    # detailed fields, currently filled for the five computing clubs
    "acronym", "also_known_as", "focus_area", "membership_full", "membership_associate",
    "membership_social", "membership_under_18", "linktree", "committee",
]
COMMITTEE_ROLES = [
    ("president", "President"), ("vice_president", "Vice President"),
    ("vice_president_operations", "Vice President (Operations)"),
    ("vice_president_administration", "Vice President (Administration)"),
    ("secretary", "Secretary"), ("treasurer", "Treasurer"),
    ("social_media_manager", "Social Media Manager"), ("sponsorship_officer", "Sponsorship Officer"),
    ("events_officer", "Events Officer"),
]
NOT_EVENT = re.compile(
    r"^(discord|instagram|facebook|email|linkedin)\b|membership|^no (specific )?upcoming|^no .*event", re.I
)


# ---------------------------------------------------------------- helpers

def clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()
    return "" if text.casefold() in PLACEHOLDERS else text


def is_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "club"


def match_key(name: str) -> str:
    name = re.sub(r"\([^)]*\)", " ", name.casefold())
    name = name.replace("&", " and ")
    words = [w for w in re.findall(r"[a-z0-9]+", name) if w not in {"rmit", "the", "university"}]
    return " ".join(words)


def to_iso_date(text: str) -> str:
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:25].split("T")[0] if fmt == "%Y-%m-%d" else text, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


# Notes written while collecting the data, not information for students.
# They are removed so they can't be retrieved or quoted to a student.
INTERNAL_NOTE = re.compile(
    r"rubric since \d{4}|supplied (content|data)|last checked|^note:|no future event|"
    r"^no (specific )?(upcoming )?events?( information)? (provided|listed|currently listed)|"
    r"^no (other )?events (currently )?listed|^no events or membership|event history available|"
    r"information: not found$|please contact the club for more information|^\d{1,2}/\d{1,2}/\d{4}$",
    re.IGNORECASE,
)


def clean_notes(text: str) -> str:
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z\d])", text)
    kept = []
    for part in parts:
        part = part.strip().strip(";").strip()
        if part and not INTERNAL_NOTE.search(part.rstrip(".")):
            kept.append(re.sub(r"(https?://\S+?)\.$", r"\1", part.rstrip(";")))
    # add a full stop between pieces, but never glue one onto the end of a link
    return " ".join(p if p.endswith((".", "!", "?")) or re.search(r"https?://\S+$", p) else p + "." for p in kept)


def is_real_description(text: str) -> bool:
    return bool(text) and not PLACEHOLDER_DESCRIPTION.search(text)


# ---------------------------------------------------------------- manual sheet

def read_manual() -> list[dict]:
    df = pd.read_csv(MANUAL, encoding="cp1252", dtype=str).dropna(how="all")
    columns = list(df.columns)
    block_start = columns.index(EVENT_BLOCK[0])
    last_checked_col = columns.index("Last Checked")

    rows = []
    for _, raw in df.iterrows():
        name = clean(raw.get("Club Name"))
        if not name or name.casefold().startswith(("legend", "selected rusu")):
            continue
        cells = [raw.iloc[i] if i < len(raw) else None for i in range(len(columns))]

        # Some rows have extra cells pushed into the event block. The last cell
        # holding a date like 19-Aug-26 is the real "Last Checked"; realign the
        # 8 event columns so they end there.
        shift = None
        for i in range(len(cells) - 1, block_start - 1, -1):
            if LAST_CHECKED.match(clean(cells[i])):
                shift = i - last_checked_col
                break
        if shift is None:
            # No "Last Checked" date: anchor on the first event date instead.
            event_date_col = columns.index("Event Date")
            for i in range(block_start, len(cells)):
                if EVENT_DATE.match(clean(cells[i])):
                    shift = i - event_date_col
                    break
        shift = shift or 0
        event = {
            col: clean(cells[block_start + k + shift]) if 0 <= block_start + k + shift < len(cells) else ""
            for k, col in enumerate(EVENT_BLOCK)
        }

        # Contact details or membership notes that landed in event columns go to notes.
        stray = []
        for col in EVENT_BLOCK[:5]:
            if NOT_EVENT.search(event[col]):
                stray.append(event[col])
                event[col] = ""
        event["Other Contact / Notes"] = "; ".join(filter(None, stray + [event["Other Contact / Notes"]]))

        rows.append(
            {
                "name": NAME_FIXES.get(name, name),
                "category_raw": clean(raw.get("Category")),
                "description": clean(raw.get("Description")),
                "who_can_join": clean(raw.get("Who Can Join")),
                "campus": clean(raw.get("Campus")),
                "email": clean(raw.get("Club Email")),
                "instagram": clean(raw.get("Instagram")),
                "facebook": clean(raw.get("Facebook")),
                "linkedin": clean(raw.get("LinkedIn")),
                "website": clean(raw.get("Website")),
                "rubric_url": clean(raw.get("Rubric Club Page")),
                "join_url": clean(raw.get("Membership / Join Link")),
                "events_url": clean(raw.get("Events Page")),
                "event_name": event["Upcoming Event"],
                "event_date": event["Event Date"],
                "event_location": event["Event Location"],
                "event_type": event["Event Type"],
                "event_frequency": event["Event Frequency"],
                "notes": event["Other Contact / Notes"],
                "source": event["Source"],
                "last_checked": to_iso_date(event["Last Checked"]),
                "event_shift": shift,
            }
        )
    return rows


# ---------------------------------------------------------------- scraped data

def read_scraped() -> list[dict]:
    df = pd.read_csv(SCRAPED, dtype=str)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "name": clean(r["club_name"]),
                "category": CATEGORIES.get(clean(r["category"]).casefold(), clean(r["category"])),
                "description": clean(r["description"]),
                "email": clean(r["emails"]).split(" | ")[0] if clean(r["emails"]) else "",
                "instagram": clean(r["instagram"]),
                "facebook": clean(r["facebook"]),
                "discord": clean(r["discord"]),
                "linkedin": clean(r["linkedin"]),
                "rubric_url": clean(r["source_url"]),
                "scraped_on": to_iso_date(clean(r["last_scraped_utc"])),
            }
        )
    return rows


# ---------------------------------------------------------------- merge

def best_link(*values: str) -> str:
    return next((v for v in values if is_url(v)), "")


def merge() -> tuple[list[dict], list[dict]]:
    manual = read_manual()
    scraped = read_scraped()
    scraped_by_key = {match_key(s["name"]): s for s in scraped}
    used_scraped: set[str] = set()

    clubs, report = [], []
    for m in manual:
        key = match_key(m["name"])
        s, how = scraped_by_key.get(key), "exact"
        if s is None:
            close = difflib.get_close_matches(key, list(scraped_by_key), n=1, cutoff=0.88)
            s, how = (scraped_by_key[close[0]], "fuzzy") if close else (None, "manual only")
        if s:
            used_scraped.add(match_key(s["name"]))
        clubs.append(combine(m, s))
        report.append({"club": m["name"], "matched_rubric_name": s["name"] if s else "", "match": how,
                       "event_columns_realigned_by": m["event_shift"]})

    for key, s in scraped_by_key.items():
        if key not in used_scraped:
            clubs.append(combine(None, s))
            report.append({"club": s["name"], "matched_rubric_name": s["name"], "match": "rubric only",
                           "event_columns_realigned_by": 0})

    # unique, stable ids (from the merged name, before the five-club names apply)
    seen: set[str] = set()
    for club in sorted(clubs, key=lambda c: c["name"].casefold()):
        base = cid = slugify(club["name"])
        n = 2
        while cid in seen:
            cid, n = f"{base}-{n}", n + 1
        seen.add(cid)
        club["club_id"] = cid
    for r in report:
        r.setdefault("five_club_files", "")
    enrich_five_clubs(clubs, report)
    clubs.sort(key=lambda c: c["name"].casefold())
    return clubs, report


def combine(m: dict | None, s: dict | None) -> dict:
    m, s = m or {}, s or {}
    manual_desc, scraped_desc = m.get("description", ""), s.get("description", "")
    candidates = [d for d in (manual_desc, scraped_desc) if is_real_description(d)]
    if candidates:
        description, quality = max(candidates, key=len), "full"
    else:
        description = manual_desc or scraped_desc
        quality = "placeholder" if description else "missing"

    category = s.get("category") or CATEGORIES.get(m.get("category_raw", "").casefold(), "")
    tags = m.get("category_raw", "")
    if not category:  # manual-only rows with a free-text category
        raw = tags.casefold()
        category = next((v for k, v in CATEGORIES.items() if k.split()[0] in raw), "Social & Special Interest")
    if tags.casefold() == category.casefold().replace("&", "and") or tags == category:
        tags = ""

    sources = [label for label, present in (("team spreadsheet", bool(m)), ("Rubric scrape", bool(s))) if present]
    if m.get("source"):
        sources.append(m["source"])

    return {
        "name": m.get("name") or s.get("name"),
        "category": category,
        "tags": tags,
        "description": description,
        "description_quality": quality,
        "who_can_join": m.get("who_can_join", ""),
        "campus": m.get("campus", ""),
        "email": m.get("email") or s.get("email", ""),
        "instagram": best_link(m.get("instagram", ""), s.get("instagram", "")) or m.get("instagram", ""),
        "facebook": best_link(m.get("facebook", ""), s.get("facebook", "")),
        "discord": s.get("discord", ""),
        "linkedin": best_link(m.get("linkedin", ""), s.get("linkedin", "")),
        "website": best_link(m.get("website", "")),
        "join_url": best_link(m.get("join_url", "")),
        "rubric_url": best_link(s.get("rubric_url", ""), m.get("rubric_url", "")),
        "events_url": best_link(m.get("events_url", "")),
        "event_name": m.get("event_name", ""),
        "event_date": m.get("event_date", ""),
        "event_location": m.get("event_location", ""),
        "event_type": m.get("event_type", ""),
        "event_frequency": m.get("event_frequency", ""),
        "notes": clean_notes(m.get("notes", "")),
        "events_checked": m.get("last_checked", ""),
        "sources": "; ".join(dict.fromkeys(sources)),
        **{k: "" for k in ("acronym", "also_known_as", "focus_area", "membership_full", "membership_associate",
                           "membership_social", "membership_under_18", "linktree", "committee")},
        "last_checked": max(filter(None, [m.get("last_checked", ""), s.get("scraped_on", "")]), default=""),
    }



# ---------------------------------------------------------------- five computing clubs

def _read_team_csv(path: Path, header_starts: str) -> pd.DataFrame:
    """The team's files have title rows above the header; start at the header."""
    import io

    text = path.read_text(encoding="utf-8-sig").replace("\ufeff", "")
    return pd.read_csv(io.StringIO(text[text.index(header_starts):]), dtype=str).fillna("")


def _best_name(acronym: str, *names: str) -> str:
    """Prefer the name that includes the acronym, e.g. "SWITCH (Society of Women
    in Technology)"; otherwise the longest, e.g. "RMIT Information Security Collective"."""
    names = [n for n in dict.fromkeys(clean(n) for n in names) if n]
    with_acronym = [n for n in names if acronym and re.search(rf"\b{re.escape(acronym)}\b", n, re.I)]
    return max(with_acronym or names, key=len)


def enrich_five_clubs(clubs: list[dict], report: list[dict]) -> None:
    if not (FIVE_CLUBS / "club.csv").exists():
        return
    info = _read_team_csv(FIVE_CLUBS / "club.csv", "club_index")
    membership = _read_team_csv(FIVE_CLUBS / "membership.csv", "club_acronym")
    social = _read_team_csv(FIVE_CLUBS / "social.csv", "club_email")
    executive = _read_team_csv(FIVE_CLUBS / "executive.csv", "club_name")

    tiers = {clean(r["club_acronym"]).lower(): r for _, r in membership.iterrows()}
    links = {clean(r["club_email"]).lower(): r for _, r in social.iterrows()}

    for _, row in info.iterrows():
        acronym = clean(row["club_acronym"])
        name = clean(row["club_name"])
        key = match_key(name)
        exec_row = next((r for _, r in executive.iterrows()
                         if match_key(r["club_name"]) == key or acronym.lower() in clean(r["club_name"]).lower()), None)
        club = next((c for c in clubs if match_key(c["name"]) == key), None)
        if club is None and exec_row is not None:
            club = next((c for c in clubs if match_key(c["name"]) == match_key(exec_row["club_name"])), None)
        if club is None:
            club = next((c for c in clubs if acronym and re.search(rf"\b{re.escape(acronym)}\b", c["name"], re.I)), None)
        if club is None:
            print(f"WARNING: five-club file row not matched: {name}")
            continue

        old_name = club["name"]
        club["name"] = _best_name(acronym, name, old_name, exec_row["club_name"] if exec_row is not None else "")
        club["also_known_as"] = "; ".join(n for n in dict.fromkeys([acronym, old_name, name]) if n and n != club["name"])
        club["acronym"] = acronym
        club["focus_area"] = "Computing"
        club["tags"] = "; ".join(t for t in dict.fromkeys(["Computing", club["tags"]]) if t)
        club["description"] = clean(row["description"]) or club["description"]
        club["description_quality"] = "full" if club["description"] else club["description_quality"]
        club["campus"] = clean(row["rmit_university_campus"]) or club["campus"]

        email = clean(exec_row["club_email"]) if exec_row is not None else ""
        club["email"] = email or club["email"]
        if exec_row is not None:
            club["committee"] = "; ".join(
                f"{label}: {clean(exec_row.get(col, ''))}" for col, label in COMMITTEE_ROLES if clean(exec_row.get(col, ""))
            )

        t = tiers.get(acronym.lower())
        if t is not None:
            club["membership_full"] = clean(t["full_membership"])
            club["membership_associate"] = clean(t["associate_membership"])
            club["membership_social"] = clean(t["social_membership"])
            club["membership_under_18"] = clean(t["under_18_membership"])

        l = links.get(email.lower())
        if l is not None:  # the team's verified links win
            for src, dst in (("instagram", "instagram"), ("facebook", "facebook"), ("linkedin", "linkedin"),
                             ("discord", "discord"), ("linktree", "linktree"), ("website", "website"),
                             ("rubric_page", "rubric_url")):
                if is_url(clean(l[src])):
                    club[dst] = clean(l[src])

        club["sources"] = "; ".join(dict.fromkeys(filter(None, [club["sources"], "team five-club files"])))
        for r in report:
            if r["club"] == old_name:
                r["five_club_files"] = "yes"


# ---------------------------------------------------------------- passages

def passage(club: dict) -> str:
    parts = [f"{club['name']} is an RMIT student club ({club['category']}"
             + (f"; {club['tags']}" if club["tags"] else "") + ")."]
    if club["description_quality"] == "full":
        parts.append(club["description"])
    else:
        parts.append("No detailed description is published for this club yet.")
    if club["also_known_as"]:
        parts.append(f"Also known as: {club['also_known_as']}.")
    for label, key in (("Full membership", "membership_full"), ("Associate membership", "membership_associate"),
                       ("Social membership", "membership_social"), ("Under 18 membership", "membership_under_18"),
                       ("Committee", "committee")):
        if club[key]:
            parts.append(f"{label}: {club[key]}.")
    for label, key in (("Who can join", "who_can_join"), ("Campus", "campus"), ("Email", "email"),
                       ("Instagram", "instagram"), ("Discord", "discord"), ("Website", "website"),
                       ("Linktree", "linktree"), ("Join", "join_url"), ("Club page", "rubric_url")):
        if club[key]:
            parts.append(f"{label}: {club[key]}.")
    if club["event_name"]:
        event = club["event_name"]
        details = ", ".join(v for v in (club["event_date"], club["event_location"]) if v)
        checked = f", as listed on {club['events_checked']}" if club["events_checked"] else ""
        parts.append(f"Listed event{checked}: {event}" + (f" ({details})" if details else "") + ".")
    if club["event_frequency"]:
        parts.append(f"Usual activity: {club['event_frequency']}.")
    if club["notes"]:
        parts.append(club["notes"])
    if club["last_checked"]:
        parts.append(f"Information last checked {club['last_checked']}.")
    return " ".join(parts)


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    clubs, report = merge()
    write_csv(DATA / "clubs_master.csv", clubs, COLUMNS)
    write_csv(DATA / "build_report.csv", report, list(report[0]))

    passages = [{"passage_id": c["club_id"], "passage": passage(c)} for c in clubs]
    write_csv(DATA / "collection.csv", passages, ["passage_id", "passage"])
    with (DATA / "collection.jsonl").open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps({"id": p["passage_id"], "contents": p["passage"]}, ensure_ascii=False) + "\n")

    quality = pd.Series([c["description_quality"] for c in clubs]).value_counts().to_dict()
    matches = pd.Series([r["match"] for r in report]).value_counts().to_dict()
    print(f"{len(clubs)} clubs written to data/clubs_master.csv")
    print("descriptions:", quality)
    print("matching:", matches)
    print("enriched from five-club files:", ", ".join(c["name"] for c in clubs if c["focus_area"] == "Computing"))
    print("with Rubric link:", sum(bool(c["rubric_url"]) for c in clubs),
          "| with email:", sum(bool(c["email"]) for c in clubs),
          "| with a listed event:", sum(bool(c["event_name"]) for c in clubs))


if __name__ == "__main__":
    main()
