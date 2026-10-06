from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
import csv
import re

START_URL = (
    "https://campus.hellorubric.com/search?"
    "country=AU&iframe=true&showall=true&"
    "state=Victoria&type=societies&universityid=17"
)

OUTPUT_FILE = "club_links.csv"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}
        )

        print("Opening RMIT/RUSU club catalogue...")

        page.goto(
            START_URL,
            wait_until="domcontentloaded",
            timeout=120000,
        )

        page.wait_for_timeout(5000)

        # Try loading all results.
        for _ in range(30):
            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(1000)

            try:
                button = page.get_by_role(
                    "button",
                    name=re.compile("load more", re.I),
                )

                if button.count() > 0 and button.first.is_visible():
                    print("Loading more clubs...")
                    button.first.click()
                    page.wait_for_timeout(1500)
                else:
                    break

            except Exception:
                break

        # Collect links from rendered page.
        links = set()

        anchors = page.locator("a[href]")

        for i in range(anchors.count()):
            href = anchors.nth(i).get_attribute("href")

            if not href:
                continue

            absolute = urljoin(
                "https://campus.hellorubric.com/",
                href
            )

            # Rubric club profiles commonly use ?s=<id>
            if (
                "campus.hellorubric.com" in absolute
                and re.search(r"[?&]s=\d+", absolute)
            ):
                links.add(absolute)

        links = sorted(links)

        print()
        print("=" * 60)
        print(f"Found {len(links)} possible club profiles")
        print("=" * 60)

        for link in links:
            print(link)

        with open(
            OUTPUT_FILE,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.writer(f)

            writer.writerow([
                "club_profile_url"
            ])

            for link in links:
                writer.writerow([link])

        print()
        print(
            f"Saved links to {OUTPUT_FILE}"
        )

        input(
            "\nPress ENTER to close the browser..."
        )

        browser.close()


if __name__ == "__main__":
    main()

