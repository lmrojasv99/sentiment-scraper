"""
Database Module V2 - Global International Relations Monitor
Event-Centric Database Design Based on Plover Methodology

Supports multi-event extraction per article with full actor role assignment.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Default paths (can be overridden via config)
_DB_PATH: Optional[Path] = None


def set_db_path(path: Path) -> None:
    """Set the database file path."""
    global _DB_PATH
    _DB_PATH = path


def get_db_path() -> Path:
    """Get the database file path."""
    global _DB_PATH
    if _DB_PATH is None:
        # Default to project root/data directory
        project_root = Path(__file__).parent.parent.parent
        _DB_PATH = project_root / "data" / "geopolitical_monitor.db"
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory enabled."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False) -> None:
    """
    Initialize database with V2 schema.
    
    Args:
        reset: If True, drops existing tables and recreates schema
    """
    conn = get_db_connection()
    
    try:
        if reset:
            # Disable foreign keys temporarily for clean drop
            conn.execute("PRAGMA foreign_keys = OFF")
            
            # Drop tables in correct order (children first)
            conn.execute("DROP TABLE IF EXISTS event_actors")
            conn.execute("DROP TABLE IF EXISTS events")
            conn.execute("DROP TABLE IF EXISTS articles")
            conn.execute("DROP TABLE IF EXISTS dimensions_taxonomy")
            conn.execute("DROP TABLE IF EXISTS countries_reference")
            conn.execute("DROP VIEW IF EXISTS v_events_full")
            conn.execute("DROP VIEW IF EXISTS v_actor_pairs")
            conn.execute("DROP VIEW IF EXISTS v_sentiment_by_dimension")
            conn.commit()
            
            # Re-enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Create tables
            _create_tables_v2(conn)
            _populate_taxonomy(conn)
            _populate_countries(conn)
            
            logger.info(f"Database {get_db_path()} initialized with V2 schema (reset mode)")
        else:
            # Create tables only if they don't exist
            _create_tables_v2(conn)
            _populate_taxonomy(conn)
            _populate_countries(conn)
            logger.info(f"Database {get_db_path()} initialized with V2 schema")
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def _create_tables_v2(conn: sqlite3.Connection) -> None:
    """Create V2 schema tables if they don't exist."""
    c = conn.cursor()
    
    # Articles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            news_id INTEGER PRIMARY KEY,
            news_title TEXT NOT NULL,
            news_text TEXT,
            article_summary TEXT,
            publication_date TEXT,
            source_url TEXT UNIQUE,
            source_domain TEXT,
            source_country TEXT,
            language TEXT DEFAULT 'en',
            date_scraped TEXT
        )
    ''')
    
    # Events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            news_id INTEGER NOT NULL,
            event_summary TEXT,
            event_date TEXT,
            event_location TEXT,
            dimension TEXT,
            event_type TEXT,
            sub_dimension TEXT,
            direction TEXT CHECK(direction IN ('unilateral', 'bilateral', 'multilateral')),
            sentiment REAL CHECK(sentiment >= -10 AND sentiment <= 10),
            confidence_level REAL CHECK(confidence_level >= 0 AND confidence_level <= 1),
            FOREIGN KEY (news_id) REFERENCES articles(news_id) ON DELETE CASCADE
        )
    ''')
    
    # Event actors table
    c.execute('''
        CREATE TABLE IF NOT EXISTS event_actors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            actor_iso3 TEXT NOT NULL,
            actor_role TEXT NOT NULL CHECK(actor_role IN ('actor1', 'actor1_secondary', 'actor2', 'actor2_secondary')),
            FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
        )
    ''')
    
    # Dimensions taxonomy table
    c.execute('''
        CREATE TABLE IF NOT EXISTS dimensions_taxonomy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dimension TEXT NOT NULL,
            sub_dimension TEXT NOT NULL,
            description TEXT,
            UNIQUE(dimension, sub_dimension)
        )
    ''')
    
    # Countries reference table
    c.execute('''
        CREATE TABLE IF NOT EXISTS countries_reference (
            iso3 TEXT PRIMARY KEY,
            country_name TEXT NOT NULL,
            aliases TEXT
        )
    ''')
    
    # Create indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_events_news_id ON events(news_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_events_dimension ON events(dimension)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_events_direction ON events(direction)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_events_sentiment ON events(sentiment)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_event_actors_event_id ON event_actors(event_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_event_actors_iso3 ON event_actors(actor_iso3)')


