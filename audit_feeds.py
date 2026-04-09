#!/usr/bin/env python3
"""
audit_feeds.py — Full RSS volume audit: scrape → translate → filter (no GPT).

Live counters show progress for each stage.

Outputs (saved to data/audit/):
  YYYY-MM-DD_HH-MM_all_articles.json      — every successfully scraped article
  YYYY-MM-DD_HH-MM_filtered_articles.json — articles that passed the intl filter
  YYYY-MM-DD_HH-MM_summary.txt            — human-readable stats

Usage:
  python3 audit_feeds.py                     # 1-day window, with translation
  python3 audit_feeds.py --days 2            # 2-day window
  python3 audit_feeds.py --no-translate      # skip translation (faster, less accurate filter)
"""

import json
import logging
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Suppress noisy library output — we handle our own progress display
logging.basicConfig(level=logging.WARNING)
logging.getLogger("newspaper").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

OUTPUT_DIR = Path(__file__).parent / "data" / "audit"


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def progress(line: str) -> None:
    """Overwrite the current terminal line."""
    print(f"\r  {line:<75}", end="", flush=True)


def done(line: str) -> None:
    """Print a completed-stage line (newline included)."""
    print(f"\r  {line:<75}")


# ── Stage 1: Scrape ───────────────────────────────────────────────────────────

def scrape_all_feeds(scraper, days: int):
    from src.data.scraper import NewsScraper  # noqa — already imported via scraper arg

    feeds = scraper.rss_feeds
    total_feeds = len(feeds)
    cutoff = datetime.now() - timedelta(days=days)
    seen_urls: set = set()
    all_articles = []
    start = time.time()

    for i, feed_info in enumerate(feeds, 1):
        feed_url = feed_info["url"] if isinstance(feed_info, dict) else feed_info
        source_country = feed_info.get("country", "") if isinstance(feed_info, dict) else ""
        host = feed_url.split("/")[2] if "//" in feed_url else feed_url[:35]

        bar_filled = int(28 * i / total_feeds)
        bar = "█" * bar_filled + "░" * (28 - bar_filled)
        progress(
            f"[{bar}] Feed {i:>3}/{total_feeds}  |  "
            f"Articles: {len(all_articles):>4}  |  {fmt_elapsed(time.time() - start)}"
        )

        try:
            batch = scraper._parse_feed(feed_url, cutoff, seen_urls, source_country)
            all_articles.extend(batch)
        except Exception:
            pass

        if i < total_feeds:
            time.sleep(random.uniform(0.5, 1.5))

    elapsed = time.time() - start
    done(f"Scraped {len(all_articles)} articles from {total_feeds} feeds  |  {fmt_elapsed(elapsed)}")
    return all_articles, elapsed


# ── Stage 2: Translate ────────────────────────────────────────────────────────

def translate_articles(articles: list):
    try:
        from src.utils.translator import get_translator
        translator = get_translator()
    except Exception as e:
        print(f"  ⚠  Translation unavailable ({e}) — running filter on original text.")
        for a in articles:
            a.setdefault("language_detected", "unknown")
            a["was_translated"] = False
        return articles, 0.0

    start = time.time()
    total = len(articles)

    for j, a in enumerate(articles, 1):
        progress(
            f"Article {j:>4}/{total}  |  {fmt_elapsed(time.time() - start)}  |  "
            f"lang: {a.get('language_detected', '?'):<6}"
        )
        try:
            tr = translator.translate(
                text=a.get("article_text", ""),
                title=a.get("headline", ""),
            )
            a["article_text"] = tr["translated_text"]
            a["headline"] = tr["translated_title"]
            a["language_detected"] = tr["language_detected"]
            a["was_translated"] = tr["was_translated"]
        except Exception:
            a.setdefault("language_detected", "unknown")
            a["was_translated"] = False

    elapsed = time.time() - start
    done(f"Translated {total} articles  |  {fmt_elapsed(elapsed)}")
    return articles, elapsed


# ── Stage 3: Filter ───────────────────────────────────────────────────────────

def filter_articles(articles: list):
    from src.utils.intl_filter import passes_international_filter

    passed, failed = [], []
    start = time.time()
    total = len(articles)

    for j, a in enumerate(articles, 1):
        progress(
            f"Article {j:>4}/{total}  |  "
            f"Pass: {len(passed):>4}  Fail: {len(failed):>4}  |  "
            f"{fmt_elapsed(time.time() - start)}"
        )
        ok, details = passes_international_filter(
            text=a.get("article_text", ""),
            title=a.get("headline", ""),
        )
        a["_filter"] = {
            "passed": ok,
            "keywords_found": details.get("keywords_found", []),
            "countries_found": details.get("countries_found", []),
            "orgs_found": details.get("orgs_found", []),
            "keyword_pass": details.get("keyword_pass", False),
            "country_pass": details.get("country_pass", False),
        }
        (passed if ok else failed).append(a)

    elapsed = time.time() - start
    pass_rate = len(passed) / total * 100 if total else 0
    done(
        f"Filter done  |  Pass: {len(passed)} ({pass_rate:.1f}%)  "
        f"Fail: {len(failed)} ({100 - pass_rate:.1f}%)  |  {fmt_elapsed(elapsed)}"
    )
    return passed, failed, elapsed


