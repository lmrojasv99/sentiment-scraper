"""
Event Extractor Module - Business Logic for Multi-Event Processing

Coordinates between analyzer and database for extracting, validating,
and storing international events from news articles.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from src.core.analyzer import EventAnalyzer
from src.data.database import (
    insert_article, insert_event, insert_event_actors,
    get_article_by_url, get_valid_dimensions
)
from src.utils.country_mapper import get_mapper

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Data class representing an international event."""
    event_id: str
    news_id: int
    event_summary: str
    event_date: str = ""
    dimension: str = "Other"
    sub_dimension: str = ""
    direction: str = "bilateral"
    sentiment: float = 0.0
    confidence_level: float = 0.5
    actors: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'event_id': self.event_id,
            'news_id': self.news_id,
            'event_summary': self.event_summary,
            'event_date': self.event_date,
            'dimension': self.dimension,
            'sub_dimension': self.sub_dimension,
            'direction': self.direction,
            'sentiment': self.sentiment,
            'confidence_level': self.confidence_level
        }


@dataclass
class ExtractionResult:
    """Results from extracting events from an article."""
    news_id: int
    article_summary: str
    events: List[Event]
    errors: List[str] = field(default_factory=list)
    is_duplicate: bool = False
    raw_response: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0
    
    @property
    def event_count(self) -> int:
        return len(self.events)


class EventExtractor:
    """
    Coordinates event extraction from articles.
    
    Handles the full pipeline:
    1. Receive article data
    2. Send to analyzer for GPT processing
    3. Validate extracted events
    4. Store article and events in database
    """
    
    def __init__(self, analyzer: Optional[EventAnalyzer] = None, model: str = "gpt-4o"):
        """Initialize the extractor."""
        self.analyzer = analyzer or EventAnalyzer(model=model)
        self.country_mapper = get_mapper()
        
        try:
            self._valid_dimensions = set(get_valid_dimensions())
        except Exception:
            self._valid_dimensions = {
                'Political Relations', 'Material Conflict', 
                'Economic Relations', 'Other'
            }
    
    def extract_events(self, article: Dict[str, Any]) -> ExtractionResult:
        """Extract events from a single article."""
        errors = []
        
        # Check for duplicate
        url = article.get('source_url', '')
        if url:
            existing = get_article_by_url(url)
            if existing:
                return ExtractionResult(
                    news_id=existing['news_id'],
                    article_summary=existing.get('article_summary', ''),
                    events=[],
                    is_duplicate=True
                )
        
        # Extract fields
        news_title = article.get('news_title', article.get('headline', ''))
        news_text = article.get('news_text', article.get('article_text', ''))
        publication_date = article.get('publication_date', article.get('published_date', ''))
        source_country = article.get('source_country', '')
        
        if not news_text and not news_title:
            errors.append("Article has no title or text content")
            return ExtractionResult(news_id=0, article_summary='', events=[], errors=errors)
        
        # Insert article
        article_data = {
            'news_title': news_title,
            'news_text': news_text,
            'publication_date': publication_date,
            'source_url': url,
            'source_domain': article.get('source_domain', article.get('source', '')),
            'source_country': source_country,
            'language': article.get('language', 'en'),
            'language_detected': article.get('language_detected', '')
        }
        
        news_id = insert_article(article_data)
        
        if news_id is None:
            existing = get_article_by_url(url)
            return ExtractionResult(
                news_id=existing['news_id'] if existing else 0,
                article_summary='',
                events=[],
                is_duplicate=True
            )
        
        # Analyze
        try:
            analysis_result = self.analyzer.analyze_article(
                news_id=news_id,
                news_title=news_title,
                news_text=news_text,
                publication_date=publication_date,
                source_country=source_country
            )
        except Exception as e:
            errors.append(f"Analysis failed: {str(e)}")
            return ExtractionResult(news_id=news_id, article_summary='', events=[], errors=errors)
        
        if analysis_result.get('error'):
            errors.append(analysis_result['error'])
        
        raw_events = analysis_result.get('events', [])
        
        # Process events
        events = []
        for i, raw_event in enumerate(raw_events):
            try:
                event = self._create_event(raw_event, news_id, i + 1)
                if event:
                    events.append(event)
            except Exception as e:
                errors.append(f"Event {i+1} validation failed: {str(e)}")
        
        # Store events
        for event in events:
            try:
                event_id = insert_event(event.to_dict())
                if event_id:
                    insert_event_actors(event.event_id, event.actors)
            except Exception as e:
                errors.append(f"Database error for event {event.event_id}: {str(e)}")
        
        logger.info(f"Article {news_id}: Extracted {len(events)} events, stored {len(events)}")
        
        return ExtractionResult(
            news_id=news_id,
            article_summary='',
            events=events,
            errors=errors,
            raw_response=analysis_result.get('raw_response')
        )
    
    def _create_event(self, raw_event: Dict[str, Any], news_id: int, 
                      sequence: int) -> Optional[Event]:
        """Create and validate an Event object from raw data."""
        event_id = f"{news_id}-{sequence}"
        
        dimension = raw_event.get('dimension', 'Other')
        if dimension not in self._valid_dimensions:
            dimension = 'Other'
        
        direction = raw_event.get('direction', 'bilateral')
        if direction not in ('unilateral', 'bilateral', 'multilateral'):
            direction = 'bilateral'
        
        sentiment = raw_event.get('sentiment', 0)
        try:
            sentiment = max(-10, min(10, float(sentiment)))
        except (TypeError, ValueError):
            sentiment = 0
        
        actors = self._normalize_actors(raw_event)
        
        all_actors = set()
        for role_actors in actors.values():
            all_actors.update(role_actors)
        
        if len(all_actors) < 2:
            return None
        
        return Event(
            event_id=str(event_id),
            news_id=news_id,
            event_summary=raw_event.get('event_summary', '')[:400],
            event_date=raw_event.get('event_date', ''),
            dimension=dimension,
            sub_dimension=raw_event.get('sub_dimension', ''),
            direction=direction,
            sentiment=sentiment,
            confidence_level=raw_event.get('confidence_level', 0.8),
            actors=actors
        )
    
    def _normalize_actors(self, raw_event: Dict[str, Any]) -> Dict[str, List[str]]:
        """Normalize actor fields to proper format."""
        actors = {
            'actor1': [],
            'actor1_secondary': [],
            'actor2': [],
            'actor2_secondary': []
        }
        
        for role in actors.keys():
            raw_value = raw_event.get(role, [])
            
            if isinstance(raw_value, list):
                codes = raw_value
            elif isinstance(raw_value, str):
                codes = [c.strip() for c in raw_value.split(',') if c.strip()]
            else:
                codes = []
            
            normalized = []
            for code in codes:
                iso3 = self.country_mapper.get_iso3(code)
                if iso3:
                    normalized.append(iso3)
                elif len(code) == 3 and code.isalpha():
                    normalized.append(code.upper())
            
            actors[role] = normalized
        
        return actors


