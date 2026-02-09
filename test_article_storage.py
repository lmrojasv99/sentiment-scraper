#!/usr/bin/env python3
"""
Local test: scrape → translate → filter → store articles (no GPT).
Verifies that articles are stored with translated text, language_detected, source_country.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime

from config.settings import get_settings
from src.data.database import (
    init_db,
    set_db_path,
    set_database_url,
    insert_article,
    get_db_connection,
    _execute_query,
    _row_to_dict,
)
from src.data.scraper import NewsScraper
from src.utils.intl_filter import passes_international_filter


def run_test(max_feeds=1, max_articles=3):
    """Scrape a few articles, translate (if available), filter, store, then show DB."""
    print("\n" + "=" * 60)
    print("LOCAL TEST: Article storage (scrape → translate → filter → store)")
    print("=" * 60)

    settings = get_settings()
    if settings.database_url:
        set_database_url(settings.database_url)
        print("Using PostgreSQL")
    else:
        set_db_path(settings.db_path)
        print(f"Using SQLite: {settings.db_path}")
    init_db(reset=False)

    # 1) Scrape: use only first N feeds to keep it fast
    scraper = NewsScraper()
    original_feeds = scraper.rss_feeds
    scraper.rss_feeds = original_feeds[:max_feeds]
    print(f"\n1. Scraping (first {max_feeds} feed(s), last 1 day)...")
    articles, _ = scraper.scrape_articles(days=1)
    articles = articles[:max_articles]
    print(f"   Got {len(articles)} article(s)")

    if not articles:
        print("   No articles found. Try increasing days or using more feeds.")
        return

    # 2) Translate (optional – skip if heavy deps not installed)
    try:
        from src.utils.translator import get_translator
        translator = get_translator()
        print("\n2. Translating to English...")
        for a in articles:
            tr = translator.translate(
                text=a.get("article_text", ""),
                title=a.get("headline", ""),
            )
            a["article_text"] = tr["translated_text"]
            a["headline"] = tr["translated_title"]
            a["language_detected"] = tr["language_detected"]
            print(f"   - {a.get('headline', '')[:50]}... → lang={tr['language_detected']}, translated={tr['was_translated']}")
    except Exception as e:
        print(f"\n2. Skipping translation ({e}). Using original text, language_detected=''.")
        for a in articles:
            a["language_detected"] = ""

    # 3) Filter
    print("\n3. Applying international-context filter...")
    filtered = []
    for a in articles:
        passes, details = passes_international_filter(
            text=a.get("article_text", ""),
            title=a.get("headline", ""),
        )
        if passes:
            filtered.append(a)
            print(f"   PASS: {a.get('headline', '')[:50]}... (keywords={len(details['keywords_found'])}, countries={details['countries_found']})")
        else:
            print(f"   FAIL: {a.get('headline', '')[:50]}... (keywords_ok={details['keyword_pass']}, countries_ok={details['country_pass']})")
    print(f"   → {len(filtered)} article(s) passed")

    # 4) Store only passers (no GPT)
    print("\n4. Storing passed articles in DB...")
    inserted_ids = []
    for a in filtered:
        article_data = {
            "news_title": a.get("headline", ""),
            "news_text": a.get("article_text", ""),
            "publication_date": a.get("published_date", a.get("publication_date", "")),
            "source_url": a.get("source_url", ""),
            "source_domain": a.get("source", ""),
            "source_country": a.get("source_country", ""),
            "language": "en",
            "language_detected": a.get("language_detected", ""),
        }
        news_id = insert_article(article_data)
        if news_id:
            inserted_ids.append(news_id)
            print(f"   Stored news_id={news_id}: {a.get('headline', '')[:50]}...")
        else:
            print(f"   Duplicate (skipped): {a.get('source_url', '')[:50]}...")

    # 5) Show what's in the DB
    print("\n5. Articles in database (recent):")
    with get_db_connection() as conn:
        cursor = _execute_query(
            conn,
            "SELECT news_id, news_title, source_country, language_detected, "
            "LENGTH(news_text) as text_len, publication_date FROM articles ORDER BY news_id DESC LIMIT 10"
        )
        rows = cursor.fetchall()
    for row in rows:
        r = _row_to_dict(row, cursor)
        rid = r.get("news_id")
        title = (r.get("news_title") or "")[:55]
        country = r.get("source_country") or "(none)"
        lang = r.get("language_detected") or "(none)"
        length = r.get("text_len") or 0
        pub = r.get("publication_date") or ""
        print(f"   [{rid}] {title}...")
        print(f"        source_country={country} | language_detected={lang} | text_len={length} | pub={pub[:10] if pub else ''}")

    print("\n" + "=" * 60)
    print("Done. Stored article fields: news_title, news_text, source_country, language_detected, etc.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Test article storage (no GPT)")
    p.add_argument("--feeds", type=int, default=1, help="Number of RSS feeds to scrape (default 1)")
    p.add_argument("--articles", type=int, default=3, help="Max articles to process (default 3)")
    args = p.parse_args()
    run_test(max_feeds=args.feeds, max_articles=args.articles)