def _populate_taxonomy(conn: sqlite3.Connection) -> None:
    """Populate the dimensions taxonomy table with Plover-based categories."""
    c = conn.cursor()
    
    taxonomy = [
        # Political Relations
        ('Political Relations', 'political', 'General political interactions'),
        ('Political Relations', 'government', 'Government-level interactions'),
        ('Political Relations', 'election', 'Electoral processes'),
        ('Political Relations', 'legislative', 'Legislative actions'),
        ('Political Relations', 'diplomatic', 'Diplomatic relations'),
        ('Political Relations', 'legal', 'Legal proceedings'),
        ('Political Relations', 'refugee', 'Refugee-related policies'),
        # Material Conflict
        ('Material Conflict', 'military', 'Military actions and defense'),
        ('Material Conflict', 'terrorism', 'Terrorism-related events'),
        ('Material Conflict', 'cbrn', 'Chemical, biological, radiological, nuclear'),
        ('Material Conflict', 'cyber', 'Cyber warfare and digital security'),
        # Economic Relations
        ('Economic Relations', 'economic', 'General economic interactions'),
        ('Economic Relations', 'trade', 'Trade agreements and tariffs'),
        ('Economic Relations', 'aid', 'Foreign and humanitarian aid'),
        ('Economic Relations', 'capital_flows', 'Investment and financial transfers'),
        ('Economic Relations', 'strategic_economic', 'Strategic economic policies'),
        ('Economic Relations', 'financial_monetary', 'Financial and monetary policy'),
        ('Economic Relations', 'development', 'Development projects'),
        ('Economic Relations', 'taxation_fiscal', 'Tax and fiscal matters'),
        ('Economic Relations', 'investment', 'Foreign direct investment'),
        ('Economic Relations', 'resources', 'Natural resources and energy'),
        ('Economic Relations', 'labour_migration', 'Labor migration'),
        ('Economic Relations', 'technology_transfer', 'Technology and innovation'),
        # Other
        ('Other', 'resource', 'Resource-related events'),
        ('Other', 'disease', 'Health crises and pandemics'),
        ('Other', 'disaster', 'Natural disasters'),
        ('Other', 'historical', 'Historical references'),
        ('Other', 'hypothetical', 'Speculative events'),
        ('Other', 'culture', 'Cultural exchanges'),
    ]
    
    for dim, sub_dim, desc in taxonomy:
        c.execute('''
            INSERT OR IGNORE INTO dimensions_taxonomy (dimension, sub_dimension, description)
            VALUES (?, ?, ?)
        ''', (dim, sub_dim, desc))


