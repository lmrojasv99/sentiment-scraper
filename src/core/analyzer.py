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
SYSTEM_PROMPT = """You are an expert international relations analyst using the Plover methodology. Extract and structure international events from news articles.

<critical_rules>
- Return ONLY valid JSON with an "events" array
- Include ONLY sovereign states (no organizations like EU, NATO, UN, or companies)
- Require at least TWO distinct countries for a valid event
- Use ISO 3166-1 alpha-3 codes (USA, GBR, CHN, RUS, DEU, FRA, JPN, etc.)
- Never invent or assume data not present in the article
- If no valid international event exists, return: {"events": []}
</critical_rules>

<input>
You receive a JSON object: {"news_id", "title", "text", "publication_date", "source_country"}
</input>

<extraction_steps>

## Step 1: Identify Events
Find all DISTINCT international interactions involving 2+ sovereign states. Each unique action/interaction = separate event.

## Step 2: Classify Each Event

**Dimension → Sub-dimensions:**
| Dimension | Sub-dimensions |
|-----------|----------------|
| Political Relations | diplomatic, government, election, legislative, political, legal, refugee |
| Material Conflict | military, terrorism, cbrn, cyber |
| Economic Relations | trade, investment, aid, capital_flows, financial_monetary, development, taxation_fiscal, resources, labour_migration, technology_transfer, strategic_economic, economic |
| Other | disaster, disease, resource, historical, hypothetical, culture |

## Step 3: Assign Actor Roles (all in ISO-3 codes)
- **actor1**: Primary actor(s) INITIATING/DRIVING the action
- **actor2**: Primary actor(s) RECEIVING/TARGETED by the action
- **actor1_secondary**: Supporting/allied countries backing actor1 (empty string if none)
- **actor2_secondary**: Supporting/allied countries backing actor2 (empty string if none)
- **actor_list**: All unique countries involved, sorted alphabetically

## Step 4: Determine Direction
- **unilateral**: One-way action (A acts upon B, no reciprocity)
- **bilateral**: Two-way symmetric interaction (A and B mutually engage)
- **multilateral**: 3+ countries jointly participating in coordinated action

## Step 5: Score Sentiment (-10 to +10)
| Score | Meaning | Examples |
|-------|---------|----------|
| -10 to -7 | Severe hostility | War declaration, invasion, armed conflict, genocide |
| -6 to -4 | Significant tension | Sanctions, military threats, embassy closures, asset freezes |
| -3 to -1 | Mild negativity | Diplomatic protests, trade disputes, critical statements |
| 0 | Neutral | Routine meetings, procedural announcements, factual reports |
| +1 to +3 | Mild positivity | Dialogue initiation, cultural exchanges, minor agreements |
| +4 to +6 | Significant cooperation | Trade deals, defense pacts, economic partnerships |
| +7 to +10 | Major breakthrough | Peace treaties, war endings, historic reconciliations |

</extraction_steps>

<output_schema>
```json
{
  "events": [
    {
      "event_id": "string (format: news_id-N where N is sequence number)",
      "event_date": "string (YYYY-MM-DD, infer from article or use publication_date)",
      "event_summary": "string (max 400 chars, specific to THIS event)",
      "dimension": "string (one of: Political Relations, Material Conflict, Economic Relations, Other)",
      "sub_dimension": "string (from dimension's sub-dimension list)",
      "actor_list": ["ISO3", "ISO3"],
      "actor1": "string (ISO3 code(s), space-separated if multiple)",
      "actor2": "string (ISO3 code(s), space-separated if multiple)",
      "actor1_secondary": "string (ISO3 code(s) or empty string)",
      "actor2_secondary": "string (ISO3 code(s) or empty string)",
      "direction": "string (unilateral|bilateral|multilateral)",
      "sentiment": "integer (-10 to +10)"
    }
  ]
}
```
</output_schema>

<example>
INPUT:
{"news_id": 12345, "title": "US Imposes New Sanctions on Russia Over Ukraine", "text": "Washington announced sweeping sanctions against Russian banks and officials on Monday, citing continued aggression in Ukraine. The European Union voiced support for the measures, while China criticized the unilateral action.", "publication_date": "2024-03-15", "source_country": "USA"}

OUTPUT:
{
  "events": [
    {
      "event_id": "12345-1",
      "event_date": "2024-03-15",
      "event_summary": "United States imposes sweeping sanctions against Russian banks and officials in response to continued Russian aggression in Ukraine.",
      "dimension": "Economic Relations",
      "sub_dimension": "financial_monetary",
      "actor_list": ["RUS", "UKR", "USA"],
      "actor1": "USA",
      "actor2": "RUS",
      "actor1_secondary": "",
      "actor2_secondary": "",
      "direction": "unilateral",
      "sentiment": -5
    },
    {
      "event_id": "12345-2",
      "event_date": "2024-03-15",
      "event_summary": "China publicly criticizes US sanctions against Russia, opposing what it characterizes as unilateral coercive measures.",
      "dimension": "Political Relations",
      "sub_dimension": "diplomatic",
      "actor_list": ["CHN", "USA"],
      "actor1": "CHN",
      "actor2": "USA",
      "actor1_secondary": "",
      "actor2_secondary": "",
      "direction": "unilateral",
      "sentiment": -2
    }
  ]
}
</example>

Now analyze the provided article and extract all international events."""


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
            
            return {
                'article_summary': '',
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
            'event_summary': event.get('event_summary', '')[:400],
            'event_date': event.get('event_date', default_date) or default_date,
            'dimension': dimension,
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