class BatchExtractor:
    """Handles batch processing of multiple articles."""
    
    def __init__(self, extractor: Optional[EventExtractor] = None,
                 batch_size: int = 10, delay_between: float = 1.0):
        """Initialize batch extractor."""
        self.extractor = extractor or EventExtractor()
        self.batch_size = batch_size
        self.delay_between = delay_between
        
        self.stats = {
            'articles_processed': 0,
            'articles_skipped_duplicate': 0,
            'events_extracted': 0,
            'events_stored': 0,
            'errors': 0
        }
    
    def process_articles(self, articles: List[Dict[str, Any]],
                         progress_callback: Optional[callable] = None) -> List[ExtractionResult]:
        """Process a list of articles in batches."""
        import time
        
        results = []
        total = len(articles)
        
        for i, article in enumerate(articles):
            if progress_callback:
                progress_callback(i + 1, total, article)
            
            try:
                result = self.extractor.extract_events(article)
                results.append(result)
                
                if result.is_duplicate:
                    self.stats['articles_skipped_duplicate'] += 1
                else:
                    self.stats['articles_processed'] += 1
                    self.stats['events_extracted'] += result.event_count
                    if result.success:
                        self.stats['events_stored'] += result.event_count
                    else:
                        self.stats['errors'] += len(result.errors)
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                self.stats['errors'] += 1
                results.append(ExtractionResult(
                    news_id=0, article_summary='', events=[], errors=[str(e)]
                ))
            
            if i < total - 1:
                time.sleep(self.delay_between)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset all statistics counters."""
        self.stats = {
            'articles_processed': 0,
            'articles_skipped_duplicate': 0,
            'events_extracted': 0,
            'events_stored': 0,
            'errors': 0
        }

