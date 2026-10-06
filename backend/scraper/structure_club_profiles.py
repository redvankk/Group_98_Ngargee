import pandas as pd
import re


INPUT_FILE = "club_profiles_raw.csv"
OUTPUT_FILE = "club_profiles_structured.csv"


def clean(value):
    if pd.isna(value):
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def extract(pattern, text):
    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if match:
        return clean(match.group(1))

    return ""


def parse_record(row):

    text = clean(row.get("raw_text", ""))

    # ----------------------------
    # Club name
    # ----------------------------

    club_name = extract(
        r"Membership Not Found Please contact the club "
        r"for more information\.\s+(.*?)\s+"
        r"RMIT University\s+Overview",
        text
    )

    # Fallback if page wording changes slightly
    if not club_name:

        club_name = extract(
            r"My Cart \(0\).*?"
            r"Membership Not Found.*?information\.\s+"
            r"(.*?)\s+RMIT University\s+Overview",
            text
        )

    # ----------------------------
    # Description
    # ----------------------------

    description = extract(
        r"Committee\s+News\s+Overview\s+"
        r"(.*?)\s+DETAILS\s+University",
        text
    )

    # ----------------------------
    # University
    # ----------------------------

    university = extract(
        r"DETAILS\s+University\s+"
        r"(.*?)\s+Category",
        text
    )

    # ----------------------------
    # Category
    # ----------------------------

    category = extract(
        r"Category\s+(.*?)\s+On Rubric since",
        text
    )

    # ----------------------------
    # Rubric year
    # ----------------------------

    rubric_since = extract(
        r"On Rubric since\s+(\d{4})",
        text
    )

    # ----------------------------
    # Existing scraped links
    # ----------------------------

    instagram = clean(row.get("instagram", ""))
    facebook = clean(row.get("facebook", ""))
    discord = clean(row.get("discord", ""))
    linkedin = clean(row.get("linkedin", ""))
    emails = clean(row.get("emails", ""))
    external_links = clean(row.get("external_links", ""))

    # ----------------------------
    # Search-friendly text
    # ----------------------------

    search_text = clean(
        f"""
        Club: {club_name}
        Category: {category}
        Description: {description}
        """
    )

    return {
        "club_name": club_name,
        "description": description,
        "category": category,
        "university": university,
        "rubric_since": rubric_since,

        "emails": emails,

        "instagram": instagram,
        "facebook": facebook,
        "discord": discord,
        "linkedin": linkedin,

        "external_links": external_links,

        "source_url": clean(
            row.get("source_url", "")
        ),

        "last_scraped_utc": clean(
            row.get("last_scraped_utc", "")
        ),

        "search_text": search_text
    }


def main():

    df = pd.read_csv(INPUT_FILE)

    print(f"Loaded {len(df)} raw records")

    structured_records = []

    for _, row in df.iterrows():
        structured_records.append(
            parse_record(row)
        )

    result = pd.DataFrame(structured_records)

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8"
    )

    print()
    print("=" * 70)

    print(
        "Records:",
        len(result)
    )

    print(
        "Club names found:",
        (result["club_name"] != "").sum()
    )

    print(
        "Descriptions found:",
        (result["description"] != "").sum()
    )

    print(
        "Categories found:",
        (result["category"] != "").sum()
    )

    print(
        "Instagram links:",
        (result["instagram"] != "").sum()
    )

    print(
        "Discord links:",
        (result["discord"] != "").sum()
    )

    print()
    print(
        f"Saved → {OUTPUT_FILE}"
    )

    print("=" * 70)

    print("\nSAMPLE RECORDS:\n")

    print(
        result[
            [
                "club_name",
                "category",
                "description"
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()