def _populate_countries(conn: sqlite3.Connection) -> None:
    """Populate the countries reference table with common countries."""
    c = conn.cursor()
    
    countries = [
        ('USA', 'United States of America', '["United States", "US", "American"]'),
        ('CAN', 'Canada', '["Canadian", "Ottawa"]'),
        ('MEX', 'Mexico', '["Mexican"]'),
        ('GBR', 'United Kingdom', '["UK", "Britain", "British"]'),
        ('FRA', 'France', '["French"]'),
        ('DEU', 'Germany', '["German"]'),
        ('CHN', 'China', '["Chinese", "Beijing"]'),
        ('RUS', 'Russia', '["Russian", "Moscow"]'),
        ('JPN', 'Japan', '["Japanese"]'),
        ('IND', 'India', '["Indian"]'),
        ('BRA', 'Brazil', '["Brazilian"]'),
        ('AUS', 'Australia', '["Australian"]'),
        ('ITA', 'Italy', '["Italian"]'),
        ('ESP', 'Spain', '["Spanish"]'),
        ('KOR', 'South Korea', '["Korean", "Seoul"]'),
        ('PRK', 'North Korea', '["DPRK", "Pyongyang"]'),
        ('IRN', 'Iran', '["Iranian", "Tehran"]'),
        ('ISR', 'Israel', '["Israeli"]'),
        ('SAU', 'Saudi Arabia', '["Saudi"]'),
        ('UKR', 'Ukraine', '["Ukrainian", "Kyiv"]'),
        ('POL', 'Poland', '["Polish"]'),
        ('TUR', 'Turkey', '["Turkish", "Ankara"]'),
        ('EGY', 'Egypt', '["Egyptian"]'),
        ('PAK', 'Pakistan', '["Pakistani"]'),
        ('ARE', 'United Arab Emirates', '["UAE", "Emirati"]'),
        ('QAT', 'Qatar', '["Qatari"]'),
        ('SYR', 'Syria', '["Syrian"]'),
        ('AFG', 'Afghanistan', '["Afghan"]'),
        ('VNM', 'Vietnam', '["Vietnamese"]'),
        ('PHL', 'Philippines', '["Filipino", "Philippine"]'),
    ]
    
    for iso3, name, aliases in countries:
        c.execute('''
            INSERT OR IGNORE INTO countries_reference (iso3, country_name, aliases)
            VALUES (?, ?, ?)
        ''', (iso3, name, aliases))


# =============================================================================
# ARTICLE OPERATIONS
# =============================================================================

def insert_article(article_data: Dict[str, Any]) -> Optional[int]:
    """
    Insert a new article into the database.
    
    Returns:
        news_id of inserted article, or None if duplicate
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        news_id = article_data.get('news_id')
        if news_id is None:
            c.execute('SELECT COALESCE(MAX(news_id), 0) + 1 FROM articles')
            news_id = c.fetchone()[0]
        
        c.execute('''
            INSERT INTO articles (
                news_id, news_title, news_text, article_summary,
                publication_date, source_url, source_domain,
                source_country, language, date_scraped
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            news_id,
            article_data.get('news_title', article_data.get('headline', '')),
            article_data.get('news_text', article_data.get('article_text', '')),
            article_data.get('article_summary', ''),
            article_data.get('publication_date', article_data.get('date', '')),
            article_data.get('source_url', ''),
            article_data.get('source_domain', ''),
            article_data.get('source_country', ''),
            article_data.get('language', 'en'),
            datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        return news_id
        
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_article_by_url(url: str) -> Optional[Dict]:
    """Get article by source URL."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM articles WHERE source_url = ?', (url,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_article_by_id(news_id: int) -> Optional[Dict]:
    """Get article by news_id."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM articles WHERE news_id = ?', (news_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_article_summary(news_id: int, summary: str) -> bool:
    """Update article summary."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE articles SET article_summary = ? WHERE news_id = ?', (summary, news_id))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


# =============================================================================
# EVENT OPERATIONS
# =============================================================================

def insert_event(event_data: Dict[str, Any]) -> Optional[str]:
    """Insert a new event into the database."""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT INTO events (
                event_id, news_id, event_summary, event_date,
                event_location, dimension, event_type, sub_dimension,
                direction, sentiment, confidence_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event_data['event_id'],
            event_data['news_id'],
            event_data.get('event_summary', ''),
            event_data.get('event_date', ''),
            event_data.get('event_location', ''),
            event_data.get('dimension', ''),
            event_data.get('event_type', ''),
            event_data.get('sub_dimension', ''),
            event_data.get('direction', 'bilateral'),
            event_data.get('sentiment', 0),
            event_data.get('confidence_level', 0.5)
        ))
        
        conn.commit()
        return event_data['event_id']
        
    except sqlite3.IntegrityError as e:
        logger.error(f"Error inserting event {event_data.get('event_id')}: {e}")
        return None
    finally:
        conn.close()


