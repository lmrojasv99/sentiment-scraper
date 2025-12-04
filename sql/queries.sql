-- ============================================================
-- GLOBAL INTERNATIONAL RELATIONS MONITOR V2 - Analysis Queries
-- Event-Centric Schema Based on Plover Methodology
-- ============================================================
-- Run with: sqlite3 -header -column geopolitical_monitor.db < queries.sql
-- Or open in any SQLite viewer (DB Browser, TablePlus, etc.)
-- ============================================================

-- ============================================================
-- OVERVIEW & STATISTICS
-- ============================================================

-- 1. DATABASE OVERVIEW: Total counts and averages
SELECT 
    (SELECT COUNT(*) FROM articles) as total_articles,
    (SELECT COUNT(*) FROM events) as total_events,
    ROUND((SELECT COUNT(*) FROM events) * 1.0 / NULLIF((SELECT COUNT(*) FROM articles), 0), 2) as avg_events_per_article,
    ROUND((SELECT AVG(sentiment) FROM events), 2) as avg_sentiment,
    (SELECT COUNT(DISTINCT actor_iso3) FROM event_actors) as unique_countries;

-- 2. SENTIMENT DISTRIBUTION: Breakdown by positive/neutral/negative
SELECT 
    CASE 
        WHEN sentiment >= 3 THEN 'Positive'
        WHEN sentiment <= -3 THEN 'Negative'
        ELSE 'Neutral'
    END as sentiment_category,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment,
    MIN(sentiment) as min_sentiment,
    MAX(sentiment) as max_sentiment
FROM events
GROUP BY sentiment_category
ORDER BY avg_sentiment DESC;

-- 3. DIMENSION DISTRIBUTION: Events by Plover dimension
SELECT 
    dimension,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment,
    GROUP_CONCAT(DISTINCT sub_dimension) as sub_dimensions
FROM events
GROUP BY dimension
ORDER BY event_count DESC;

-- 4. SUB-DIMENSION BREAKDOWN: Detailed taxonomy usage
SELECT 
    dimension,
    sub_dimension,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment
FROM events
GROUP BY dimension, sub_dimension
ORDER BY dimension, event_count DESC;

-- ============================================================
-- EVENT DIRECTION ANALYSIS
-- ============================================================

-- 5. DIRECTION DISTRIBUTION: Unilateral vs Bilateral vs Multilateral
SELECT 
    direction,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM events), 1) as percentage
FROM events
GROUP BY direction
ORDER BY event_count DESC;

-- 6. DIRECTION BY DIMENSION: How event types relate to direction
SELECT 
    dimension,
    direction,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment
FROM events
GROUP BY dimension, direction
ORDER BY dimension, event_count DESC;

-- ============================================================
-- ACTOR ANALYSIS
-- ============================================================

-- 7. TOP ACTORS: Most frequently mentioned countries
SELECT 
    ea.actor_iso3,
    cr.country_name,
    COUNT(*) as total_mentions,
    SUM(CASE WHEN ea.actor_role = 'actor1' THEN 1 ELSE 0 END) as as_initiator,
    SUM(CASE WHEN ea.actor_role = 'actor2' THEN 1 ELSE 0 END) as as_target,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment
FROM event_actors ea
JOIN events e ON ea.event_id = e.event_id
LEFT JOIN countries_reference cr ON ea.actor_iso3 = cr.iso3
GROUP BY ea.actor_iso3
ORDER BY total_mentions DESC
LIMIT 20;

-- 8. ACTOR ROLE DISTRIBUTION: How countries act (initiator vs target)
SELECT 
    ea.actor_iso3,
    ea.actor_role,
    COUNT(*) as role_count,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment
FROM event_actors ea
JOIN events e ON ea.event_id = e.event_id
GROUP BY ea.actor_iso3, ea.actor_role
ORDER BY ea.actor_iso3, role_count DESC;

