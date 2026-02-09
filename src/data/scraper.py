import os
import csv
import time
import random
import logging
import requests
import feedparser
from datetime import datetime, timedelta
from newspaper import Article, Config
from dateutil import parser as date_parser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewsScraper:
    """
    News scraper using free RSS feeds from major news outlets.
    Focuses on North American international relations (US, Canada, Mexico).
    """
    
    def __init__(self, feeds_csv=None):
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.config = Config()
        self.config.browser_user_agent = self.user_agent
        self.config.request_timeout = 15
        
        # Get base path for CSV files
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Load RSS feeds from CSV
        feeds_path = feeds_csv or os.path.join(base_path, 'RSS_feeds.csv')
        self.rss_feeds = self._load_feeds_from_csv(feeds_path)
        # Keywords are no longer used by the scraper.
        # International-context filtering happens post-translation in intl_filter.py.
    
    def _load_feeds_from_csv(self, csv_path):
        """Load RSS feeds from CSV. Returns list of dicts with 'url' and 'country'."""
        feeds = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('RSS_Feed') or row.get('url')
                    country = row.get('Country', '').strip()
                    if url and url.strip():
                        feeds.append({'url': url.strip(), 'country': country})
            logger.info(f"Loaded {len(feeds)} RSS feeds from {csv_path}")
        except FileNotFoundError:
            logger.error(f"RSS feeds CSV not found: {csv_path}")
        except Exception as e:
            logger.error(f"Error loading RSS feeds: {e}")
        return feeds

    def scrape_articles(self, days=5):
        """
        Scrapes articles from RSS feeds, filtering for North American relevance.
        Includes timing to track execution duration.
        
        Returns:
            tuple: (articles list, elapsed time in seconds)
        """
        start_time = time.time()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        all_articles = []
        seen_urls = set()
        
        logger.info(f"Starting scrape for articles from the last {days} day(s)...")
        
        for feed_info in self.rss_feeds:
            feed_url = feed_info['url'] if isinstance(feed_info, dict) else feed_info
            source_country = feed_info.get('country', '') if isinstance(feed_info, dict) else ''
            logger.info(f"Fetching RSS feed: {feed_url} (country: {source_country or 'unknown'})")
            try:
                articles = self._parse_feed(feed_url, cutoff_date, seen_urls, source_country)
                all_articles.extend(articles)
                time.sleep(random.uniform(0.5, 1.5))  # Be respectful to servers
            except Exception as e:
                logger.warning(f"Error fetching feed {feed_url}: {e}")
                continue
        
        # Calculate and log timing
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        logger.info(f"Found {len(all_articles)} relevant articles from RSS feeds")
        logger.info(f"⏱️  Scraping completed in {int(minutes)}m {seconds:.2f}s for {days} day(s)")
        
        return all_articles, elapsed_time

    def _parse_feed(self, feed_url, cutoff_date, seen_urls, source_country=''):
        """Parse a single RSS feed and extract articles (no relevance filter — that happens after translation)."""
        articles = []
        
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(feed_url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
        except Exception as e:
            logger.warning(f"Failed to fetch feed {feed_url}: {e}")
            return articles
        
        for entry in feed.entries:
            try:
                # Get URL
                url = entry.get('link', '')
                if not url or url in seen_urls:
                    continue
                
                # Get title
                title = entry.get('title', '')
                if not title:
                    continue
                
                # Parse publication date
                pub_date = self._parse_date(entry)
                if pub_date and pub_date < cutoff_date:
                    continue
                
                seen_urls.add(url)
                
                # Fetch full article content
                content = self._fetch_article_content(url)
                
                if content:
                    articles.append({
                        'source_url': url,
                        'headline': title,
                        'published_date': pub_date.isoformat() if pub_date else datetime.now().isoformat(),
                        'source': feed.feed.get('title', 'Unknown'),
                        'source_country': source_country,
                        'article_text': content
                    })
                    logger.info(f"✓ Scraped article: {title[:60]}...")
                    
            except Exception as e:
                logger.debug(f"Error processing entry: {e}")
                continue
        
        return articles
    # NOTE: _is_relevant() has been removed.
    # Relevance filtering now happens AFTER translation, in the
    # international context filter (src/utils/intl_filter.py).

    def _parse_date(self, entry):
        """Parse publication date from feed entry."""
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
        
        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    struct_time = getattr(entry, field)
                    return datetime(*struct_time[:6])
                except:
                    pass
        
        # Try string date parsing
        date_strings = ['published', 'updated', 'created', 'pubDate']
        for field in date_strings:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    return date_parser.parse(getattr(entry, field))
                except:
                    pass
        
        return datetime.now()

    def _fetch_article_content(self, url, retries=2):
        """
        Fetches and parses the article content using newspaper3k.
        """
        for i in range(retries):
            try:
                headers = {'User-Agent': self.user_agent}
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                
                article = Article(url, config=self.config)
                article.set_html(response.text)
                article.parse()
                
                # Return content if substantial
                if article.text and len(article.text) > 200:
                    return article.text
                return None
                
            except Exception as e:
                wait_time = (2 ** i) + random.random()
                logger.debug(f"Retry {i+1} for {url}: {e}")
                time.sleep(wait_time)
        
        return None


if __name__ == "__main__":
    scraper = NewsScraper()
    articles, elapsed = scraper.scrape_articles(days=3)
    
    print(f"\n{'='*60}")
    print(f"Scraped {len(articles)} relevant articles")
    print(f"⏱️  Total time: {elapsed:.2f} seconds")
    print(f"{'='*60}")
    
    for i, article in enumerate(articles[:5], 1):
        print(f"\n{i}. {article['headline'][:80]}")
        print(f"   Source: {article['source']}")
        print(f"   URL: {article['source_url'][:60]}...")
