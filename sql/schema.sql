-- ============================================================
-- GLOBAL INTERNATIONAL RELATIONS MONITOR - Schema V2
-- Event-Centric Database Design Based on Plover Methodology
-- ============================================================
-- This schema supports multi-event extraction per article with
-- full actor role assignment and Plover-based taxonomy
-- ============================================================

-- Drop existing tables if they exist (for fresh setup)
DROP TABLE IF EXISTS event_actors;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS articles;
DROP TABLE IF EXISTS dimensions_taxonomy;
DROP TABLE IF EXISTS countries_reference;

-- ============================================================
-- ARTICLES TABLE
-- Stores source news articles with metadata
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
    news_id INTEGER PRIMARY KEY,
    news_title TEXT NOT NULL,
    news_text TEXT,
    article_summary TEXT,          -- DEPRECATED: no longer populated by GPT
    publication_date TEXT,
    source_url TEXT UNIQUE,
    source_domain TEXT,
    source_country TEXT,
    language TEXT DEFAULT 'en',
    language_detected TEXT,
    date_scraped TEXT
);

-- ============================================================
-- EVENTS TABLE
-- Stores individual international events extracted from articles
-- One article can have multiple events
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    news_id INTEGER NOT NULL,
    event_summary TEXT,
    event_date TEXT,
    event_location TEXT,           -- DEPRECATED: no longer populated by GPT
    dimension TEXT,
    event_type TEXT,               -- DEPRECATED: no longer populated by GPT
    sub_dimension TEXT,
    direction TEXT CHECK(direction IN ('unilateral', 'bilateral', 'multilateral')),
    sentiment REAL CHECK(sentiment >= -10 AND sentiment <= 10),
    confidence_level REAL CHECK(confidence_level >= 0 AND confidence_level <= 1),
    FOREIGN KEY (news_id) REFERENCES articles(news_id) ON DELETE CASCADE
);

-- ============================================================
-- EVENT_ACTORS TABLE
-- Stores actor roles for each event (supports multiple actors per role)
-- ============================================================
CREATE TABLE IF NOT EXISTS event_actors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    actor_iso3 TEXT NOT NULL,
    actor_role TEXT NOT NULL CHECK(actor_role IN ('actor1', 'actor1_secondary', 'actor2', 'actor2_secondary')),
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

-- ============================================================
-- DIMENSIONS_TAXONOMY TABLE
-- Reference table for Plover-based dimension/subdimension taxonomy
-- ============================================================
CREATE TABLE IF NOT EXISTS dimensions_taxonomy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dimension TEXT NOT NULL,
    sub_dimension TEXT NOT NULL,
    description TEXT,
    UNIQUE(dimension, sub_dimension)
);

-- ============================================================
-- COUNTRIES_REFERENCE TABLE
-- Reference table for ISO3 country codes and aliases
-- ============================================================
CREATE TABLE IF NOT EXISTS countries_reference (
    iso3 TEXT PRIMARY KEY,
    country_name TEXT NOT NULL,
    aliases TEXT  -- JSON array of alternative names/demonyms
);

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_events_news_id ON events(news_id);
CREATE INDEX IF NOT EXISTS idx_events_dimension ON events(dimension);
CREATE INDEX IF NOT EXISTS idx_events_direction ON events(direction);
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_sentiment ON events(sentiment);
CREATE INDEX IF NOT EXISTS idx_event_actors_event_id ON event_actors(event_id);
CREATE INDEX IF NOT EXISTS idx_event_actors_iso3 ON event_actors(actor_iso3);
CREATE INDEX IF NOT EXISTS idx_event_actors_role ON event_actors(actor_role);
CREATE INDEX IF NOT EXISTS idx_articles_publication_date ON articles(publication_date);
CREATE INDEX IF NOT EXISTS idx_articles_source_domain ON articles(source_domain);

