# Global International Relations Monitor v2.0

## Event-Centric Analysis Pipeline Based on Plover Methodology

An automated pipeline for collecting, translating, filtering, and analyzing international news articles with multi-event extraction using GPT-4o.

### Pipeline Overview

1. **Scrape** — RSS feeds (with `source_country` from CSV); full article text, date, source, link; no pre-scrape relevance filter.
2. **Translate** — Non-English articles translated to English via MarianMT (Helsinki-NLP); language detected with `langdetect`.
3. **Filter** — International-context filter: at least one keyword (e.g. diplomacy, trade, sanctions) and **≥2 distinct countries** in the text. Only articles that pass are kept.
4. **Store** — Only passing articles are inserted into the database (translated English text, `language_detected`, `source_country`).
5. **Classify** — GPT-4o extracts events (dimension, actors, sentiment); reduced fields (no `article_summary`, `event_location`, `event_type`).
6. **Store events** — Events and actor roles written to the DB.

---

## Project Structure

```
Sentiment_Scraper/
├── main.py                    # Entry point & pipeline orchestrator
├── api.py                     # Flask REST API
├── requirements.txt           # Dependencies
├── test_article_storage.py    # Local test: scrape → translate → filter → store (no GPT)
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
│   │   ├── analyzer.py        # GPT-4o event analysis (Plover)
│   │   └── event_extractor.py # Event processing & DB writes
│   ├── data/                  # Data handling
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite & PostgreSQL
│   │   ├── scraper.py         # RSS feed scraping
│   │   ├── RSS_feeds.csv      # Feed URLs + Country column
│   │   └── keywords.csv       # (optional, for reference)
│   └── utils/                 # Utilities
│       ├── __init__.py
│       ├── country_mapper.py  # ISO3 code mapping
│       ├── translator.py      # MarianMT translation (Helsinki-NLP)
│       └── intl_filter.py     # International-context filter (keywords + countries)
│
├── sql/                       # SQL files
│   ├── schema.sql             # Database schema
│   └── queries.sql            # Analysis queries
│
├── data/                      # Data storage (gitignored)
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

# Install dependencies (includes transformers, torch, spacy, langdetect for translation)
pip install -r requirements.txt

# Download spaCy model for sentence-aware chunking in translation
python -m spacy download en_core_web_sm

# Configure API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

MarianMT models (e.g. `Helsinki-NLP/opus-mt-*-en`) are downloaded automatically on first use per language.

### Usage

```bash
# Run full pipeline (scrape → translate → filter → store → GPT)
python3 main.py

# Run with specific options
python3 main.py --days 3 --model gpt-4o-mini

# Test article storage only (no GPT): scrape a few articles, translate, filter, store
python3 test_article_storage.py --feeds 1 --articles 3

# Test with sample article (full GPT extraction)
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

### Translation (MarianMT)
- Detects language with `langdetect`; supports 40+ languages via Helsinki-NLP `opus-mt-*-en` models.
- Sentence-aware chunking (spaCy) for long texts; full article and title translated to English before filtering and storage.

### International-Context Filter
- **Keyword criterion:** At least one term from a fixed list (e.g. diplomacy, trade, sanctions, NATO, refugee, treaty).
- **Country criterion:** At least **two distinct sovereign countries** (ISO3) in the text, via `CountryMapper`.
- Runs on **translated English** text; only articles passing both criteria are stored and sent to GPT.

### Scraper
- Loads RSS feeds from `src/data/RSS_feeds.csv` with a **Country** column; each article gets `source_country`.
- No pre-scrape relevance filter; full article text fetched. Filtering happens after translation.

### Multi-Event Extraction
- Extracts **multiple distinct events** from each article.
- Uses Plover methodology for standardized classification.
- Assigns actor roles (initiator vs target). GPT output no longer includes `article_summary`, `event_location`, or `event_type` (reduced token usage).

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

- **articles:** `news_id`, `news_title`, `news_text`, `publication_date`, `source_url`, `source_domain`, `source_country`, `language`, `language_detected`, `date_scraped`. (`article_summary` column exists but is no longer populated.)
- **events:** `event_id`, `news_id`, `event_summary`, `event_date`, `dimension`, `sub_dimension`, `direction`, `sentiment`, `confidence_level`. (`event_location`, `event_type` columns exist but are no longer populated.)
- **event_actors:** `event_id`, `actor_iso3`, `actor_role`.
- **dimensions_taxonomy**, **countries_reference:** Reference data.

Supports **SQLite** (local) and **PostgreSQL** (e.g. production via `DATABASE_URL`). A migration runs on `init_db()` to add `language_detected` to existing databases.

### Query examples

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
from src.utils.translator import get_translator, translate_article
from src.utils.intl_filter import passes_international_filter

