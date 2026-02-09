"""
Database Module V2 - Global International Relations Monitor
Event-Centric Database Design Based on Plover Methodology

Supports both SQLite (local development) and PostgreSQL (Render production).
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database configuration
_DB_PATH: Optional[Path] = None
_DATABASE_URL: Optional[str] = None


def set_db_path(path: Path) -> None:
    """Set the SQLite database file path (for local development)."""
    global _DB_PATH
    _DB_PATH = path


def set_database_url(url: str) -> None:
    """Set the PostgreSQL database URL (for production)."""
    global _DATABASE_URL
    _DATABASE_URL = url


def _use_postgres() -> bool:
    """Check if we should use PostgreSQL."""
    global _DATABASE_URL
    if _DATABASE_URL:
        return True
    # Also check environment variable
    return bool(os.getenv("DATABASE_URL"))


def _get_postgres_url() -> str:
    """Get PostgreSQL connection URL."""
    global _DATABASE_URL
    return _DATABASE_URL or os.getenv("DATABASE_URL", "")


def get_db_path() -> Path:
    """Get the SQLite database file path."""
    global _DB_PATH
    if _DB_PATH is None:
        project_root = Path(__file__).parent.parent.parent
        _DB_PATH = project_root / "data" / "geopolitical_monitor.db"
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


@contextmanager
def get_db_connection():
    """
    Get database connection - works for both SQLite and PostgreSQL.
    Uses context manager for automatic cleanup.
    """
    if _use_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(_get_postgres_url())
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.close()
    else:
        import sqlite3
        
        conn = sqlite3.connect(str(get_db_path()))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()


def _execute_query(conn, query: str, params: tuple = None):
    """Execute a query with proper parameter placeholder handling."""
    if _use_postgres():
        # PostgreSQL uses %s for placeholders
        query = query.replace("?", "%s")
    
    cursor = conn.cursor()
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor


def _row_to_dict(row, cursor=None) -> Dict:
    """Convert a database row to dictionary."""
    if row is None:
        return None
    if _use_postgres():
        # For psycopg2 with RealDictCursor or regular cursor
        if hasattr(row, '_asdict'):
            return row._asdict()
        elif hasattr(row, 'keys'):
            return dict(row)
        else:
            # Regular cursor - need column names from cursor description
            if cursor and cursor.description:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return dict(row) if hasattr(row, '__iter__') else row
    else:
        return dict(row)


def _run_migrations(conn) -> None:
    """Run safe schema migrations for existing databases."""
    cursor = conn.cursor()

    # Migration 1: Add language_detected column to articles
    try:
        if _use_postgres():
            cursor.execute("""
                ALTER TABLE articles ADD COLUMN IF NOT EXISTS language_detected TEXT
            """)
        else:
            # SQLite: check if column exists first
            cursor.execute("PRAGMA table_info(articles)")
            columns = [row[1] for row in cursor.fetchall()]
            if "language_detected" not in columns:
                cursor.execute("ALTER TABLE articles ADD COLUMN language_detected TEXT")
                logger.info("Migration: Added language_detected column to articles")
    except Exception as e:
        logger.warning(f"Migration (language_detected): {e}")


def init_db(reset: bool = False) -> None:
    """
    Initialize database with V2 schema.

    Args:
        reset: If True, drops existing tables and recreates schema
    """
    with get_db_connection() as conn:
        try:
            if reset:
                _drop_tables(conn)

            _create_tables(conn)
            _run_migrations(conn)
            _populate_taxonomy(conn)
            _populate_countries(conn)

            conn.commit()
            logger.info(f"Database initialized successfully (reset={reset})")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
            raise


def _drop_tables(conn) -> None:
    """Drop all tables."""
    tables = [
        "event_actors",
        "events", 
        "articles",
        "dimensions_taxonomy",
        "countries_reference"
    ]
    
    if _use_postgres():
        for table in tables:
            _execute_query(conn, f"DROP TABLE IF EXISTS {table} CASCADE")
    else:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in tables:
            _execute_query(conn, f"DROP TABLE IF EXISTS {table}")
        # Drop views
        for view in ["v_events_full", "v_actor_pairs", "v_sentiment_by_dimension"]:
            _execute_query(conn, f"DROP VIEW IF EXISTS {view}")
        conn.execute("PRAGMA foreign_keys = ON")


def _create_tables(conn) -> None:
    """Create V2 schema tables."""
    cursor = conn.cursor()
    
    if _use_postgres():
        # PostgreSQL schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                news_id SERIAL PRIMARY KEY,
                news_title TEXT NOT NULL,
                news_text TEXT,
                article_summary TEXT,
                publication_date TEXT,
                source_url TEXT UNIQUE,
                source_domain TEXT,
                source_country TEXT,
                language TEXT DEFAULT 'en',
                language_detected TEXT,
                date_scraped TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                event_id TEXT UNIQUE NOT NULL,
                news_id INTEGER NOT NULL REFERENCES articles(news_id) ON DELETE CASCADE,
                event_summary TEXT,
                event_date TEXT,
                event_location TEXT,
                dimension TEXT,
                event_type TEXT,
                sub_dimension TEXT,
                direction TEXT CHECK(direction IN ('unilateral', 'bilateral', 'multilateral')),
                sentiment REAL CHECK(sentiment >= -10 AND sentiment <= 10),
                confidence_level REAL CHECK(confidence_level >= 0 AND confidence_level <= 1)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_actors (
                id SERIAL PRIMARY KEY,
                event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
                actor_iso3 TEXT NOT NULL,
                actor_role TEXT NOT NULL CHECK(actor_role IN ('actor1', 'actor1_secondary', 'actor2', 'actor2_secondary'))
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dimensions_taxonomy (
                id SERIAL PRIMARY KEY,
                dimension TEXT NOT NULL,
                sub_dimension TEXT NOT NULL,
                description TEXT,
                UNIQUE(dimension, sub_dimension)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS countries_reference (
                iso3 TEXT PRIMARY KEY,
                country_name TEXT NOT NULL,
                aliases TEXT
            )
        ''')
    else:
        # SQLite schema
        cursor.execute('''
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
                language_detected TEXT,
                date_scraped TEXT
            )
        ''')
        
        cursor.execute('''
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_actors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                actor_iso3 TEXT NOT NULL,
                actor_role TEXT NOT NULL CHECK(actor_role IN ('actor1', 'actor1_secondary', 'actor2', 'actor2_secondary')),
                FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dimensions_taxonomy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dimension TEXT NOT NULL,
                sub_dimension TEXT NOT NULL,
                description TEXT,
                UNIQUE(dimension, sub_dimension)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS countries_reference (
                iso3 TEXT PRIMARY KEY,
                country_name TEXT NOT NULL,
                aliases TEXT
            )
        ''')
    
    # Create indexes (same syntax for both)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_events_news_id ON events(news_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_dimension ON events(dimension)",
        "CREATE INDEX IF NOT EXISTS idx_events_direction ON events(direction)",
        "CREATE INDEX IF NOT EXISTS idx_events_sentiment ON events(sentiment)",
        "CREATE INDEX IF NOT EXISTS idx_event_actors_event_id ON event_actors(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_event_actors_iso3 ON event_actors(actor_iso3)",
    ]
    
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass  # Index may already exist


def _populate_taxonomy(conn) -> None:
    """Populate the dimensions taxonomy table."""
    taxonomy = [
        ('Political Relations', 'political', 'General political interactions'),
        ('Political Relations', 'government', 'Government-level interactions'),
        ('Political Relations', 'election', 'Electoral processes'),
        ('Political Relations', 'legislative', 'Legislative actions'),
        ('Political Relations', 'diplomatic', 'Diplomatic relations'),
        ('Political Relations', 'legal', 'Legal proceedings'),
        ('Political Relations', 'refugee', 'Refugee-related policies'),
        ('Material Conflict', 'military', 'Military actions and defense'),
        ('Material Conflict', 'terrorism', 'Terrorism-related events'),
        ('Material Conflict', 'cbrn', 'Chemical, biological, radiological, nuclear'),
        ('Material Conflict', 'cyber', 'Cyber warfare and digital security'),
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
        ('Other', 'resource', 'Resource-related events'),
        ('Other', 'disease', 'Health crises and pandemics'),
        ('Other', 'disaster', 'Natural disasters'),
        ('Other', 'historical', 'Historical references'),
        ('Other', 'hypothetical', 'Speculative events'),
        ('Other', 'culture', 'Cultural exchanges'),
    ]
    
    if _use_postgres():
        cursor = conn.cursor()
        for dim, sub_dim, desc in taxonomy:
            cursor.execute('''
                INSERT INTO dimensions_taxonomy (dimension, sub_dimension, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (dimension, sub_dimension) DO NOTHING
            ''', (dim, sub_dim, desc))
    else:
        cursor = conn.cursor()
        for dim, sub_dim, desc in taxonomy:
            cursor.execute('''
                INSERT OR IGNORE INTO dimensions_taxonomy (dimension, sub_dimension, description)
                VALUES (?, ?, ?)
            ''', (dim, sub_dim, desc))


def _populate_countries(conn) -> None:
    """Populate the countries reference table."""
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
    
    if _use_postgres():
        cursor = conn.cursor()
        for iso3, name, aliases in countries:
            cursor.execute('''
                INSERT INTO countries_reference (iso3, country_name, aliases)
                VALUES (%s, %s, %s)
                ON CONFLICT (iso3) DO NOTHING
            ''', (iso3, name, aliases))
    else:
        cursor = conn.cursor()
        for iso3, name, aliases in countries:
            cursor.execute('''
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
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        try:
            news_title = article_data.get('news_title', article_data.get('headline', ''))
            news_text = article_data.get('news_text', article_data.get('article_text', ''))
            
            if _use_postgres():
                cursor.execute('''
                    INSERT INTO articles (
                        news_title, news_text, article_summary,
                        publication_date, source_url, source_domain,
                        source_country, language, language_detected, date_scraped
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING news_id
                ''', (
                    news_title,
                    news_text,
                    article_data.get('article_summary', ''),
                    article_data.get('publication_date', article_data.get('date', '')),
                    article_data.get('source_url', ''),
                    article_data.get('source_domain', ''),
                    article_data.get('source_country', ''),
                    article_data.get('language', 'en'),
                    article_data.get('language_detected', ''),
                    datetime.utcnow().isoformat()
                ))
                row = cursor.fetchone()
                news_id = row[0] if row else None
            else:
                # SQLite - get next ID manually
                news_id = article_data.get('news_id')
                if news_id is None:
                    cursor.execute('SELECT COALESCE(MAX(news_id), 0) + 1 FROM articles')
                    news_id = cursor.fetchone()[0]
                
                cursor.execute('''
                    INSERT INTO articles (
                        news_id, news_title, news_text, article_summary,
                        publication_date, source_url, source_domain,
                        source_country, language, language_detected, date_scraped
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    news_id,
                    news_title,
                    news_text,
                    article_data.get('article_summary', ''),
                    article_data.get('publication_date', article_data.get('date', '')),
                    article_data.get('source_url', ''),
                    article_data.get('source_domain', ''),
                    article_data.get('source_country', ''),
                    article_data.get('language', 'en'),
                    article_data.get('language_detected', ''),
                    datetime.utcnow().isoformat()
                ))
            
            conn.commit()
            return news_id
            
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                return None
            logger.error(f"Error inserting article: {e}")
            conn.rollback()
            return None


def get_article_by_url(url: str) -> Optional[Dict]:
    """Get article by source URL."""
    with get_db_connection() as conn:
        cursor = _execute_query(conn, 'SELECT * FROM articles WHERE source_url = ?', (url,))
        row = cursor.fetchone()
        return _row_to_dict(row, cursor)


def get_article_by_id(news_id: int) -> Optional[Dict]:
    """Get article by news_id."""
    with get_db_connection() as conn:
        cursor = _execute_query(conn, 'SELECT * FROM articles WHERE news_id = ?', (news_id,))
        row = cursor.fetchone()
        return _row_to_dict(row, cursor)


def update_article_summary(news_id: int, summary: str) -> bool:
    """Update article summary."""
    with get_db_connection() as conn:
        cursor = _execute_query(
            conn, 
            'UPDATE articles SET article_summary = ? WHERE news_id = ?', 
            (summary, news_id)
        )
        conn.commit()
        return cursor.rowcount > 0


# =============================================================================
# EVENT OPERATIONS
# =============================================================================

def insert_event(event_data: Dict[str, Any]) -> Optional[str]:
    """Insert a new event into the database."""
    with get_db_connection() as conn:
        try:
            if _use_postgres():
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO events (
                        event_id, news_id, event_summary, event_date,
                        dimension, sub_dimension,
                        direction, sentiment, confidence_level
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    event_data['event_id'],
                    event_data['news_id'],
                    event_data.get('event_summary', ''),
                    event_data.get('event_date', ''),
                    event_data.get('dimension', ''),
                    event_data.get('sub_dimension', ''),
                    event_data.get('direction', 'bilateral'),
                    event_data.get('sentiment', 0),
                    event_data.get('confidence_level', 0.5)
                ))
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO events (
                        event_id, news_id, event_summary, event_date,
                        dimension, sub_dimension,
                        direction, sentiment, confidence_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_data['event_id'],
                    event_data['news_id'],
                    event_data.get('event_summary', ''),
                    event_data.get('event_date', ''),
                    event_data.get('dimension', ''),
                    event_data.get('sub_dimension', ''),
                    event_data.get('direction', 'bilateral'),
                    event_data.get('sentiment', 0),
                    event_data.get('confidence_level', 0.5)
                ))
            
            conn.commit()
            return event_data['event_id']
            
        except Exception as e:
            logger.error(f"Error inserting event {event_data.get('event_id')}: {e}")
            conn.rollback()
            return None


def insert_event_actors(event_id: str, actors: Dict[str, List[str]]) -> bool:
    """Insert actor roles for an event."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
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
                        if _use_postgres():
                            cursor.execute('''
                                INSERT INTO event_actors (event_id, actor_iso3, actor_role)
                                VALUES (%s, %s, %s)
                            ''', (event_id, iso3.upper(), role))
                        else:
                            cursor.execute('''
                                INSERT INTO event_actors (event_id, actor_iso3, actor_role)
                                VALUES (?, ?, ?)
                            ''', (event_id, iso3.upper(), role))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error inserting actors for event {event_id}: {e}")
            conn.rollback()
            return False