-- ============================================================
-- POPULATE DIMENSIONS TAXONOMY (Plover-based)
-- ============================================================
INSERT OR IGNORE INTO dimensions_taxonomy (dimension, sub_dimension, description) VALUES
-- Political Relations
('Political Relations', 'political', 'General political interactions and policy matters'),
('Political Relations', 'government', 'Government-level interactions and administration'),
('Political Relations', 'election', 'Electoral processes and voting-related events'),
('Political Relations', 'legislative', 'Legislative actions, laws, and parliamentary matters'),
('Political Relations', 'diplomatic', 'Diplomatic relations, embassies, and formal state interactions'),
('Political Relations', 'legal', 'Legal proceedings, courts, and international law'),
('Political Relations', 'refugee', 'Refugee-related policies and humanitarian protection'),

-- Material Conflict
('Material Conflict', 'military', 'Military actions, defense, and armed forces'),
('Material Conflict', 'terrorism', 'Terrorism-related events and counter-terrorism'),
('Material Conflict', 'cbrn', 'Chemical, biological, radiological, and nuclear matters'),
('Material Conflict', 'cyber', 'Cyber warfare, hacking, and digital security threats'),

-- Economic Relations
('Economic Relations', 'economic', 'General economic interactions and policies'),
('Economic Relations', 'trade', 'Trade agreements, tariffs, and commercial exchanges'),
('Economic Relations', 'aid', 'Foreign aid, humanitarian assistance, and development aid'),
('Economic Relations', 'capital_flows', 'Investment flows, capital movement, and financial transfers'),
('Economic Relations', 'strategic_economic', 'Strategic economic policies and economic sanctions'),
('Economic Relations', 'financial_monetary', 'Financial systems, monetary policy, and banking'),
('Economic Relations', 'development', 'Development projects and infrastructure'),
('Economic Relations', 'taxation_fiscal', 'Tax policies and fiscal matters'),
('Economic Relations', 'investment', 'Foreign direct investment and business ventures'),
('Economic Relations', 'resources', 'Natural resources, energy, and commodities'),
('Economic Relations', 'labour_migration', 'Labor migration and workforce movement'),
('Economic Relations', 'technology_transfer', 'Technology transfer and innovation cooperation'),

-- Other
('Other', 'resource', 'Resource-related events outside economic context'),
('Other', 'disease', 'Health crises, pandemics, and disease outbreaks'),
('Other', 'disaster', 'Natural disasters and emergency response'),
('Other', 'historical', 'Historical references and commemorations'),
('Other', 'hypothetical', 'Speculative or proposed future events'),
('Other', 'culture', 'Cultural exchanges and soft power interactions');

