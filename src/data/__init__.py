"""
Data module - Database operations and news scraping.
"""

from .database import (
    init_db,
    get_db_connection,
    insert_article,
    insert_event,
    insert_event_actors,
    get_events_by_article,
    get_events_by_dimension,
    get_events_by_country_pair,
    get_statistics
)
from .scraper import NewsScraper

__all__ = [
    'init_db',
    'get_db_connection',
    'insert_article',
    'insert_event',
    'insert_event_actors',
    'get_events_by_article',
    'get_events_by_dimension',
    'get_events_by_country_pair',
    'get_statistics',
    'NewsScraper'
]