def get_events_by_article(news_id: int) -> List[Dict]:
    """Get all events for a specific article."""
    with get_db_connection() as conn:
        if _use_postgres():
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.*, STRING_AGG(DISTINCT ea.actor_iso3, ',') as all_actors
                FROM events e
                LEFT JOIN event_actors ea ON e.event_id = ea.event_id
                WHERE e.news_id = %s
                GROUP BY e.id, e.event_id, e.news_id, e.event_summary, e.event_date,
                         e.event_location, e.dimension, e.event_type, e.sub_dimension,
                         e.direction, e.sentiment, e.confidence_level
                ORDER BY e.event_id
            ''', (news_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.*, GROUP_CONCAT(DISTINCT ea.actor_iso3) as all_actors
                FROM events e
                LEFT JOIN event_actors ea ON e.event_id = ea.event_id
                WHERE e.news_id = ?
                GROUP BY e.event_id
                ORDER BY e.event_id
            ''', (news_id,))
        
        rows = cursor.fetchall()
        return [_row_to_dict(row, cursor) for row in rows]


def get_events_by_dimension(dimension: str) -> List[Dict]:
    """Get all events for a specific dimension."""
    with get_db_connection() as conn:
        cursor = _execute_query(conn, '''
            SELECT e.*, a.news_title, a.publication_date
            FROM events e
            JOIN articles a ON e.news_id = a.news_id
            WHERE e.dimension = ?
            ORDER BY e.event_date DESC
        ''', (dimension,))
        
        rows = cursor.fetchall()
        return [_row_to_dict(row, cursor) for row in rows]


