# Global International Relations Monitor v2.0

## Event-Centric Analysis Pipeline Based on Plover Methodology

An automated pipeline for collecting, processing, and analyzing international news articles with multi-event extraction using GPT-4o.

---

## Project Structure

```
Sentiment_Scraper/
├── main.py                    # Entry point & CLI
├── requirements.txt           # Dependencies
├── README.md                  # Documentation
├── .env                       # API configuration
├── .env.example               # Example env file
│
├── config/                    # Configuration
│   ├── __init__.py
│   └── settings.py            # Centralized settings
│
├── src/                       # Source code
│   ├── __init__.py
│   ├── core/                  # Core business logic
│   │   ├── __init__.py
│   │   ├── analyzer.py        # GPT-4o event analysis
│   │   └── event_extractor.py # Event processing
│   ├── data/                  # Data handling
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite operations
│   │   └── scraper.py         # RSS feed scraping
│   └── utils/                 # Utilities
│       ├── __init__.py
│       └── country_mapper.py  # ISO3 code mapping
│
├── sql/                       # SQL files
│   ├── schema.sql             # Database schema
│   └── queries.sql            # Analysis queries
│
├── data/                      # Data storage
│   └── geopolitical_monitor.db
│
└── notebooks/                 # Jupyter notebooks
    └── analysis.ipynb         # Data analysis
```

---

## Quick Start

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

### Usage

```bash
# Run full pipeline (5 days of news)
python3 main.py

# Run with specific options
python3 main.py --days 3 --model gpt-4o-mini

# Test with sample article
python3 main.py --test

# Reset database
python3 main.py --reset-db
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--days`, `-d` | Days to look back | 5 |
| `--batch-size`, `-b` | Batch size | 10 |
| `--delay`, `-w` | Delay between API calls | 1.5 |
| `--model`, `-m` | Model (gpt-4o, gpt-4o-mini) | gpt-4o |
| `--reset-db` | Reset database | False |
| `--test` | Run with test article | False |

---

## Key Features

### Multi-Event Extraction
- Extracts **multiple distinct events** from each article
- Uses Plover methodology for standardized classification
- Assigns actor roles (initiator vs target)

### Sentiment Scale (-10 to +10)
| Range | Category | Examples |
|-------|----------|----------|
| +7 to +10 | Extremely Positive | Peace treaties |
| +3 to +6 | Positive | Cooperation deals |
| -2 to +2 | Neutral | Routine meetings |
| -6 to -3 | Negative | Sanctions |
| -10 to -7 | Extremely Negative | Wars |

### Plover Taxonomy

| Dimension | Sub-dimensions |
|-----------|----------------|
| Political Relations | political, government, election, diplomatic, legal, refugee |
| Material Conflict | military, terrorism, cbrn, cyber |
| Economic Relations | trade, aid, investment, resources, technology_transfer |
| Other | disease, disaster, historical, culture |

---

## Database Schema

```sql
-- Main tables
articles (news_id, news_title, news_text, article_summary, ...)
events (event_id, news_id, event_summary, dimension, sentiment, ...)
event_actors (event_id, actor_iso3, actor_role)
dimensions_taxonomy (dimension, sub_dimension, description)
countries_reference (iso3, country_name, aliases)
```

### Query Examples

```bash
# Run predefined queries
sqlite3 -header -column data/geopolitical_monitor.db < sql/queries.sql

# Interactive mode
sqlite3 data/geopolitical_monitor.db
```

```sql
-- All events with actors
SELECT e.event_id, e.event_summary, e.sentiment,
       GROUP_CONCAT(ea.actor_iso3) as actors
FROM events e
JOIN event_actors ea ON e.event_id = ea.event_id
GROUP BY e.event_id;

-- Events by dimension
SELECT dimension, COUNT(*) as count, AVG(sentiment) as avg_sentiment
FROM events GROUP BY dimension;
```

---

## Python API

```python
from src.core.analyzer import EventAnalyzer
from src.core.event_extractor import EventExtractor
from src.data.database import init_db, get_statistics

# Initialize
init_db()
analyzer = EventAnalyzer(model="gpt-4o")
extractor = EventExtractor(analyzer=analyzer)

# Process article
result = extractor.extract_events({
    'headline': 'US-China Trade Talks',
    'article_text': '...',
    'source_url': 'https://...'
})

print(f"Extracted {result.event_count} events")
for event in result.events:
    print(f"  {event.event_id}: {event.sentiment:+.0f}")
```

---

## Configuration

Settings are centralized in `config/settings.py`:

```python
from config.settings import get_settings

settings = get_settings()
print(settings.openai_model)      # gpt-4o
print(settings.db_path)           # data/geopolitical_monitor.db
print(settings.scraper_days_lookback)  # 5
```

### Environment Variables

```bash
# .env file
OPENAI_API_KEY=sk-your-api-key-here
```

---

## Module Overview

### `src/core/analyzer.py`
- `EventAnalyzer` - GPT-4o interface for event extraction
- Plover-based system prompt
- Response parsing and validation

### `src/core/event_extractor.py`
- `EventExtractor` - Single article processing
- `BatchExtractor` - Batch processing with progress tracking
- `Event`, `ExtractionResult` - Data classes

### `src/data/database.py`
- `init_db()` - Initialize schema
- `insert_article()`, `insert_event()` - Data insertion
- `get_events_by_*()` - Query functions
- `get_statistics()` - Summary stats

### `src/data/scraper.py`
- `NewsScraper` - RSS feed scraping
- Relevance filtering
- Article content extraction

### `src/utils/country_mapper.py`
- `CountryMapper` - ISO3 code mapping
- 150+ countries with aliases
- Demonym recognition

---