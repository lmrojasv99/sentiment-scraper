"""
Simple Flask API for querying the Sentiment Scraper database.
Deployed on Render to enable external access to the free-tier Postgres.
"""

import os
import sqlite3
from pathlib import Path
from flask import Flask, jsonify, request
from functools import wraps

app = Flask(__name__)

# Check if using PostgreSQL or SQLite
def _use_postgres():
    return bool(os.getenv("DATABASE_URL"))

def get_db_connection():
    """Get database connection - supports both PostgreSQL and SQLite."""
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Use PostgreSQL
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    else:
        # Fall back to local SQLite
        db_path = Path(__file__).parent / "data" / "geopolitical_monitor.db"
        if not db_path.exists():
            raise Exception(f"Local database not found at {db_path}")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


def handle_db_errors(f):
    """Decorator to handle database errors."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return wrapper


@app.route("/")
def index():
    """API info."""
    return jsonify({
        "name": "Sentiment Scraper API",
        "endpoints": {
            "/stats": "Database statistics",
            "/articles": "List articles (query params: limit, offset)",
            "/articles/<id>": "Get article by ID",
            "/events": "List events (query params: limit, offset, dimension)",
            "/events/<id>": "Get event by ID",
            "/query": "Run custom SQL (POST with {sql: '...'})"
        }
    })


@app.route("/stats")
@handle_db_errors
def stats():
    """Get database statistics."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    stats = {}
    
    cur.execute("SELECT COUNT(*) as count FROM articles")
    row = cur.fetchone()
    stats["total_articles"] = row["count"] if isinstance(row, dict) else row[0]
    
    cur.execute("SELECT COUNT(*) as count FROM events")
    row = cur.fetchone()
    stats["total_events"] = row["count"] if isinstance(row, dict) else row[0]
    
    cur.execute("""
        SELECT dimension, COUNT(*) as count 
        FROM events 
        GROUP BY dimension 
        ORDER BY count DESC
    """)
    rows = cur.fetchall()
    stats["events_by_dimension"] = {
        (row["dimension"] if isinstance(row, dict) else row[0]): (row["count"] if isinstance(row, dict) else row[1]) 
        for row in rows
    }
    
    if _use_postgres():
        cur.execute("SELECT ROUND(AVG(sentiment)::numeric, 2) as avg FROM events")
    else:
        cur.execute("SELECT ROUND(AVG(sentiment), 2) as avg FROM events")
    row = cur.fetchone()
    avg_val = row["avg"] if isinstance(row, dict) else row[0]
    stats["avg_sentiment"] = float(avg_val) if avg_val else None
    
    conn.close()
    return jsonify(stats)