-- ============================================================
-- COUNTRY PAIR ANALYSIS
-- ============================================================

-- 9. COUNTRY PAIRS: All bilateral interactions with sentiment
SELECT 
    a1.actor_iso3 as actor1,
    a2.actor_iso3 as actor2,
    COUNT(*) as interaction_count,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment,
    GROUP_CONCAT(DISTINCT e.dimension) as dimensions
FROM events e
JOIN event_actors a1 ON e.event_id = a1.event_id AND a1.actor_role = 'actor1'
JOIN event_actors a2 ON e.event_id = a2.event_id AND a2.actor_role = 'actor2'
GROUP BY a1.actor_iso3, a2.actor_iso3
ORDER BY interaction_count DESC
LIMIT 30;

-- 10. COUNTRY PAIR SENTIMENT MATRIX: For network visualization
SELECT 
    a1.actor_iso3 as source,
    a2.actor_iso3 as target,
    COUNT(*) as weight,
    ROUND(AVG(e.sentiment), 2) as sentiment,
    e.direction
FROM events e
JOIN event_actors a1 ON e.event_id = a1.event_id AND a1.actor_role IN ('actor1')
JOIN event_actors a2 ON e.event_id = a2.event_id AND a2.actor_role IN ('actor2')
GROUP BY a1.actor_iso3, a2.actor_iso3, e.direction
HAVING COUNT(*) >= 1
ORDER BY weight DESC;

-- ============================================================
-- SPECIFIC COUNTRY QUERIES
-- ============================================================

-- 11. USA EVENTS: All events involving the United States
SELECT 
    e.event_id,
    e.event_summary,
    e.dimension,
    e.direction,
    e.sentiment,
    e.event_date,
    ea.actor_role
FROM events e
JOIN event_actors ea ON e.event_id = ea.event_id
WHERE ea.actor_iso3 = 'USA'
ORDER BY e.event_date DESC
LIMIT 50;

-- 12. USA-CHINA RELATIONS: Bilateral events between USA and China
SELECT 
    e.event_id,
    e.event_summary,
    e.dimension,
    e.sub_dimension,
    e.direction,
    e.sentiment,
    e.event_date,
    a.news_title
FROM events e
JOIN event_actors ea1 ON e.event_id = ea1.event_id
JOIN event_actors ea2 ON e.event_id = ea2.event_id
JOIN articles a ON e.news_id = a.news_id
WHERE (ea1.actor_iso3 = 'USA' AND ea2.actor_iso3 = 'CHN')
   OR (ea1.actor_iso3 = 'CHN' AND ea2.actor_iso3 = 'USA')
GROUP BY e.event_id
ORDER BY e.event_date DESC;

-- 13. USA-RUSSIA RELATIONS: Events involving USA and Russia
SELECT 
    e.event_id,
    e.event_summary,
    e.dimension,
    e.direction,
    e.sentiment,
    e.event_date
FROM events e
JOIN event_actors ea1 ON e.event_id = ea1.event_id
JOIN event_actors ea2 ON e.event_id = ea2.event_id
WHERE (ea1.actor_iso3 = 'USA' AND ea2.actor_iso3 = 'RUS')
   OR (ea1.actor_iso3 = 'RUS' AND ea2.actor_iso3 = 'USA')
GROUP BY e.event_id
ORDER BY e.sentiment ASC;

-- 14. NORTH AMERICA TRILATERAL: Events between USA, Canada, Mexico
SELECT 
    e.event_id,
    e.event_summary,
    e.dimension,
    e.direction,
    e.sentiment,
    GROUP_CONCAT(DISTINCT ea.actor_iso3) as actors
FROM events e
JOIN event_actors ea ON e.event_id = ea.event_id
WHERE ea.actor_iso3 IN ('USA', 'CAN', 'MEX')
GROUP BY e.event_id
HAVING COUNT(DISTINCT ea.actor_iso3) >= 2
ORDER BY e.event_date DESC;

