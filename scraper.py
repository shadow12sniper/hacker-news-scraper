#!/usr/bin/env python3
"""
Production-ready Hacker News scraper.
Extracts article data (Title, Link, Points, Comments) from the first two pages.
Writes the results to scraped_leads.json with 4-space indentation.
"""

import json
import sys
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

# Constants
BASE_URL = "https://news.ycombinator.com/"
PAGES_TO_SCRAPE = 2
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)
OUTPUT_FILE = "scraped_leads.json"


def fetch_page(page_num: int) -> Optional[BeautifulSoup]:
    """
    Fetch a single Hacker News page and return a BeautifulSoup object.
    Returns None if the request fails.
    """
    if page_num == 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}?p={page_num}"

    headers = {"User-Agent": USER_AGENT}

    try:
        print(f"[INFO] Fetching page {page_num}: {url}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        # Ensure we parse with the correct encoding
        soup = BeautifulSoup(response.text, "html.parser")
        print(f"[INFO] Successfully fetched page {page_num} (status {response.status_code})")
        return soup
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch page {page_num}: {e}", file=sys.stderr)
        return None


def parse_article(row) -> Optional[Dict[str, str]]:
    """
    Parse a single article row (<tr class="athing">) and its following subtext row.
    Returns a dictionary with keys: title, link, points, comments.
    Returns None if the title cannot be extracted (critical field).
    """
    # 1. Extract title and link from the titleline span
    titleline = row.find("span", class_="titleline")
    if not titleline:
        # No titleline found – skip this row entirely
        return None

    link_tag = titleline.find("a")
    if not link_tag:
        # No anchor tag – skip
        return None

    title = link_tag.get_text(strip=True)
    link = link_tag.get("href")
    if not link:
        # Fallback: if href missing, set to empty string
        link = ""

    # 2. Find the subtext row (the next sibling with class 'subtext')
    subtext = row.find_next_sibling("tr")
    if not subtext or "subtext" not in subtext.get("class", []):
        # If no subtext row, we still return title/link with default points/comments
        points = 0
        comments = 0
    else:
        # Extract points
        score_span = subtext.find("span", class_="score")
        if score_span:
            score_text = score_span.get_text(strip=True)
            # score_text like "123 points" or "1 point"
            # Try to parse integer
            try:
                points = int(score_text.split()[0])
            except (ValueError, IndexError):
                points = 0
        else:
            points = 0

        # Extract comments count
        # The link to comments usually has text like "123 comments" or "discuss"
        comments_anchor = subtext.find("a", string=lambda t: t and ("comment" in t or "discuss" in t))
        if comments_anchor:
            comments_text = comments_anchor.get_text(strip=True)
            if comments_text == "discuss":
                comments = 0
            else:
                try:
                    comments = int(comments_text.split()[0])
                except (ValueError, IndexError):
                    comments = 0
        else:
            # Look for any 'a' with href containing 'item?id='
            # Sometimes "comments" link is the last anchor in subtext
            all_links = subtext.find_all("a")
            if all_links:
                # Usually the last link is the comments link
                last_link = all_links[-1]
                if last_link.get("href", "").startswith("item?id="):
                    comments_text = last_link.get_text(strip=True)
                    if comments_text == "discuss":
                        comments = 0
                    else:
                        try:
                            comments = int(comments_text.split()[0])
                        except (ValueError, IndexError):
                            comments = 0
                else:
                    comments = 0
            else:
                comments = 0

    return {
        "title": title,
        "link": link,
        "points": points,
        "comments": comments,
    }


def scrape_page(page_num: int) -> List[Dict[str, str]]:
    """
    Scrape a single page and return a list of article dictionaries.
    """
    soup = fetch_page(page_num)
    if soup is None:
        return []

    rows = soup.find_all("tr", class_="athing")
    if not rows:
        print(f"[WARN] No article rows found on page {page_num}")
        return []

    articles = []
    for row in rows:
        try:
            article = parse_article(row)
            if article is not None:
                articles.append(article)
        except Exception as e:
            # Catch any unforeseen parsing errors to keep the script running
            print(f"[WARN] Error parsing row: {e}", file=sys.stderr)
            continue

    print(f"[INFO] Parsed {len(articles)} articles from page {page_num}")
    return articles


def main():
    """Main entry point."""
    print("[INFO] Starting Hacker News scraper...")
    start_time = time.time()

    all_articles: List[Dict[str, str]] = []

    for page in range(1, PAGES_TO_SCRAPE + 1):
        articles = scrape_page(page)
        all_articles.extend(articles)
        # Be polite – slight delay between requests
        if page < PAGES_TO_SCRAPE:
            time.sleep(1)

    print(f"[INFO] Total articles collected: {len(all_articles)}")

    # Write to JSON file
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_articles, f, indent=4, ensure_ascii=False)
        print(f"[INFO] Successfully wrote data to {OUTPUT_FILE}")
    except IOError as e:
        print(f"[ERROR] Could not write to {OUTPUT_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"[INFO] Scraping completed in {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()