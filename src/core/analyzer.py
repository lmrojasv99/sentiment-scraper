"""
Analyzer Module V2 - Global International Relations Event Extractor
Based on Plover Methodology for Multi-Event Extraction

Uses GPT-4o with structured prompting to extract multiple international
events from news articles, including actor roles and sentiment scoring.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

from src.utils.country_mapper import get_mapper

load_dotenv()

logger = logging.getLogger(__name__)


# Plover-based System Prompt for International Relations Analysis
SYSTEM_PROMPT = """
You are an international relations analyst and extractor trained in the Plover methodology. Your task is to identify and structure international events from news articles, using the schema below.

Return **only** a JSON array of international events. Do not explain, describe, comment, or include any keys or data not explicitly requested. If no valid event with two or more countries is found, return an empty array [].

### INPUT FORMAT (ARTICLE OBJECT)

You will receive a JSON article object with metadata (text, title, country, date, etc.)

### TASKS

1. **Summarize the article**
- Read the full article content.
- Write one concise summary (maximum 500 characters) that captures the main idea or purpose of the article (`article_summary`).
- If the article describes multiple international events, ensure the summary reflects all of them collectively.

#### FOR EACH IDENTIFIED INTERNATIONAL EVENT

2. **Extract countries (`actor_list`)**
- **Entity filtering:** Include **only** sovereign states. Ignore organizations (e.g., EU, NATO), companies, NGOs, sub-national entities, etc.
- **ISO-3 mapping & deduplication:** Convert each unique mention to its ISO-3 code; remove duplicates and sort alphabetically.

3. **Extract international events**
- Identify all **distinct international events** involving **two or more countries**.
- For each event:
  - Assign a unique event_id in the format: news_id-1, news_id-2, etc.
  - Extract or infer event_date (YYYY-MM-DD); use article publish date if unclear.
  - Extract location (city or country) if mentioned; else leave as empty string "".
  - Write a concise event_summary (≤ 400 characters) describing the international interaction.

4. **Classify each event**
- Assign dimension and sub_dimension based on this mapping:

| Dimension | Subdimensions |
|-----------|---------------|
| Political Relations | political, government, election, legislative, diplomatic, legal, refugee |
| Material Conflict | military, terrorism, cbrn, cyber |
| Economic Relations | economic, trade, aid, capital_flows, strategic_economic, financial_monetary, development, taxation_fiscal, investment, resources, labour_migration, technology_transfer |
| Other | resource, disease, disaster, historical, hypothetical, culture |

5. **Assign country roles (per event)**
- `actor1`: Country/countries driving the action
- `actor2`: Country/countries targeted by the action
- `actor1_secondary`: Countries supporting actor1
- `actor2_secondary`: Countries aligned with actor2

6. **Establish direction**
- "unilateral": One actor acts upon another
- "bilateral": Symmetric action/interaction
- "multilateral": Several countries involved

7. **Score sentiment**
- Assign a **sentiment** value on a **-10 to +10** scale:
  - **-10 to -8**: Extremely negative (war, invasion)
  - **-5 to -3**: Negative (sanctions, expulsions)
  - **0**: Neutral
  - **+3 to +5**: Positive (cooperation deals)
  - **+7 to +10**: Extremely positive (peace agreements)

### OUTPUT FORMAT

Return a **JSON array** of events:

```json
[
  {
    "article_summary": "article summary",
    "event_id": "news_id-1",
    "event_date": "YYYY-MM-DD",
    "event_location": "<city or country or ''>",
    "event_summary": "<concise event description>",
    "event_type": "<event type>",
    "dimension": "<dimension>",
    "sub_dimension": "<subdimension>",
    "actor_list": ["ISO3", ...],
    "actor1": "ISO3 or multiple",
    "actor1_secondary": "ISO3 or multiple or ''",
    "actor2": "ISO3 or multiple or ''",
    "actor2_secondary": "ISO3 or multiple or ''",
    "direction": "unilateral | bilateral | multilateral",
    "sentiment": <integer from -10 to 10>
  }
]
```