-- ============================================================
-- SAMPLE COUNTRIES REFERENCE DATA (Core countries)
-- Full list should be populated from external source
-- ============================================================
INSERT OR IGNORE INTO countries_reference (iso3, country_name, aliases) VALUES
('USA', 'United States of America', '["United States", "US", "U.S.", "America", "American", "Washington"]'),
('CAN', 'Canada', '["Canadian", "Ottawa"]'),
('MEX', 'Mexico', '["Mexican", "Mexico City"]'),
('GBR', 'United Kingdom', '["UK", "Britain", "British", "England", "London"]'),
('FRA', 'France', '["French", "Paris"]'),
('DEU', 'Germany', '["German", "Berlin"]'),
('CHN', 'China', '["Chinese", "Beijing", "PRC"]'),
('RUS', 'Russia', '["Russian", "Moscow", "Russian Federation"]'),
('JPN', 'Japan', '["Japanese", "Tokyo"]'),
('IND', 'India', '["Indian", "New Delhi"]'),
('BRA', 'Brazil', '["Brazilian", "Brasilia"]'),
('AUS', 'Australia', '["Australian", "Canberra"]'),
('ITA', 'Italy', '["Italian", "Rome"]'),
('ESP', 'Spain', '["Spanish", "Madrid"]'),
('KOR', 'South Korea', '["Korean", "Seoul", "Republic of Korea"]'),
('PRK', 'North Korea', '["DPRK", "Pyongyang"]'),
('IRN', 'Iran', '["Iranian", "Tehran", "Persia"]'),
('ISR', 'Israel', '["Israeli", "Tel Aviv", "Jerusalem"]'),
('SAU', 'Saudi Arabia', '["Saudi", "Riyadh"]'),
('UKR', 'Ukraine', '["Ukrainian", "Kyiv", "Kiev"]'),
('POL', 'Poland', '["Polish", "Warsaw"]'),
('NLD', 'Netherlands', '["Dutch", "Amsterdam", "Holland"]'),
('TUR', 'Turkey', '["Turkish", "Ankara", "Türkiye"]'),
('ARG', 'Argentina', '["Argentine", "Buenos Aires"]'),
('ZAF', 'South Africa', '["South African", "Pretoria", "Cape Town"]'),
('EGY', 'Egypt', '["Egyptian", "Cairo"]'),
('NGA', 'Nigeria', '["Nigerian", "Abuja", "Lagos"]'),
('IDN', 'Indonesia', '["Indonesian", "Jakarta"]'),
('PAK', 'Pakistan', '["Pakistani", "Islamabad"]'),
('BGD', 'Bangladesh', '["Bangladeshi", "Dhaka"]'),
('VNM', 'Vietnam', '["Vietnamese", "Hanoi"]'),
('THA', 'Thailand', '["Thai", "Bangkok"]'),
('PHL', 'Philippines', '["Filipino", "Philippine", "Manila"]'),
('MYS', 'Malaysia', '["Malaysian", "Kuala Lumpur"]'),
('SGP', 'Singapore', '["Singaporean"]'),
('COL', 'Colombia', '["Colombian", "Bogota"]'),
('CHL', 'Chile', '["Chilean", "Santiago"]'),
('PER', 'Peru', '["Peruvian", "Lima"]'),
('VEN', 'Venezuela', '["Venezuelan", "Caracas"]'),
('CUB', 'Cuba', '["Cuban", "Havana"]'),
('SWE', 'Sweden', '["Swedish", "Stockholm"]'),
('NOR', 'Norway', '["Norwegian", "Oslo"]'),
('DNK', 'Denmark', '["Danish", "Copenhagen"]'),
('FIN', 'Finland', '["Finnish", "Helsinki"]'),
('CHE', 'Switzerland', '["Swiss", "Bern", "Geneva", "Zurich"]'),
('AUT', 'Austria', '["Austrian", "Vienna"]'),
('BEL', 'Belgium', '["Belgian", "Brussels"]'),
('PRT', 'Portugal', '["Portuguese", "Lisbon"]'),
('GRC', 'Greece', '["Greek", "Athens"]'),
('CZE', 'Czech Republic', '["Czech", "Prague", "Czechia"]'),
('HUN', 'Hungary', '["Hungarian", "Budapest"]'),
('ROU', 'Romania', '["Romanian", "Bucharest"]'),
('IRL', 'Ireland', '["Irish", "Dublin"]'),
('NZL', 'New Zealand', '["New Zealander", "Kiwi", "Wellington"]'),
('ARE', 'United Arab Emirates', '["UAE", "Emirati", "Dubai", "Abu Dhabi"]'),
('QAT', 'Qatar', '["Qatari", "Doha"]'),
('KWT', 'Kuwait', '["Kuwaiti"]'),
('IRQ', 'Iraq', '["Iraqi", "Baghdad"]'),
('SYR', 'Syria', '["Syrian", "Damascus"]'),
('AFG', 'Afghanistan', '["Afghan", "Kabul"]'),
('PSE', 'Palestine', '["Palestinian", "Gaza", "West Bank"]'),
('LBN', 'Lebanon', '["Lebanese", "Beirut"]'),
('JOR', 'Jordan', '["Jordanian", "Amman"]'),
('MAR', 'Morocco', '["Moroccan", "Rabat"]'),
('DZA', 'Algeria', '["Algerian", "Algiers"]'),
('TUN', 'Tunisia', '["Tunisian", "Tunis"]'),
('LBY', 'Libya', '["Libyan", "Tripoli"]'),
('SDN', 'Sudan', '["Sudanese", "Khartoum"]'),
('ETH', 'Ethiopia', '["Ethiopian", "Addis Ababa"]'),
('KEN', 'Kenya', '["Kenyan", "Nairobi"]'),
('GHA', 'Ghana', '["Ghanaian", "Accra"]'),
('SEN', 'Senegal', '["Senegalese", "Dakar"]'),
('CIV', 'Ivory Coast', '["Ivorian", "Cote d Ivoire", "Abidjan"]'),
('CMR', 'Cameroon', '["Cameroonian", "Yaounde"]'),
('COD', 'Democratic Republic of the Congo', '["DRC", "Congolese", "Kinshasa"]'),
('AGO', 'Angola', '["Angolan", "Luanda"]'),
('TZA', 'Tanzania', '["Tanzanian", "Dodoma", "Dar es Salaam"]'),
('UGA', 'Uganda', '["Ugandan", "Kampala"]'),
('ZWE', 'Zimbabwe', '["Zimbabwean", "Harare"]'),
('MMR', 'Myanmar', '["Burmese", "Burma", "Naypyidaw"]'),
('NPL', 'Nepal', '["Nepali", "Nepalese", "Kathmandu"]'),
('LKA', 'Sri Lanka', '["Sri Lankan", "Colombo"]'),
('KAZ', 'Kazakhstan', '["Kazakh", "Astana", "Nur-Sultan"]'),
('UZB', 'Uzbekistan', '["Uzbek", "Tashkent"]'),
('AZE', 'Azerbaijan', '["Azerbaijani", "Baku"]'),
('GEO', 'Georgia', '["Georgian", "Tbilisi"]'),
('ARM', 'Armenia', '["Armenian", "Yerevan"]'),
('BLR', 'Belarus', '["Belarusian", "Minsk"]'),
('MDA', 'Moldova', '["Moldovan", "Chisinau"]'),
('SRB', 'Serbia', '["Serbian", "Belgrade"]'),
('HRV', 'Croatia', '["Croatian", "Zagreb"]'),
('SVN', 'Slovenia', '["Slovenian", "Ljubljana"]'),
('SVK', 'Slovakia', '["Slovak", "Bratislava"]'),
('BGR', 'Bulgaria', '["Bulgarian", "Sofia"]'),
('UKR', 'Ukraine', '["Ukrainian", "Kyiv"]'),
('LTU', 'Lithuania', '["Lithuanian", "Vilnius"]'),
('LVA', 'Latvia', '["Latvian", "Riga"]'),
('EST', 'Estonia', '["Estonian", "Tallinn"]');