-- ============================================================
-- TIME SERIES ANALYSIS
-- ============================================================

-- 15. DAILY EVENT COUNTS: Events per day
SELECT 
    DATE(e.event_date) as date,
    COUNT(*) as event_count,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment,
    GROUP_CONCAT(DISTINCT e.dimension) as dimensions
FROM events e
WHERE e.event_date IS NOT NULL AND e.event_date != ''
GROUP BY DATE(e.event_date)
ORDER BY date DESC
LIMIT 30;

-- 16. SENTIMENT TREND: Daily average sentiment
SELECT 
    DATE(e.event_date) as date,
    COUNT(*) as events,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment,
    MIN(e.sentiment) as min_sentiment,
    MAX(e.sentiment) as max_sentiment
FROM events e
WHERE e.event_date IS NOT NULL AND e.event_date != ''
GROUP BY DATE(e.event_date)
ORDER BY date DESC;

-- ============================================================
-- ARTICLE ANALYSIS
-- ============================================================

-- 17. ARTICLES WITH MOST EVENTS: Multi-event extraction success
SELECT 
    a.news_id,
    a.news_title,
    COUNT(e.event_id) as event_count,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment,
    GROUP_CONCAT(DISTINCT e.dimension) as dimensions
FROM articles a
JOIN events e ON a.news_id = e.news_id
GROUP BY a.news_id
ORDER BY event_count DESC
LIMIT 20;

-- 18. RECENT ARTICLES: Latest processed articles with events
SELECT 
    a.news_id,
    a.news_title,
    a.publication_date,
    a.source_domain,
    COUNT(e.event_id) as events,
    a.article_summary
FROM articles a
LEFT JOIN events e ON a.news_id = e.news_id
GROUP BY a.news_id
ORDER BY a.date_scraped DESC
LIMIT 20;

-- 19. ARTICLES BY SOURCE: Distribution of articles by source domain
SELECT 
    a.source_domain,
    COUNT(DISTINCT a.news_id) as article_count,
    COUNT(e.event_id) as total_events,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment
FROM articles a
LEFT JOIN events e ON a.news_id = e.news_id
GROUP BY a.source_domain
ORDER BY article_count DESC;

-- ============================================================
-- EVENT TYPE ANALYSIS
-- ============================================================

-- 20. EVENT TYPES: Distribution of event types
SELECT 
    event_type,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment,
    GROUP_CONCAT(DISTINCT dimension) as dimensions
FROM events
WHERE event_type IS NOT NULL AND event_type != ''
GROUP BY event_type
ORDER BY event_count DESC
LIMIT 20;

-- ============================================================
-- NEGATIVE/POSITIVE EVENT FOCUS
-- ============================================================

-- 21. MOST NEGATIVE EVENTS: Lowest sentiment events
SELECT 
    e.event_id,
    e.event_summary,
    e.sentiment,
    e.dimension,
    e.direction,
    GROUP_CONCAT(DISTINCT ea.actor_iso3) as actors,
    a.news_title
FROM events e
JOIN event_actors ea ON e.event_id = ea.event_id
JOIN articles a ON e.news_id = a.news_id
GROUP BY e.event_id
ORDER BY e.sentiment ASC
LIMIT 15;

-- 22. MOST POSITIVE EVENTS: Highest sentiment events
SELECT 
    e.event_id,
    e.event_summary,
    e.sentiment,
    e.dimension,
    e.direction,
    GROUP_CONCAT(DISTINCT ea.actor_iso3) as actors,
    a.news_title
FROM events e
JOIN event_actors ea ON e.event_id = ea.event_id
JOIN articles a ON e.news_id = a.news_id
GROUP BY e.event_id
ORDER BY e.sentiment DESC
LIMIT 15;

-- ============================================================
-- TAXONOMY REFERENCE
-- ============================================================

