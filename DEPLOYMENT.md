# Render Deployment Guide

This document explains the cloud deployment architecture for the Global International Relations Monitor on Render.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RENDER PLATFORM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                      ┌─────────────────────────────┐  │
│  │   CRON JOB       │                      │   POSTGRESQL DATABASE       │  │
│  │   sentiment-     │  ───── INSERT ─────▶ │   sentiment-scraper-db      │  │
│  │   scraper        │                      │                             │  │
│  │                  │                      │   Tables:                   │  │
│  │   Schedule:      │                      │   - articles                │  │
│  │   Every 6 hours  │                      │   - events                  │  │
│  │   (0 */6 * * *)  │                      │   - event_actors            │  │
│  │                  │                      │   - dimensions_taxonomy     │  │
│  │   Runs:          │                      │   - countries_reference     │  │
│  │   python main.py │                      │                             │  │
│  └──────────────────┘                      └─────────────────────────────┘  │
│                                                        │                     │
│                                                        │                     │
│                                                   QUERY (internal)           │
│                                                        │                     │
│                                                        ▼                     │
│                                            ┌─────────────────────────────┐  │
│                                            │   WEB SERVICE (API)         │  │
│                                            │   sentiment-scraper-api     │  │
│                                            │                             │  │
│                                            │   Endpoints:                │  │
│                                            │   - GET /stats              │  │
│                                            │   - GET /articles           │  │
│                                            │   - GET /events             │  │
│                                            │   - GET /full-export        │  │
│                                            │   - POST /query             │  │
│                                            │                             │  │
│                                            │   URL:                      │  │
│                                            │   sentiment-scraper-api-    │  │
│                                            │   ffga.onrender.com         │  │
│                                            └─────────────────────────────┘  │
│                                                        │                     │
└────────────────────────────────────────────────────────│─────────────────────┘
                                                         │
                                                    HTTPS (external)
                                                         │
                                                         ▼
                                            ┌─────────────────────────────┐
                                            │   YOUR LOCAL MACHINE        │
                                            │                             │
                                            │   - curl commands           │
                                            │   - Python scripts          │
                                            │   - Jupyter notebooks       │
                                            │   - Any HTTP client         │
                                            └─────────────────────────────┘
```

---

## Render Resources

| Resource | Name | URL | Purpose |
|----------|------|-----|---------|
| **Postgres** | sentiment-scraper-db | [Dashboard](https://dashboard.render.com/d/dpg-d5uf38e3jp1c739uq0jg-a) | Stores articles and events |
| **Cron Job** | sentiment-scraper | [Dashboard](https://dashboard.render.com/cron/crn-d5uf3fiqcgvc73aulcqg) | Scrapes news every 6 hours |
| **Web Service** | sentiment-scraper-api | https://sentiment-scraper-api-ffga.onrender.com | REST API for queries |

---

## Environment Variables

### Cron Job (`sentiment-scraper`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Internal Postgres connection URL |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o analysis |

### Web Service (`sentiment-scraper-api`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Internal Postgres connection URL |

---

## API Reference

Base URL: `https://sentiment-scraper-api-ffga.onrender.com`

### GET /

Returns API information and available endpoints.

```bash
curl https://sentiment-scraper-api-ffga.onrender.com/
```

**Response:**
```json
{
  "name": "Sentiment Scraper API",
  "endpoints": {
    "/stats": "Database statistics",
    "/articles": "List articles (query params: limit, offset)",
    "/articles/<id>": "Get article by ID",
    "/events": "List events (query params: limit, offset, dimension)",
    "/events/<id>": "Get event by ID",
    "/query": "Run custom SQL (POST with {sql: '...'})"
  }
}
```

---

### GET /stats

Returns database statistics.

```bash
curl https://sentiment-scraper-api-ffga.onrender.com/stats
```

**Response:**
```json
{
  "total_articles": 150,
  "total_events": 423,
  "events_by_dimension": {
    "Political Relations": 180,
    "Economic Relations": 145,
    "Material Conflict": 78,
    "Other": 20
  },
  "avg_sentiment": -1.25
}
```

---

### GET /articles

Lists articles with pagination.