def get_events_by_country_pair(iso3_a: str, iso3_b: str) -> List[Dict]:
    """Get all events involving a specific pair of countries."""
    with get_db_connection() as conn:
        cursor = _execute_query(conn, '''
            SELECT DISTINCT e.*, a.news_title
            FROM events e
            JOIN articles a ON e.news_id = a.news_id
            JOIN event_actors ea1 ON e.event_id = ea1.event_id
            JOIN event_actors ea2 ON e.event_id = ea2.event_id
            WHERE ea1.actor_iso3 = ? AND ea2.actor_iso3 = ?
            ORDER BY e.event_date DESC
        ''', (iso3_a.upper(), iso3_b.upper()))
        
        rows = cursor.fetchall()
        return [_row_to_dict(row, cursor) for row in rows]


def get_valid_dimensions() -> List[str]:
    """Get list of valid dimension values."""
    with get_db_connection() as conn:
        cursor = _execute_query(conn, 'SELECT DISTINCT dimension FROM dimensions_taxonomy')
        rows = cursor.fetchall()
        return [_row_to_dict(row, cursor)['dimension'] for row in rows]


def get_statistics() -> Dict[str, Any]:
    """Get comprehensive database statistics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        stats = {}
        
        cursor = _execute_query(conn, 'SELECT COUNT(*) as cnt FROM articles')
        row = cursor.fetchone()
        stats['total_articles'] = row[0] if row else 0
        
        cursor = _execute_query(conn, 'SELECT COUNT(*) as cnt FROM events')
        row = cursor.fetchone()
        stats['total_events'] = row[0] if row else 0
        
        cursor = _execute_query(conn, '''
            SELECT AVG(event_count) as avg_events
            FROM (SELECT news_id, COUNT(*) as event_count FROM events GROUP BY news_id) sub
        ''')
        row = cursor.fetchone()
        stats['avg_events_per_article'] = round(row[0] or 0, 2) if row else 0
        
        cursor = _execute_query(conn, 'SELECT ROUND(AVG(sentiment)::numeric, 2) FROM events') if _use_postgres() else \
                 _execute_query(conn, 'SELECT ROUND(AVG(sentiment), 2) FROM events')
        row = cursor.fetchone()
        stats['avg_sentiment'] = row[0] if row else None
        
        cursor = _execute_query(conn, '''
            SELECT dimension, COUNT(*) as count FROM events
            GROUP BY dimension ORDER BY count DESC
        ''')
        stats['events_by_dimension'] = {_row_to_dict(row, cursor)['dimension']: _row_to_dict(row, cursor)['count'] 
                                         for row in cursor.fetchall()}
        
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initializing database...")
    init_db(reset=False)
    stats = get_statistics()
    print(f"Articles: {stats['total_articles']}, Events: {stats['total_events']}")
