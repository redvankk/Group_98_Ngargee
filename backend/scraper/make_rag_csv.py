import pandas as pd
import re
from pathlib import Path


INPUT_FILE = "club_profiles_structured.csv"
OUTPUT_FILE = "../data/Clubs_scraped.csv"


def clean(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def slugify(text):
    text = clean(text).lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text
    )

    return text.strip("-")


def first_useful_website(external_links):

    if pd.isna(external_links):
        return ""

    links = [
        x.strip()
        for x in str(external_links).split("|")
        if x.strip()
    ]

    social_domains = [
        "instagram.com",
        "facebook.com",
        "linkedin.com",
        "discord.gg",
        "discord.com",
        "hellorubric.com"
    ]

    for link in links:

        if not any(
            domain in link.lower()
            for domain in social_domains
        ):
            return link

    return ""


def main():

    df = pd.read_csv(INPUT_FILE)

    records = []

    for _, row in df.iterrows():

        club_name = clean(
            row.get("club_name", "")
        )

        record = {

            "id":
                slugify(club_name),

            "name":
                club_name,

            "category":
                clean(row.get("category", "")),

            "description":
                clean(row.get("description", "")),

            "membership":
                "",

            "campus":
                clean(row.get("university", "")),

            "email":
                clean(row.get("emails", "")),

            "committee":
                "",

            "instagram":
                clean(row.get("instagram", "")),

            "facebook":
                clean(row.get("facebook", "")),

            "linkedin":
                clean(row.get("linkedin", "")),

            "website":
                first_useful_website(
                    row.get("external_links", "")
                ),

            "rubric_url":
                clean(row.get("source_url", "")),

            "join_url":
                "",

            "events_url":
                "",

            "url":
                clean(row.get("source_url", ""))
        }

        records.append(record)

    result = pd.DataFrame(records)

    output = Path(OUTPUT_FILE)

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        output,
        index=False,
        encoding="utf-8"
    )

    print("=" * 70)

    print(
        f"Created {len(result)} RAG-ready club records"
    )

    print(
        f"Saved → {output}"
    )

    print("=" * 70)

    print("\nSAMPLE:\n")

    print(
        result[
            [
                "id",
                "name",
                "category",
                "description",
                "url"
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()