**Query Parameters:**
- `limit` (default: 50) - Number of results
- `offset` (default: 0) - Skip N results

```bash
# Get first 10 articles
curl "https://sentiment-scraper-api-ffga.onrender.com/articles?limit=10"

# Get next page
curl "https://sentiment-scraper-api-ffga.onrender.com/articles?limit=10&offset=10"
```

**Response:**
```json
{
  "articles": [
    {
      "news_id": 1,
      "news_title": "US-China Trade Talks Resume",
      "publication_date": "2026-01-30",
      "source_url": "https://...",
      "source_domain": "reuters.com",
      "date_scraped": "2026-01-30T12:00:00"
    }
  ],
  "limit": 10,
  "offset": 0
}
```

---

### GET /articles/:id

Get a specific article with all its events.

```bash
curl https://sentiment-scraper-api-ffga.onrender.com/articles/1
```

**Response:**
```json
{
  "news_id": 1,
  "news_title": "US-China Trade Talks Resume",
  "news_text": "Full article text...",
  "article_summary": "Summary...",
  "publication_date": "2026-01-30",
  "events": [
    {
      "event_id": "1-1",
      "event_summary": "Trade negotiations between US and China",
      "dimension": "Economic Relations",
      "sub_dimension": "trade",
      "sentiment": -2,
      "actors": "USA,CHN"
    }
  ]
}
```

---

### GET /events

Lists events with pagination and optional filtering.

**Query Parameters:**
- `limit` (default: 50)
- `offset` (default: 0)
- `dimension` (optional) - Filter by dimension

```bash
# Get all events
curl "https://sentiment-scraper-api-ffga.onrender.com/events?limit=20"

# Filter by dimension
curl "https://sentiment-scraper-api-ffga.onrender.com/events?dimension=Political%20Relations"
```

---

### GET /events/:id

Get a specific event with actors.

```bash
curl https://sentiment-scraper-api-ffga.onrender.com/events/1-1
```

**Response:**
```json
{
  "event_id": "1-1",
  "news_id": 1,
  "event_summary": "Trade negotiations...",
  "dimension": "Economic Relations",
  "sub_dimension": "trade",
  "sentiment": -2,
  "direction": "bilateral",
  "news_title": "US-China Trade Talks Resume",
  "actors": [
    {"actor_iso3": "USA", "actor_role": "actor1"},
    {"actor_iso3": "CHN", "actor_role": "actor2"}
  ]
}
```

---

### GET /full-export

Exports all events with full details (matches the analysis notebook query).

**Query Parameters:**
- `limit` (default: 1000)

```bash
curl "https://sentiment-scraper-api-ffga.onrender.com/full-export?limit=500"
```

**Response:**
```json
{
  "data": [
    {
      "news_id": 1,
      "news_title": "US-China Trade Talks Resume",
      "news_text_preview": "First 500 chars...",
      "article_summary": "...",
      "event_id": "1-1",
      "event_summary": "...",
      "publication_date": "2026-01-30",
      "event_date": "2026-01-30",
      "event_location": "Washington",
      "dimension": "Economic Relations",
      "event_type": "negotiation",
      "sub_dimension": "trade",
      "actor_list": "USA,CHN",
      "actor1": "USA",
      "actor1_secondary": null,
      "actor2": "CHN",
      "actor2_secondary": null,
      "direction": "bilateral",
      "sentiment": -2
    }
  ],
  "count": 1
}
```

---

### POST /query

Run a custom read-only SQL query.

```bash
curl -X POST https://sentiment-scraper-api-ffga.onrender.com/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT dimension, COUNT(*) as count FROM events GROUP BY dimension"}'
```

**Response:**
```json
{
  "results": [
    {"dimension": "Political Relations", "count": 180},
    {"dimension": "Economic Relations", "count": 145}
  ],
  "count": 4
}
```

**Note:** Only `SELECT` queries are allowed.

---

## Python Usage Examples

### Using requests library

