from playwright.sync_api import sync_playwright
import csv
import time
import re
from datetime import datetime, timezone


INPUT_FILE = "club_links.csv"
OUTPUT_FILE = "club_profiles_raw.csv"


def clean_text(text: str) -> str:
    """Remove excessive whitespace."""
    return re.sub(r"\s+", " ", text or "").strip()


def extract_emails(text: str):
    """Find email addresses in visible text."""
    pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    return sorted(set(re.findall(pattern, text)))


def main():

    # Load club URLs
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        club_urls = [
            row["club_profile_url"]
            for row in reader
            if row.get("club_profile_url")
        ]

    print(f"Loaded {len(club_urls)} club URLs.")

    records = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}
        )

        for index, url in enumerate(club_urls, 1):

            print()
            print("=" * 70)
            print(f"[{index}/{len(club_urls)}]")
            print(url)

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=90000
                )

                # Allow dynamic content to load
                page.wait_for_timeout(2500)

                # Scroll a little in case sections lazy-load
                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(1000)

                # Page title
                title = clean_text(page.title())

                # All visible text
                body_text = clean_text(
                    page.locator("body").inner_text()
                )

                # Extract links
                links = []

                anchors = page.locator("a[href]")

                for i in range(anchors.count()):

                    href = anchors.nth(i).get_attribute("href")

                    if href:
                        links.append(href)

                links = sorted(set(links))

                # Extract email addresses
                emails = extract_emails(body_text)

                # Also collect mailto links
                for link in links:

                    if link.startswith("mailto:"):

                        email = (
                            link
                            .replace("mailto:", "")
                            .split("?")[0]
                        )

                        emails.append(email)

                emails = sorted(set(emails))

                # Social / useful URLs
                instagram = [
                    x for x in links
                    if "instagram.com" in x.lower()
                ]

                facebook = [
                    x for x in links
                    if "facebook.com" in x.lower()
                ]

                discord = [
                    x for x in links
                    if "discord" in x.lower()
                ]

                linkedin = [
                    x for x in links
                    if "linkedin.com" in x.lower()
                ]

                external_links = [
                    x for x in links
                    if x.startswith("http")
                    and "hellorubric.com" not in x
                ]

                record = {
                    "source_url": url,
                    "page_title": title,

                    "emails": " | ".join(emails),

                    "instagram": " | ".join(
                        sorted(set(instagram))
                    ),

                    "facebook": " | ".join(
                        sorted(set(facebook))
                    ),

                    "discord": " | ".join(
                        sorted(set(discord))
                    ),

                    "linkedin": " | ".join(
                        sorted(set(linkedin))
                    ),

                    "external_links": " | ".join(
                        sorted(set(external_links))
                    ),

                    "raw_text": body_text,

                    "last_scraped_utc":
                        datetime.now(timezone.utc).isoformat()
                }

                records.append(record)

                print(
                    f"✓ scraped "
                    f"{len(body_text)} characters, "
                    f"{len(emails)} email(s), "
                    f"{len(external_links)} external link(s)"
                )

            except Exception as e:

                print("✗ ERROR:", e)

                records.append({
                    "source_url": url,
                    "page_title": "",
                    "emails": "",
                    "instagram": "",
                    "facebook": "",
                    "discord": "",
                    "linkedin": "",
                    "external_links": "",
                    "raw_text": "",
                    "last_scraped_utc":
                        datetime.now(timezone.utc).isoformat()
                })

            # Be polite to the site
            time.sleep(1.5)

        browser.close()

    # Save CSV
    fieldnames = [
        "source_url",
        "page_title",
        "emails",
        "instagram",
        "facebook",
        "discord",
        "linkedin",
        "external_links",
        "raw_text",
        "last_scraped_utc"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(records)

    print()
    print("=" * 70)
    print(f"DONE — saved {len(records)} records")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()