- If no valid international event is found, return: []
- Do **not invent** countries or data not present in the article.
"""


class EventAnalyzer:
    """
    Analyzes articles using GPT-4o for multi-event extraction
    based on the Plover methodology for international relations.
    """
    
    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        """
        Initialize the analyzer.
        
        Args:
            model: OpenAI model to use (default: gpt-4o)
            api_key: Optional API key (defaults to env var)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.country_mapper = get_mapper()
        
        self.temperature = 0
        self.max_tokens = 4096
        self.top_p = 1
    
    def analyze_article(
        self,
        news_id: int,
        news_title: str,
        news_text: str,
        publication_date: str = "",
        source_country: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze an article and extract international events.
        
        Returns:
            Dictionary containing article_summary, events list, and error if any
        """
        article_input = self._prepare_article_input(
            news_id, news_title, news_text, publication_date, source_country
        )
        
        try:
            raw_response = self._call_openai(article_input)
            events = self._parse_response(raw_response, news_id, publication_date)
            
            article_summary = events[0].get('article_summary', '') if events else ''
            
            return {
                'article_summary': article_summary,
                'events': events,
                'raw_response': raw_response,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Analysis failed for article {news_id}: {e}")
            return {
                'article_summary': '',
                'events': [],
                'raw_response': None,
                'error': str(e)
            }
    
    def _prepare_article_input(self, news_id: int, title: str, text: str, 
                                date: str, source_country: str) -> str:
        """Prepare article as JSON input for GPT."""
        truncated_text = text[:6000] if len(text) > 6000 else text
        
        article_obj = {
            "news_id": news_id,
            "title": title,
            "text": truncated_text,
            "publication_date": date,
            "source_country": source_country
        }
        
        return json.dumps(article_obj, ensure_ascii=False)
    
    def _call_openai(self, article_json: str) -> str:
        """Call OpenAI API for structured event extraction."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": article_json}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            response_format={"type": "json_object"}
        )
        
        return response.choices[0].message.content
    
    def _parse_response(self, raw_response: str, news_id: int, 
                        default_date: str) -> List[Dict[str, Any]]:
        """Parse and validate the GPT response."""
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return []
        
        if isinstance(parsed, list):
            events = parsed
        elif isinstance(parsed, dict):
            events = parsed.get('events', [parsed] if 'event_id' in parsed else [])
        else:
            events = []
        
        validated_events = []
        for i, event in enumerate(events):
            validated = self._validate_event(event, news_id, i + 1, default_date)
            if validated:
                validated_events.append(validated)
        
        return validated_events
    
    def _validate_event(self, event: Dict[str, Any], news_id: int, 
                        sequence: int, default_date: str) -> Optional[Dict[str, Any]]:
        """Validate and normalize a single event object."""
        if not isinstance(event, dict):
            return None
        
        event_id = f"{news_id}-{sequence}"
        
        # Validate dimension
        valid_dimensions = {'Political Relations', 'Material Conflict', 'Economic Relations', 'Other'}
        dimension = event.get('dimension', 'Other')
        if dimension not in valid_dimensions:
            dimension = 'Other'
        
        # Validate direction
        direction = event.get('direction', 'bilateral')
        if direction not in ('unilateral', 'bilateral', 'multilateral'):
            direction = 'bilateral'
        
        # Validate sentiment
        sentiment = event.get('sentiment', 0)
        try:
            sentiment = max(-10, min(10, float(sentiment)))
        except (TypeError, ValueError):
            sentiment = 0
        
        # Normalize actors
        actor_list = self._normalize_actors(event.get('actor_list', []))
        actor1 = self._normalize_actor_field(event.get('actor1', ''))
        actor1_secondary = self._normalize_actor_field(event.get('actor1_secondary', ''))
        actor2 = self._normalize_actor_field(event.get('actor2', ''))
        actor2_secondary = self._normalize_actor_field(event.get('actor2_secondary', ''))
        
        all_actors = set(actor_list + actor1 + actor1_secondary + actor2 + actor2_secondary)
        if len(all_actors) < 2:
            logger.warning(f"Event {event_id} has fewer than 2 countries, skipping")
            return None
        
        return {
            'event_id': str(event_id),
            'news_id': news_id,
            'article_summary': event.get('article_summary', '')[:500],
            'event_summary': event.get('event_summary', '')[:400],
            'event_date': event.get('event_date', default_date) or default_date,
            'event_location': event.get('event_location', ''),
            'dimension': dimension,
            'event_type': event.get('event_type', ''),
            'sub_dimension': event.get('sub_dimension', ''),
            'direction': direction,
            'sentiment': sentiment,
            'confidence_level': 0.8,
            'actor_list': actor_list,
            'actor1': actor1,
            'actor1_secondary': actor1_secondary,
            'actor2': actor2,
            'actor2_secondary': actor2_secondary
        }
    
    def _normalize_actors(self, actors: Any) -> List[str]:
        """Normalize actor_list to list of ISO3 codes."""
        if not actors:
            return []
        
        if isinstance(actors, str):
            actors = actors.strip('[]').replace("'", "").replace('"', '')
            actors = [a.strip() for a in actors.split(',')]
        
        normalized = []
        for actor in actors:
            if isinstance(actor, str) and actor.strip():
                code = self.country_mapper.get_iso3(actor.strip())
                if code:
                    normalized.append(code)
                elif len(actor.strip()) == 3:
                    normalized.append(actor.strip().upper())
        
        return list(set(normalized))
    
    def _normalize_actor_field(self, field: Any) -> List[str]:
        """Normalize actor field to list of ISO3 codes."""
        if not field:
            return []
        if isinstance(field, list):
            return self._normalize_actors(field)
        if isinstance(field, str):
            parts = field.replace(',', ' ').split()
            return self._normalize_actors(parts)
        return []

