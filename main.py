#!/usr/bin/env python3
"""
Global International Relations Monitor v2.0
Main Entry Point - Pipeline Orchestrator

Coordinates the full pipeline for:
1. Fetching articles from RSS feeds
2. Filtering for international relevance
3. Extracting multiple events per article using GPT-4o
4. Storing articles and events in the database
5. Generating statistics and reports
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from config.settings import get_settings, Settings
from src.data.database import init_db, get_statistics, set_db_path
from src.data.scraper import NewsScraper
from src.core.analyzer import EventAnalyzer
from src.core.event_extractor import EventExtractor, BatchExtractor, ExtractionResult

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GeopoliticalAgent")


def print_banner():
    """Print startup banner."""
    print("\n" + "=" * 70)
    print("🌎 GLOBAL INTERNATIONAL RELATIONS MONITOR v2.0")
    print("    Plover-Based Multi-Event Extraction Pipeline")
    print("    Powered by GPT-4o")
    print("=" * 70 + "\n")


def progress_callback(current: int, total: int, article: Dict[str, Any]):
    """Progress callback for batch processing."""
    title = article.get('headline', article.get('news_title', 'Unknown'))[:50]
    logger.info(f"[{current}/{total}] Processing: {title}...")


def print_event_summary(result: ExtractionResult):
    """Print summary for a single extraction result."""
    if result.is_duplicate:
        logger.info(f"  ⏭️  Duplicate article, skipped")
        return
    
    if result.errors:
        for error in result.errors:
            logger.warning(f"  ⚠️  {error}")
    
    if result.events:
        logger.info(f"  📊 Extracted {result.event_count} events:")
        for event in result.events:
            emoji = "🟢" if event.sentiment >= 3 else "🔴" if event.sentiment <= -3 else "⚪"
            logger.info(f"    {emoji} {event.dimension}/{event.sub_dimension}: "
                       f"sentiment={event.sentiment:+.0f}")
    else:
        logger.info(f"  ℹ️  No international events extracted")


def print_final_summary(results: List[ExtractionResult], stats: Dict[str, Any]):
    """Print final processing summary."""
    print("\n" + "=" * 70)
    print("📊 PROCESSING SUMMARY")
    print("=" * 70)
    
    total_articles = len(results)
    duplicates = sum(1 for r in results if r.is_duplicate)
    processed = total_articles - duplicates
    total_events = sum(r.event_count for r in results if not r.is_duplicate)
    
    print(f"\n📰 Articles:")
    print(f"   Total fetched:     {total_articles}")
    print(f"   Processed (new):   {processed}")
    print(f"   Skipped (dupe):    {duplicates}")
    
    print(f"\n🎯 Events:")
    print(f"   Total extracted:   {total_events}")
    if processed > 0:
        print(f"   Avg per article:   {total_events/processed:.1f}")
    
    # Dimension breakdown
    dimension_counts = {}
    sentiment_sum = 0
    sentiment_count = 0
    
    for result in results:
        for event in result.events:
            dim = event.dimension
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1
            sentiment_sum += event.sentiment
            sentiment_count += 1
    
    if dimension_counts:
        print(f"\n📁 Events by Dimension:")
        for dim, count in sorted(dimension_counts.items(), key=lambda x: -x[1]):
            print(f"   {dim}: {count}")
    
    if sentiment_count > 0:
        avg_sentiment = sentiment_sum / sentiment_count
        print(f"\n📈 Sentiment:")
        print(f"   Average score:     {avg_sentiment:+.1f} (scale: -10 to +10)")
    
    print(f"\n💾 Database Statistics:")
    print(f"   Total articles:    {stats.get('total_articles', 0)}")
    print(f"   Total events:      {stats.get('total_events', 0)}")
    
    print("\n" + "=" * 70)


def main(
    days: int = 5,
    batch_size: int = 10,
    delay_between: float = 1.5,
    model: str = "gpt-4o",
    reset_db: bool = False
):
    """Main pipeline execution."""
    print_banner()
    
    settings = get_settings()
    
    # Check API key
    if not settings.is_api_configured:
        logger.error("❌ OPENAI_API_KEY not configured!")
        print("\nPlease set your OpenAI API key in .env file")
        return
    
    logger.info("Starting Global International Relations Monitor v2.0")
    start_time = datetime.now()
    
    # Initialize Database
    logger.info("📁 Initializing database...")
    set_db_path(settings.db_path)
    init_db(reset=reset_db)
    
    # Initialize Components
    logger.info(f"🤖 Initializing analyzer with {model}...")
    analyzer = EventAnalyzer(model=model)
    extractor = EventExtractor(analyzer=analyzer)
    batch_processor = BatchExtractor(
        extractor=extractor,
        batch_size=batch_size,
        delay_between=delay_between
    )
    
    scraper = NewsScraper()
    
    # Scrape Articles
    logger.info(f"📰 Scraping news articles (last {days} days)...")
    articles = scraper.scrape_articles(days=days)
    logger.info(f"Found {len(articles)} relevant articles")
    
    if not articles:
        logger.warning("No articles found.")
        return
    
    # Process articles
    logger.info(f"\n🔍 Extracting international events...")
    results = batch_processor.process_articles(
        articles=articles,
        progress_callback=progress_callback
    )
    
    # Print summaries
    for i, (article, result) in enumerate(zip(articles, results)):
        title = article.get('headline', article.get('news_title', 'Unknown'))[:60]
        logger.info(f"\n[{i+1}] {title}")
        print_event_summary(result)
    
    # Final statistics
    stats = get_statistics()
    print_final_summary(results, stats)
    
    elapsed = datetime.now() - start_time
    logger.info(f"\n✅ Pipeline complete. Total time: {elapsed.total_seconds():.1f}s")


def run_test(model: str = "gpt-4o"):
    """Run with a test article."""
    settings = get_settings()
    
    if not settings.is_api_configured:
        print("❌ OPENAI_API_KEY not configured!")
        return
    
    set_db_path(settings.db_path)
    init_db(reset=False)
    
    analyzer = EventAnalyzer(model=model)
    extractor = EventExtractor(analyzer=analyzer)
    
    test_article = {
        'source_url': f'test-{datetime.now().isoformat()}',
        'headline': 'US-China Trade Talks Resume Amid Tech Dispute',
        'article_text': '''
        The United States and China announced new trade negotiations today, 
        with both countries seeking to resolve ongoing disputes over technology tariffs.
        President Biden and President Xi spoke via phone call to discuss bilateral relations.
        
        Meanwhile, the European Union expressed concern about the potential impact on
        transatlantic trade, with officials in Brussels calling for closer coordination.
        
        Russia criticized the talks, with Foreign Minister Lavrov saying they could
        destabilize the global economic order.
        ''',
        'published_date': datetime.now().isoformat()
    }
    
    result = extractor.extract_events(test_article)
    
    print(f"\n📊 Test Extraction Result:")
    print(f"   News ID: {result.news_id}")
    print(f"   Events: {result.event_count}")
    
    for event in result.events:
        print(f"\n   Event {event.event_id}:")
        print(f"     {event.event_summary[:80]}...")
        print(f"     Dimension: {event.dimension}/{event.sub_dimension}")
        print(f"     Sentiment: {event.sentiment:+.0f}")
        print(f"     Actors: {event.actors}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Global International Relations Monitor"
    )
    parser.add_argument("--days", "-d", type=int, default=5)
    parser.add_argument("--batch-size", "-b", type=int, default=10)
    parser.add_argument("--delay", "-w", type=float, default=1.5)
    parser.add_argument("--model", "-m", type=str, default="gpt-4o",
                        choices=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"])
    parser.add_argument("--reset-db", action="store_true")
    parser.add_argument("--test", action="store_true")
    
    args = parser.parse_args()
    
    if args.test:
        run_test(model=args.model)
    else:
        main(
            days=args.days,
            batch_size=args.batch_size,
            delay_between=args.delay,
            model=args.model,
            reset_db=args.reset_db
        )