```python
import requests

API_BASE = "https://sentiment-scraper-api-ffga.onrender.com"

# Get statistics
stats = requests.get(f"{API_BASE}/stats").json()
print(f"Total articles: {stats['total_articles']}")
print(f"Total events: {stats['total_events']}")

# Get articles
articles = requests.get(f"{API_BASE}/articles", params={"limit": 10}).json()
for article in articles["articles"]:
    print(f"- {article['news_title']}")

# Run custom query
response = requests.post(
    f"{API_BASE}/query",
    json={"sql": "SELECT * FROM events WHERE sentiment < -5 LIMIT 10"}
)
negative_events = response.json()["results"]
```

### Loading into Pandas

```python
import pandas as pd
import requests

API_BASE = "https://sentiment-scraper-api-ffga.onrender.com"

# Get full export as DataFrame
response = requests.get(f"{API_BASE}/full-export", params={"limit": 5000})
data = response.json()["data"]
df = pd.DataFrame(data)

# Analyze
print(df.groupby("dimension")["sentiment"].mean())
print(df["actor_list"].value_counts().head(10))
```

---

## Cron Job Schedule

The scraper runs every 6 hours at:
- 00:00 UTC
- 06:00 UTC
- 12:00 UTC
- 18:00 UTC

To trigger manually:
1. Go to https://dashboard.render.com/cron/crn-d5uf3fiqcgvc73aulcqg
2. Click **"Trigger Run"**

---

## Local Development

### Running locally with SQLite (default)

```bash
# No DATABASE_URL = uses SQLite
python main.py --days 1 --test
```

### Running locally against Render Postgres

**Note:** Requires paid Postgres plan for external connections.

```bash
export DATABASE_URL="postgresql://user:pass@host.oregon-postgres.render.com/db"
python main.py --days 1
```

---

## Database Schema

### Tables

```sql
-- Articles table
CREATE TABLE articles (
    news_id SERIAL PRIMARY KEY,
    news_title TEXT NOT NULL,
    news_text TEXT,
    article_summary TEXT,
    publication_date TEXT,
    source_url TEXT UNIQUE,
    source_domain TEXT,
    source_country TEXT,
    language TEXT DEFAULT 'en',
    date_scraped TEXT
);

-- Events table
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    news_id INTEGER REFERENCES articles(news_id),
    event_summary TEXT,
    event_date TEXT,
    event_location TEXT,
    dimension TEXT,
    event_type TEXT,
    sub_dimension TEXT,
    direction TEXT CHECK(direction IN ('unilateral', 'bilateral', 'multilateral')),
    sentiment REAL CHECK(sentiment >= -10 AND sentiment <= 10),
    confidence_level REAL
);

-- Event actors table
CREATE TABLE event_actors (
    id SERIAL PRIMARY KEY,
    event_id TEXT REFERENCES events(event_id),
    actor_iso3 TEXT NOT NULL,
    actor_role TEXT CHECK(actor_role IN ('actor1', 'actor1_secondary', 'actor2', 'actor2_secondary'))
);
```

### Dimensions Taxonomy

| Dimension | Sub-dimensions |
|-----------|----------------|
| Political Relations | political, government, election, legislative, diplomatic, legal, refugee |
| Material Conflict | military, terrorism, cbrn, cyber |
| Economic Relations | trade, aid, investment, resources, technology_transfer, etc. |
| Other | disease, disaster, historical, culture |

---

## Troubleshooting

### API returns 502 Bad Gateway
- The service is still deploying or restarting
- Wait 1-2 minutes and try again
- Check deployment logs at the dashboard

### Database is empty
- The cron job hasn't run yet
- Trigger a manual run from the dashboard
- Check cron job logs for errors

### Connection refused (local psql)
- Free tier Postgres only allows internal connections
- Use the API instead, or upgrade to paid Postgres

---

## Costs

| Resource | Plan | Cost |
|----------|------|------|
| Postgres | Free | $0/month (expires in 30 days) |
| Cron Job | Starter | ~$7/month |
| Web Service | Starter | ~$7/month |

**Total:** ~$14/month (plus Postgres after free trial)

---

## Important Notes

1. **Free Postgres expires** in 30 days. Upgrade before March 1, 2026.
2. **Auto-deploy is enabled** - pushing to `main` triggers redeployment.
3. **Rate limits** - Be mindful of API usage; add caching if needed.
4. **OpenAI costs** - Each scraper run uses GPT-4o for analysis.