@app.route("/articles")
@handle_db_errors
def list_articles():
    """List articles."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if _use_postgres():
        cur.execute("""
            SELECT news_id, news_title, publication_date, source_url, source_domain, date_scraped
            FROM articles
            ORDER BY news_id DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
    else:
        cur.execute("""
            SELECT news_id, news_title, publication_date, source_url, source_domain, date_scraped
            FROM articles
            ORDER BY news_id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
    
    articles = cur.fetchall()
    conn.close()
    
    return jsonify({"articles": [dict(a) for a in articles], "limit": limit, "offset": offset})


@app.route("/articles/<int:article_id>")
@handle_db_errors
def get_article(article_id):
    """Get article by ID with its events."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if _use_postgres():
        cur.execute("SELECT * FROM articles WHERE news_id = %s", (article_id,))
    else:
        cur.execute("SELECT * FROM articles WHERE news_id = ?", (article_id,))
    article = cur.fetchone()
    
    if not article:
        conn.close()
        return jsonify({"error": "Article not found"}), 404
    
    if _use_postgres():
        cur.execute("""
            SELECT e.*, STRING_AGG(DISTINCT ea.actor_iso3, ',') as actors
            FROM events e
            LEFT JOIN event_actors ea ON e.event_id = ea.event_id
            WHERE e.news_id = %s
            GROUP BY e.id, e.event_id, e.news_id, e.event_summary, e.event_date,
                     e.event_location, e.dimension, e.event_type, e.sub_dimension,
                     e.direction, e.sentiment, e.confidence_level
        """, (article_id,))
    else:
        cur.execute("""
            SELECT e.*, GROUP_CONCAT(DISTINCT ea.actor_iso3) as actors
            FROM events e
            LEFT JOIN event_actors ea ON e.event_id = ea.event_id
            WHERE e.news_id = ?
            GROUP BY e.event_id
        """, (article_id,))
    events = cur.fetchall()
    
    conn.close()
    
    result = dict(article)
    result["events"] = [dict(e) for e in events]
    
    return jsonify(result)


@app.route("/events")
@handle_db_errors
def list_events():
    """List events."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    dimension = request.args.get("dimension")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if _use_postgres():
        if dimension:
            cur.execute("""
                SELECT e.event_id, e.news_id, e.event_summary, e.dimension, 
                       e.sub_dimension, e.sentiment, e.direction, a.news_title
                FROM events e
                JOIN articles a ON e.news_id = a.news_id
                WHERE e.dimension = %s
                ORDER BY e.id DESC
                LIMIT %s OFFSET %s
            """, (dimension, limit, offset))
        else:
            cur.execute("""
                SELECT e.event_id, e.news_id, e.event_summary, e.dimension, 
                       e.sub_dimension, e.sentiment, e.direction, a.news_title
                FROM events e
                JOIN articles a ON e.news_id = a.news_id
                ORDER BY e.id DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
    else:
        if dimension:
            cur.execute("""
                SELECT e.event_id, e.news_id, e.event_summary, e.dimension, 
                       e.sub_dimension, e.sentiment, e.direction, a.news_title
                FROM events e
                JOIN articles a ON e.news_id = a.news_id
                WHERE e.dimension = ?
                ORDER BY e.id DESC
                LIMIT ? OFFSET ?
            """, (dimension, limit, offset))
        else:
            cur.execute("""
                SELECT e.event_id, e.news_id, e.event_summary, e.dimension, 
                       e.sub_dimension, e.sentiment, e.direction, a.news_title
                FROM events e
                JOIN articles a ON e.news_id = a.news_id
                ORDER BY e.id DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
    
    events = cur.fetchall()
    conn.close()
    
    return jsonify({"events": [dict(e) for e in events], "limit": limit, "offset": offset})


@app.route("/events/<event_id>")
@handle_db_errors
def get_event(event_id):
    """Get event by ID with actors."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if _use_postgres():
        cur.execute("""
            SELECT e.*, a.news_title, a.source_url
            FROM events e
            JOIN articles a ON e.news_id = a.news_id
            WHERE e.event_id = %s
        """, (event_id,))
    else:
        cur.execute("""
            SELECT e.*, a.news_title, a.source_url
            FROM events e
            JOIN articles a ON e.news_id = a.news_id
            WHERE e.event_id = ?
        """, (event_id,))
    event = cur.fetchone()
    
    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404
    
    if _use_postgres():
        cur.execute("""
            SELECT actor_iso3, actor_role
            FROM event_actors
            WHERE event_id = %s
        """, (event_id,))
    else:
        cur.execute("""
            SELECT actor_iso3, actor_role
            FROM event_actors
            WHERE event_id = ?
        """, (event_id,))
    actors = cur.fetchall()
    
    conn.close()
    
    result = dict(event)
    result["actors"] = [dict(a) for a in actors]
    
    return jsonify(result)


@app.route("/query", methods=["POST"])
@handle_db_errors
def run_query():
    """Run a custom read-only SQL query."""
    data = request.get_json()
    if not data or "sql" not in data:
        return jsonify({"error": "Missing 'sql' in request body"}), 400
    
    sql = data["sql"].strip()
    
    # Basic safety check - only allow SELECT
    if not sql.upper().startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries allowed"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(sql)
    rows = cur.fetchall()
    
    conn.close()
    
    return jsonify({"results": [dict(r) for r in rows], "count": len(rows)})


@app.route("/full-export")
@handle_db_errors
def full_export():
    """Export all events with full article and actor data."""
    limit = request.args.get("limit", 1000, type=int)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if _use_postgres():
        cur.execute("""
            SELECT 
                a.news_id,
                a.news_title,
                SUBSTRING(a.news_text, 1, 500) as news_text_preview,
                a.article_summary,
                e.event_id,
                e.event_summary,
                a.publication_date,
                e.event_date,
                e.event_location,
                e.dimension,
                e.event_type,
                e.sub_dimension,
                (
                    SELECT STRING_AGG(DISTINCT ea.actor_iso3, ',')
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id
                ) as actor_list,
                (
                    SELECT STRING_AGG(ea.actor_iso3, ',')
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor1'
                ) as actor1,
                (
                    SELECT STRING_AGG(ea.actor_iso3, ',')
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor1_secondary'
                ) as actor1_secondary,
                (
                    SELECT STRING_AGG(ea.actor_iso3, ',')
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor2'
                ) as actor2,
                (
                    SELECT STRING_AGG(ea.actor_iso3, ',')
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor2_secondary'
                ) as actor2_secondary,
                e.direction,
                e.sentiment
            FROM events e
            JOIN articles a ON e.news_id = a.news_id
            ORDER BY a.news_id, e.event_id
            LIMIT %s
        """, (limit,))
    else:
        cur.execute("""
            SELECT 
                a.news_id,
                a.news_title,
                SUBSTR(a.news_text, 1, 500) as news_text_preview,
                a.article_summary,
                e.event_id,
                e.event_summary,
                a.publication_date,
                e.event_date,
                e.event_location,
                e.dimension,
                e.event_type,
                e.sub_dimension,
                (
                    SELECT GROUP_CONCAT(DISTINCT ea.actor_iso3)
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id
                ) as actor_list,
                (
                    SELECT GROUP_CONCAT(ea.actor_iso3)
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor1'
                ) as actor1,
                (
                    SELECT GROUP_CONCAT(ea.actor_iso3)
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor1_secondary'
                ) as actor1_secondary,
                (
                    SELECT GROUP_CONCAT(ea.actor_iso3)
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor2'
                ) as actor2,
                (
                    SELECT GROUP_CONCAT(ea.actor_iso3)
                    FROM event_actors ea 
                    WHERE ea.event_id = e.event_id AND ea.actor_role = 'actor2_secondary'
                ) as actor2_secondary,
                e.direction,
                e.sentiment
            FROM events e
            JOIN articles a ON e.news_id = a.news_id
            ORDER BY a.news_id, e.event_id
            LIMIT ?
        """, (limit,))
    
    rows = cur.fetchall()
    conn.close()
    
    return jsonify({"data": [dict(r) for r in rows], "count": len(rows)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
