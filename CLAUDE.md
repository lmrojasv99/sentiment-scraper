# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # required for NER in intl_filter

# Run full pipeline (scrape → translate → filter → store → GPT classify)
python3 main.py
python3 main.py --days 3 --model gpt-4o-mini --batch-size 5
python3 main.py --test        # run with hardcoded test article (no scraping)
python3 main.py --reset-db    # drop and recreate database

# Test scrape → translate → filter → store without GPT
python3 test_article_storage.py --feeds 1 --articles 3

# Run REST API
python3 api.py
PORT=5001 python3 api.py
```

### `main.py` CLI options
| Flag | Default | Description |
|------|---------|-------------|
| `--days` / `-d` | 5 | Days to look back |
| `--batch-size` / `-b` | 10 | Articles per batch |
| `--delay` / `-w` | 1.5 | Seconds between API calls |
| `--model` / `-m` | gpt-4o | OpenAI model |
| `--reset-db` | false | Reset database |
| `--test` | false | Use test article |

## Architecture

The pipeline processes international news in five sequential stages:

```
RSS Feeds (src/data/RSS_feeds.csv)
    ↓
[1] SCRAPER      src/data/scraper.py       — feedparser + newspaper3k; returns headline, full text, date, URL, source_country
    ↓
[2] TRANSLATOR   src/utils/translator.py   — langdetect → MarianMT (Helsinki-NLP); 96 languages; direct AutoTokenizer/AutoModelForSeq2SeqLM with BATCH_SIZE=16
    ↓
[3] INT'L FILTER src/utils/intl_filter.py  — ≥1 IR keyword AND (≥2 countries OR 1 country+1 org); two-layer country detection; failing articles DISCARDED
    ↓
[4] DATABASE     src/data/database.py      — stores translated English text + language_detected; SQLite locally, PostgreSQL in production via DATABASE_URL
    ↓
[5] GPT ANALYSIS src/core/analyzer.py      — Plover methodology; extracts structured events with dimension, sentiment (-10 to +10), and actor roles
    ↓
