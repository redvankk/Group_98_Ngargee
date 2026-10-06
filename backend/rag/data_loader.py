from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

PLACEHOLDERS = {
    "", "-", "—", "–", "n/a", "na", "none", "nil", "not available",
    "not listed", "not publicly listed", "not specified", "none listed",
    "no upcoming events listed", "date not provided",
}

NAME_FIXES = {
    "International Studies Associaiton": "International Studies Association",
    "Pspchology Student Society": "Psychology Student Society",
    "RMIT Engineers Austrila Student Society": "RMIT Engineers Australia Student Society",
    "Women in Built Envirnoments": "Women in Built Environments",
    "Laboratory Medicine association": "Laboratory Medicine Association",
    "Student Osteopathic Medicine association": "Student Osteopathic Medicine Association",
}

CATEGORY_FIXES = {
    "Academic and Professional": "Academic & Professional",
    "Social and Special Interest": "Social & Special Interest",
    "Cultural and International": "Cultural & International",
}

SAFE_COLUMNS = [
    "Club Name",
    "Category",
    "Description",
    "Who Can Join",
    "Campus",
    "Club Email",
    "Contact Person / Committee",
    "Instagram",
    "Facebook",
    "LinkedIn",
    "Website",
    "Rubric Club Page",
    "Membership / Join Link",
    "Events Page",
]


def clean_value(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if text.casefold() in PLACEHOLDERS:
        return ""
    return text


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug or "club"


def first_url(*values: str) -> str:
    for value in values:
        value = clean_value(value)
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return ""


MASTER_FIELDS = [
    "club_id", "name", "category", "tags", "description", "description_quality",
    "who_can_join", "campus", "email", "instagram", "facebook", "discord", "linkedin",
    "website", "join_url", "rubric_url", "events_url", "event_name", "event_date",
    "event_location", "event_type", "event_frequency", "notes", "events_checked",
    "sources", "last_checked", "acronym", "also_known_as", "focus_area", "membership_full",
    "membership_associate", "membership_social", "membership_under_18", "linktree", "committee",
]


def load_master(csv_path: Path) -> list[dict]:
    """Read data/clubs_master.csv (built by data/build_dataset.py)."""
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str).fillna("")
    clubs = []
    for _, row in df.iterrows():
        club = {f: clean_value(row.get(f, "")) for f in MASTER_FIELDS}
        if not club["name"]:
            continue
        if club["description_quality"] != "full":
            club["description"] = ""  # a Rubric greeting tells retrieval nothing
        club["id"] = club.pop("club_id") or slugify(club["name"])
        club["membership"] = club.pop("who_can_join")
        club["url"] = first_url(club["rubric_url"], club["website"], club["join_url"], club["instagram"])
        clubs.append(club)
    return clubs


def load_clubs(csv_path: Path) -> list[dict]:
    """Load clubs from the tidy master file, or the original team spreadsheet."""
    header = Path(csv_path).read_bytes()[:400].decode("utf-8", errors="ignore")
    if "club_id" in header:
        return load_master(csv_path)
    return load_legacy(csv_path)


def load_legacy(csv_path: Path) -> list[dict]:
    # This source file was exported in Windows-1252. utf-8-sig is attempted first
    # so a future clean export works without changing this loader.
    last_error = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        raise last_error  # type: ignore[misc]

    # Keep the stable portion of the spreadsheet schema. The original export has
    # several unnamed trailing columns caused by sheet formatting / shifted event
    # fields; those are deliberately excluded from the first integration test.
    available = [c for c in SAFE_COLUMNS if c in df.columns]
    df = df[available].copy()

    # Drop spreadsheet padding and the final legend row.
    df["Club Name"] = df["Club Name"].map(clean_value)
    df = df[df["Club Name"] != ""]
    df = df[~df["Club Name"].str.casefold().str.startswith("legend:")]

    clubs: list[dict] = []
    seen_ids: set[str] = set()

    for _, row in df.iterrows():
        raw_name = clean_value(row.get("Club Name", ""))
        name = NAME_FIXES.get(raw_name, raw_name).strip()
        category = clean_value(row.get("Category", ""))
        category = CATEGORY_FIXES.get(category, category) or "Uncategorised"
        description = clean_value(row.get("Description", ""))
        membership = clean_value(row.get("Who Can Join", ""))
        campus = clean_value(row.get("Campus", ""))
        email = clean_value(row.get("Club Email", ""))
        committee = clean_value(row.get("Contact Person / Committee", ""))
        instagram = clean_value(row.get("Instagram", ""))
        facebook = clean_value(row.get("Facebook", ""))
        linkedin = clean_value(row.get("LinkedIn", ""))
        website = clean_value(row.get("Website", ""))
        rubric = clean_value(row.get("Rubric Club Page", ""))
        join_link = clean_value(row.get("Membership / Join Link", ""))
        events_page = clean_value(row.get("Events Page", ""))

        club_id = slugify(name)
        base_id = club_id
        suffix = 2
        while club_id in seen_ids:
            club_id = f"{base_id}-{suffix}"
            suffix += 1
        seen_ids.add(club_id)

        url = first_url(rubric, website, join_link, instagram, facebook, linkedin, events_page)

        clubs.append(
            {
                "id": club_id,
                "name": name,
                "category": category,
                "description": description,
                "membership": membership,
                "campus": campus,
                "email": email,
                "committee": committee,
                "instagram": instagram,
                "facebook": facebook,
                "linkedin": linkedin,
                "website": website,
                "rubric_url": rubric,
                "join_url": join_link,
                "events_url": events_page,
                "url": url,
            }
        )

    return clubs
