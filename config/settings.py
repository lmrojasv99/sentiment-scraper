"""
Centralized configuration settings for the application.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SQL_DIR = PROJECT_ROOT / "sql"


@dataclass
class Settings:
    """Application settings container."""
    
    # API Configuration
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0
    openai_max_tokens: int = 4096
    
    # Database Configuration
    # If DATABASE_URL is set (Render Postgres), use it; otherwise use SQLite
    database_url: Optional[str] = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    db_name: str = "geopolitical_monitor.db"
    db_path: Path = field(default_factory=lambda: DATA_DIR / "geopolitical_monitor.db")
    schema_path: Path = field(default_factory=lambda: SQL_DIR / "schema.sql")
    
    @property
    def use_postgres(self) -> bool:
        """Check if using Postgres (via DATABASE_URL)."""
        return bool(self.database_url)
    
    # Scraper Configuration
    scraper_days_lookback: int = 5
    scraper_delay_min: float = 0.5
    scraper_delay_max: float = 1.5
    scraper_timeout: int = 15
    scraper_max_articles_per_feed: int = 20
    
    # Processing Configuration
    batch_size: int = 10
    delay_between_calls: float = 1.5
    max_retries: int = 3
    
    # Logging Configuration
    log_file: str = "agent.log"
    log_level: str = "INFO"
    
    # RSS Feeds
    rss_feeds: List[str] = field(default_factory=lambda: [
        # Reuters
        "https://www.rss.app/feeds/tswtMNNRqiPOqVe6.xml",
        # BBC
        "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        # NPR
        "https://feeds.npr.org/1004/rss.xml",
        # The Guardian
        "https://www.theguardian.com/world/americas/rss",
        "https://www.theguardian.com/us-news/rss",
        # Al Jazeera
        "https://www.aljazeera.com/xml/rss/all.xml",
        # Associated Press
        "https://rsshub.app/apnews/topics/world-news",
        # CBC (Canadian)
        "https://www.cbc.ca/webfeed/rss/rss-world",
        "https://www.cbc.ca/webfeed/rss/rss-politics",
        # Mexico News Daily
        "https://mexiconewsdaily.com/feed/",
    ])
    
    # Relevance Keywords
    relevance_keywords: List[str] = field(default_factory=lambda: [
        'united states', 'usa', 'u.s.', 'america', 'american', 'washington',
        'canada', 'canadian', 'ottawa', 'trudeau',
        'mexico', 'mexican', 'amlo', 'sheinbaum',
        'trade', 'tariff', 'nafta', 'usmca', 'border', 'immigration',
        'diplomacy', 'treaty', 'agreement', 'relations', 'summit',
        'sanction', 'embargo', 'cooperation', 'alliance', 'tension',
        'bilateral', 'trilateral', 'north america'
    ])
    
    def __post_init__(self):
        """Ensure data directory exists."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_api_configured(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key and self.openai_api_key != "your-openai-api-key-here")


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