[6] EVENT STORE  src/core/event_extractor.py — writes events + event_actors; one article → multiple events possible
```

### Key design decisions
- **Translation before filtering**: `intl_filter.py` and `country_mapper.py` always operate on translated English text.
- **Only passing articles are persisted**: the database never stores articles that fail the international filter.
- **Original non-English text is discarded**: only the English translation is stored in `articles.news_text`.
- **Actor roles**: `event_actors` rows use `actor_role` values `actor1`, `actor1_secondary`, `actor2`, `actor2_secondary` — actor1 is the initiator, actor2 is the target.
- **Country-only actors**: EU, NATO, UN and non-sovereign entities are excluded; only ISO3 sovereign state codes are valid.
- **Filter criterion (structural)**: ≥2 sovereign countries OR (≥1 country + ≥1 recognised international organisation). The org list (EU, NATO, ASEAN, BRICS, etc.) lives in `INTL_ORGS_MAP` in `intl_filter.py`.
- **Country detection uses two layers**: (a) pre-compiled alias/demonym regex in `CountryMapper` — 197 countries, unidecode-normalised; (b) spaCy NER GPE/LOC + `pycountry` lookup — catches proper nouns not in the alias list.
- **Translation engine**: direct `AutoTokenizer` + `AutoModelForSeq2SeqLM` (not HF `pipeline`) with `BATCH_SIZE=16` chunk batching; 96 languages; model IDs for Croatian, Greek, Lithuanian, Portuguese, Romanian, Nepali are patched in `TRANSLATION_MODELS` in `translator.py`. Device auto-selected: CUDA → MPS → CPU.

### Database schema (core tables)
- `articles` — scraped articles with `news_id` PK, `source_url` UNIQUE, `language_detected`
- `events` — extracted events with `event_id` UNIQUE (e.g. "123-1"), FK to `news_id`; fields: `dimension`, `sub_dimension`, `sentiment` (−10 to +10), `direction` (unilateral/bilateral/multilateral)
- `event_actors` — one row per actor per event; `actor_iso3` + `actor_role`
- `dimensions_taxonomy` — reference table of valid dimension/sub_dimension pairs
- `countries_reference` — ISO3 → country_name + aliases JSON

### Dimensions taxonomy
Four top-level dimensions: **Political Relations**, **Material Conflict**, **Economic Relations**, **Other**. See `sql/schema.sql` for the full sub-dimension list.

### Environment / configuration
- New dependencies: `pycountry` (NER country lookup) and `unidecode` (accent-insensitive matching) — both in `requirements.txt`
- Required: `OPENAI_API_KEY` in `.env`
- Optional: `DATABASE_URL` (PostgreSQL connection string; defaults to SQLite at `data/geopolitical_monitor.db`)
- RSS feeds loaded from `src/data/RSS_feeds.csv` (columns: `RSS_Feed`, `Country`); falls back to hardcoded list if missing
- All settings centralized in `config/settings.py`

### API endpoints (`api.py`, Flask)
- `GET /stats` — database statistics
- `GET /articles` — paginated article list (`?limit=50&offset=0`)
- `GET /articles/<id>` — article with its events
- `GET /events` — event list with filtering (`?dimension=...`)
- `GET /events/<id>` — event with actors
- `POST /query` — custom SELECT-only SQL (prefix-checked)
- `GET /full-export` — full JSON export (default limit 1000)

### Non-obvious implementation details

**Article field normalization**: Scraper outputs `headline`, `article_text`, `source`; the DB and GPT analyzer expect `news_title`, `news_text`, `source_domain`. `EventExtractor._normalize_article_fields()` maps these on ingestion — don't rename scraper output keys.

**Duplicate detection**: `insert_article()` returns `None` on duplicate (caught via UNIQUE constraint on `source_url`). `EventExtractor` checks for `None` and sets `ExtractionResult.is_duplicate=True`, skipping GPT analysis. Duplicates are counted in batch stats but never analyzed.

**Batch error handling**: Per-article errors in `BatchExtractor` are appended to `ExtractionResult.errors` (not raised). A failed article does not stop the batch; `errors`/`events_extracted`/`events_stored` are tracked separately in the returned stats dict.

**Translation chunking**: Text is split sentence-aware at 512 chars (`MAX_CHUNK_CHARS`). Sentences >512 chars are hard-split. Forward passes run in batches of 16 chunks. If a model is missing for a language, the original text is returned (logged as info, not error).

**spaCy NER lazy loading**: The `en_core_web_sm` model is loaded on the first `passes_international_filter()` call. If the model is absent, NER layer is disabled (only alias-regex matching works) — no exception is raised, but country recall drops.

**Sentiment scoring scale** (used in GPT system prompt and validation):

| Range | Category |
|-------|----------|
| −10 to −7 | Severe hostility (war, invasion) |
| −6 to −4 | Significant tension (sanctions, military threats) |
| −3 to −1 | Mild negativity (protests, trade disputes) |
| 0 | Neutral (routine meetings) |
| +1 to +3 | Mild positivity (dialogue, cultural exchange) |
| +4 to +6 | Significant cooperation (trade deals, defense pacts) |
| +7 to +10 | Major breakthrough (peace treaties) |

**Deprecated schema fields**: `articles.article_summary`, `events.event_location`, and `events.event_type` exist in `sql/schema.sql` but are never written by any pipeline stage — do not rely on them.

**Logging**: Pipeline logs to both `agent.log` (file) and stdout at INFO level. Adjust in `main.py` `logging.basicConfig()`.

**Pre-built SQL queries**: `sql/queries.sql` contains ~30 reference queries for stats, actor analysis, country-pair interactions, sentiment trends, and network-analysis edge/node lists. These are not called by code — analyst reference only.

**Database portability**: `_execute_query()` in `database.py` auto-converts `?` → `%s` for Postgres and uses `RealDictCursor` vs `sqlite3.Row` accordingly. Always use `?` placeholders in new queries; do not write Postgres-specific SQL.