# ── Main ──────────────────────────────────────────────────────────────────────

def run_audit(days: int = 1, skip_translation: bool = False):
    from src.data.scraper import NewsScraper

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 70)
    print(f"  RSS FEED AUDIT  |  {days}-day window  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    scraper = NewsScraper()
    total_feeds = len(scraper.rss_feeds)

    # ── 1. Scrape ─────────────────────────────────────────────────────────────
    print(f"\n[1/3] SCRAPING  ({total_feeds} feeds, last {days} day(s))\n")
    all_articles, elapsed_scrape = scrape_all_feeds(scraper, days)

    if not all_articles:
        print("\n  No articles found. Try increasing --days.")
        return

    # Save all_articles immediately after scraping
    all_path = OUTPUT_DIR / f"{date_str}_all_articles.json"
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  → Saved: {all_path}")

    # ── 2. Translate ──────────────────────────────────────────────────────────
    if skip_translation:
        print(f"\n[2/3] TRANSLATING  (skipped — filter will run on original text)\n")
        for a in all_articles:
            a.setdefault("language_detected", "")
            a["was_translated"] = False
        elapsed_translate = 0.0
    else:
        print(f"\n[2/3] TRANSLATING  ({len(all_articles)} articles)\n")
        all_articles, elapsed_translate = translate_articles(all_articles)

    # ── 3. Filter ─────────────────────────────────────────────────────────────
    print(f"\n[3/3] FILTERING  ({len(all_articles)} articles)\n")
    passed, failed, elapsed_filter = filter_articles(all_articles)

    total_elapsed = elapsed_scrape + elapsed_translate + elapsed_filter

    # ── 4. Save files ─────────────────────────────────────────────────────────
    # all_articles already saved right after scraping — overwrite with translated text
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2, default=str)

    filtered_path = OUTPUT_DIR / f"{date_str}_filtered_articles.json"
    summary_path = OUTPUT_DIR / f"{date_str}_summary.txt"

    with open(filtered_path, "w", encoding="utf-8") as f:
        json.dump(passed, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  → Saved: {filtered_path}")

    # Country breakdown (top 15 by article count, from passed set)
    country_counts: dict = {}
    for a in passed:
        c = a.get("source_country") or "Unknown"
        country_counts[c] = country_counts.get(c, 0) + 1
    top_countries = sorted(country_counts.items(), key=lambda x: -x[1])[:15]

    pass_rate = len(passed) / len(all_articles) * 100 if all_articles else 0

    summary_lines = [
        f"RSS Feed Audit",
        f"Run date    : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Days window : {days}",
        f"Total feeds : {total_feeds}",
        f"Translation : {'skipped' if skip_translation else 'enabled'}",
        "",
        f"TIMING",
        f"  Scraping    : {fmt_elapsed(elapsed_scrape)}",
        f"  Translation : {fmt_elapsed(elapsed_translate)}",
        f"  Filtering   : {fmt_elapsed(elapsed_filter)}",
        f"  Total       : {fmt_elapsed(total_elapsed)}",
        "",
        f"VOLUME",
        f"  Total scraped : {len(all_articles)}",
        f"  Passed filter : {len(passed)}  ({pass_rate:.1f}%)",
        f"  Discarded     : {len(failed)}  ({100 - pass_rate:.1f}%)",
        "",
        f"TOP SOURCE COUNTRIES (filtered set)",
    ]
    for country, count in top_countries:
        summary_lines.append(f"  {country:<30} {count:>4} articles")

    summary_lines += [
        "",
        f"FILES SAVED",
        f"  All articles : {all_path}",
        f"  Filtered     : {filtered_path}",
        f"  Summary      : {summary_path}",
    ]

    summary_text = "\n".join(summary_lines)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    # ── 5. Print summary ──────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print(summary_text)
    print("=" * 70)
    print()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Audit all RSS feeds (no GPT)")
    p.add_argument("--days", "-d", type=int, default=1, help="Days to look back (default: 1)")
    p.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip MarianMT translation (faster but filter is less accurate for non-English feeds)",
    )
    args = p.parse_args()
    run_audit(days=args.days, skip_translation=args.no_translate)