-- ============================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================

-- View: Events with article info
CREATE VIEW IF NOT EXISTS v_events_full AS
SELECT 
    e.event_id,
    e.news_id,
    a.news_title,
    a.article_summary,
    e.event_summary,
    e.event_date,
    e.event_location,
    e.dimension,
    e.event_type,
    e.sub_dimension,
    e.direction,
    e.sentiment,
    e.confidence_level,
    a.publication_date,
    a.source_url,
    a.source_domain
FROM events e
JOIN articles a ON e.news_id = a.news_id;

-- View: Actor pairs for network analysis
CREATE VIEW IF NOT EXISTS v_actor_pairs AS
SELECT 
    e.event_id,
    e.dimension,
    e.sentiment,
    e.direction,
    a1.actor_iso3 as actor1_iso3,
    a2.actor_iso3 as actor2_iso3
FROM events e
JOIN event_actors a1 ON e.event_id = a1.event_id AND a1.actor_role = 'actor1'
JOIN event_actors a2 ON e.event_id = a2.event_id AND a2.actor_role = 'actor2';

-- View: Sentiment by dimension
CREATE VIEW IF NOT EXISTS v_sentiment_by_dimension AS
SELECT 
    dimension,
    sub_dimension,
    COUNT(*) as event_count,
    ROUND(AVG(sentiment), 2) as avg_sentiment,
    ROUND(MIN(sentiment), 2) as min_sentiment,
    ROUND(MAX(sentiment), 2) as max_sentiment
FROM events
GROUP BY dimension, sub_dimension
ORDER BY dimension, event_count DESC;