-- 23. TAXONOMY OVERVIEW: Available dimensions and subdimensions
SELECT 
    dimension,
    sub_dimension,
    description
FROM dimensions_taxonomy
ORDER BY dimension, sub_dimension;

-- 24. TAXONOMY USAGE: Which taxonomy entries are actually used
SELECT 
    dt.dimension,
    dt.sub_dimension,
    COUNT(e.event_id) as usage_count
FROM dimensions_taxonomy dt
LEFT JOIN events e ON dt.dimension = e.dimension AND dt.sub_dimension = e.sub_dimension
GROUP BY dt.dimension, dt.sub_dimension
ORDER BY usage_count DESC;

-- ============================================================
-- NETWORK ANALYSIS DATA EXPORTS
-- ============================================================

-- 25. EDGE LIST: For network graph visualization
SELECT 
    a1.actor_iso3 as source,
    a2.actor_iso3 as target,
    COUNT(*) as weight,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment,
    GROUP_CONCAT(DISTINCT e.dimension) as edge_types
FROM events e
JOIN event_actors a1 ON e.event_id = a1.event_id AND a1.actor_role IN ('actor1', 'actor1_secondary')
JOIN event_actors a2 ON e.event_id = a2.event_id AND a2.actor_role IN ('actor2', 'actor2_secondary')
WHERE a1.actor_iso3 != a2.actor_iso3
GROUP BY a1.actor_iso3, a2.actor_iso3
ORDER BY weight DESC;

-- 26. NODE LIST: Countries with their attributes
SELECT 
    ea.actor_iso3 as id,
    cr.country_name as label,
    COUNT(DISTINCT e.event_id) as degree,
    ROUND(AVG(e.sentiment), 2) as avg_sentiment,
    SUM(CASE WHEN ea.actor_role = 'actor1' THEN 1 ELSE 0 END) as out_degree,
    SUM(CASE WHEN ea.actor_role = 'actor2' THEN 1 ELSE 0 END) as in_degree
FROM event_actors ea
JOIN events e ON ea.event_id = e.event_id
LEFT JOIN countries_reference cr ON ea.actor_iso3 = cr.iso3
GROUP BY ea.actor_iso3
ORDER BY degree DESC;

-- ============================================================
-- SINGLE EVENT LOOKUP (parameterized)
-- ============================================================

-- 27. FULL EVENT DETAILS: Complete information for one event
-- Replace '123-1' with actual event_id
-- SELECT 
--     e.*,
--     a.news_title,
--     a.news_text,
--     GROUP_CONCAT(DISTINCT ea.actor_iso3 || ':' || ea.actor_role) as actor_roles
-- FROM events e
-- JOIN articles a ON e.news_id = a.news_id
-- JOIN event_actors ea ON e.event_id = ea.event_id
-- WHERE e.event_id = '123-1'
-- GROUP BY e.event_id;

-- ============================================================
-- DATA QUALITY CHECKS
-- ============================================================

-- 28. EVENTS WITHOUT ACTORS: Potential data issues
SELECT 
    e.event_id,
    e.event_summary
FROM events e
LEFT JOIN event_actors ea ON e.event_id = ea.event_id
WHERE ea.event_id IS NULL;

-- 29. SINGLE-ACTOR EVENTS: Events with fewer than 2 countries
SELECT 
    e.event_id,
    e.event_summary,
    COUNT(DISTINCT ea.actor_iso3) as actor_count
FROM events e
JOIN event_actors ea ON e.event_id = ea.event_id
GROUP BY e.event_id
HAVING actor_count < 2;

-- 30. ARTICLES WITHOUT EVENTS: Articles that had no events extracted
SELECT 
    a.news_id,
    a.news_title,
    a.date_scraped
FROM articles a
LEFT JOIN events e ON a.news_id = e.news_id
WHERE e.event_id IS NULL
ORDER BY a.date_scraped DESC;