def insert_event_actors(event_id: str, actors: Dict[str, List[str]]) -> bool:
    """Insert actor roles for an event."""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        for role, iso3_codes in actors.items():
            if role not in ('actor1', 'actor1_secondary', 'actor2', 'actor2_secondary'):
                continue
            
            if isinstance(iso3_codes, str):
                codes = [code.strip() for code in iso3_codes.split(',') if code.strip()]
            else:
                codes = iso3_codes or []
            
            for iso3 in codes:
                if iso3:
                    c.execute('''
                        INSERT INTO event_actors (event_id, actor_iso3, actor_role)
                        VALUES (?, ?, ?)
                    ''', (event_id, iso3.upper(), role))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error inserting actors for event {event_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_events_by_article(news_id: int) -> List[Dict]:
    """Get all events for a specific article."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT e.*, GROUP_CONCAT(DISTINCT ea.actor_iso3) as all_actors
        FROM events e
        LEFT JOIN event_actors ea ON e.event_id = ea.event_id
        WHERE e.news_id = ?
        GROUP BY e.event_id
        ORDER BY e.event_id
    ''', (news_id,))
    
    events = [dict(row) for row in c.fetchall()]
    conn.close()
    return events


def get_events_by_dimension(dimension: str) -> List[Dict]:
    """Get all events for a specific dimension."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT e.*, a.news_title, a.publication_date
        FROM events e
        JOIN articles a ON e.news_id = a.news_id
        WHERE e.dimension = ?
        ORDER BY e.event_date DESC
    ''', (dimension,))
    
    events = [dict(row) for row in c.fetchall()]
    conn.close()
    return events


def get_events_by_country_pair(iso3_a: str, iso3_b: str) -> List[Dict]:
    """Get all events involving a specific pair of countries."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT DISTINCT e.*, a.news_title
        FROM events e
        JOIN articles a ON e.news_id = a.news_id
        JOIN event_actors ea1 ON e.event_id = ea1.event_id
        JOIN event_actors ea2 ON e.event_id = ea2.event_id
        WHERE ea1.actor_iso3 = ? AND ea2.actor_iso3 = ?
        ORDER BY e.event_date DESC
    ''', (iso3_a.upper(), iso3_b.upper()))
    
    events = [dict(row) for row in c.fetchall()]
    conn.close()
    return events


def get_valid_dimensions() -> List[str]:
    """Get list of valid dimension values."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT dimension FROM dimensions_taxonomy')
    dimensions = [row['dimension'] for row in c.fetchall()]
    conn.close()
    return dimensions


def get_statistics() -> Dict[str, Any]:
    """Get comprehensive database statistics."""
    conn = get_db_connection()
    c = conn.cursor()
    
    stats = {}
    
    c.execute('SELECT COUNT(*) FROM articles')
    stats['total_articles'] = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM events')
    stats['total_events'] = c.fetchone()[0]
    
    c.execute('''
        SELECT AVG(event_count) as avg_events
        FROM (SELECT news_id, COUNT(*) as event_count FROM events GROUP BY news_id)
    ''')
    row = c.fetchone()
    stats['avg_events_per_article'] = round(row['avg_events'] or 0, 2)
    
    c.execute('SELECT ROUND(AVG(sentiment), 2) FROM events')
    stats['avg_sentiment'] = c.fetchone()[0]
    
    c.execute('''
        SELECT dimension, COUNT(*) as count FROM events
        GROUP BY dimension ORDER BY count DESC
    ''')
    stats['events_by_dimension'] = {row['dimension']: row['count'] for row in c.fetchall()}
    
    conn.close()
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initializing database...")
    init_db(reset=False)
    stats = get_statistics()
    print(f"Articles: {stats['total_articles']}, Events: {stats['total_events']}")