# Initialize
init_db()
analyzer = EventAnalyzer(model="gpt-4o")
extractor = EventExtractor(analyzer=analyzer)

# Translate (optional, if not already English)
tr = translate_article("El presidente de México viajó a Washington.", "Reunión bilateral")
# tr['translated_text'], tr['translated_title'], tr['language_detected'], tr['was_translated']

# Filter
passes, details = passes_international_filter(tr['translated_text'], tr['translated_title'])
# details: keywords_found, countries_found, keyword_pass, country_pass

# Process article (expects translated English; stores with language_detected if provided)
result = extractor.extract_events({
    'headline': 'US-China Trade Talks',
    'article_text': '...',
    'source_url': 'https://...',
    'source_country': 'USA',
    'language_detected': 'en'
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

# Optional: PostgreSQL (if set, used instead of SQLite)
DATABASE_URL=postgres://user:pass@host:5432/dbname
```

---

## REST API

The project includes a Flask API for querying the database. It supports both PostgreSQL (production) and SQLite (local development).

### Running the API

```bash
# Local development (uses SQLite)
python3 api.py

# Or specify a custom port
PORT=5001 python3 api.py

# Production (uses PostgreSQL via DATABASE_URL)
DATABASE_URL=postgres://... python3 api.py
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info and available endpoints |
| `/stats` | GET | Database statistics (counts, averages) |
| `/articles` | GET | List articles (`?limit=N&offset=N`) |
| `/articles/<id>` | GET | Get article by ID with its events |
| `/events` | GET | List events (`?limit=N&offset=N&dimension=X`) |
| `/events/<id>` | GET | Get event by ID with actors |
| `/query` | POST | Run custom SQL query (`{"sql": "SELECT ..."}`) |
| `/full-export` | GET | Export all events with full data (`?limit=N`) |

### Example Requests

```bash
# Get database statistics
curl http://127.0.0.1:5000/stats

# Get recent articles
curl "http://127.0.0.1:5000/articles?limit=10"

# Get events filtered by dimension
curl "http://127.0.0.1:5000/events?dimension=Economic%20Relations&limit=20"

# Get full article with events
curl http://127.0.0.1:5000/articles/83

# Export all data to JSON
curl "http://127.0.0.1:5000/full-export?limit=1000" > data_export.json

# Run custom query
curl -X POST http://127.0.0.1:5000/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT dimension, COUNT(*) FROM events GROUP BY dimension"}'
```

---

## Module Overview

### `main.py`
- Orchestrates pipeline: scrape → translate → filter → store (only passers) → GPT → store events.
- Uses `get_translator()`, `passes_international_filter()`, then `BatchExtractor.process_articles()` on filtered articles.

### `src/core/analyzer.py`
- `EventAnalyzer` — GPT-4o interface for event extraction; Plover-based system prompt.
- Output: events only (no `article_summary`, `event_location`, `event_type`); response parsing and validation.

### `src/core/event_extractor.py`
- `EventExtractor` — Single-article processing (insert article, call analyzer, insert events).
- `BatchExtractor` — Batch processing with progress callback.
- `Event`, `ExtractionResult` — Data classes (no `event_location`/`event_type`).

### `src/data/database.py`
- `init_db()` — Create tables, run migrations (e.g. add `language_detected`), populate taxonomy/countries.
- `insert_article()` — Writes `language_detected`; supports SQLite and PostgreSQL.
- `insert_event()`, `insert_event_actors()` — Event storage (no `event_location`/`event_type`).
- `get_events_by_*()`, `get_statistics()` — Query helpers.

### `src/data/scraper.py`
- `NewsScraper` — Loads feeds from CSV (columns `RSS_Feed`, `Country`); returns list of `{url, country}`.
- Fetches full article text; no in-scraper relevance filter (filtering after translation in `intl_filter`).
- Each article dict includes `source_country`, `headline`, `article_text`, `published_date`, `source`, `source_url`.

### `src/utils/translator.py`
- `ArticleTranslator` / `get_translator()` — MarianMT (Helsinki-NLP) translation to English.
- Language detection via `langdetect`; sentence chunking via spaCy; per-language pipeline cache.
- `translate_article(text, title)` returns `translated_text`, `translated_title`, `language_detected`, `was_translated`.

### `src/utils/intl_filter.py`
- `passes_international_filter(text, title, min_countries=2)` — Requires ≥1 keyword and ≥2 distinct countries (ISO3).
- Uses `CountryMapper.extract_countries_from_text()`; returns `(passes: bool, details: dict)`.

### `src/utils/country_mapper.py`
- `CountryMapper` / `get_mapper()` — ISO3 mapping; 150+ countries with aliases; `extract_countries_from_text()`.

---