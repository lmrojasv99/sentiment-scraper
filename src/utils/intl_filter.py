"""International Context Filter.

Filters articles for international relevance using two criteria
(BOTH must be satisfied):

  1. Structural: at least two distinct sovereign countries are mentioned,
     OR one country + one recognised international organisation.

  2. Semantic: at least one international-relations keyword is present.

Country detection uses three complementary layers:
  a. Alias / demonym regex patterns (CountryMapper — fast, comprehensive)
  b. spaCy NER GPE/LOC entities resolved via pycountry (catches proper nouns
     not in the alias list)

The filter always operates on TRANSLATED ENGLISH text so that keyword and
country detection work reliably regardless of the original article language.
"""

import logging
import re
from typing import List, Optional, Set, Tuple

import pycountry
from unidecode import unidecode

from src.utils.country_mapper import get_mapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# International organisations
# ---------------------------------------------------------------------------

INTL_ORGS_MAP: dict = {
    # European Union
    "european union": "EU", "eu": "EU", "e.u.": "EU",
    # European Central Bank
    "european central bank": "ECB", "ecb": "ECB",
    # NATO
    "north atlantic treaty organization": "NATO", "nato": "NATO",
    # G7 / G20
    "group of seven": "G7", "g7": "G7", "g-7": "G7",
    "group of twenty": "G20", "g20": "G20", "g-20": "G20",
    # BRICS
    "brics": "BRICS",
    # ASEAN
    "association of southeast asian nations": "ASEAN", "asean": "ASEAN",
    # MERCOSUR
    "mercosur": "MERCOSUR", "southern common market": "MERCOSUR",
    # USMCA
    "united states mexico canada agreement": "USMCA", "usmca": "USMCA",
    # OPEC
    "organization of the petroleum exporting countries": "OPEC", "opec": "OPEC",
    # GCC
    "gulf cooperation council": "GCC", "gcc": "GCC",
    # QUAD
    "quadrilateral security dialogue": "QUAD", "quad": "QUAD",
    # ECOWAS
    "economic community of west african states": "ECOWAS", "ecowas": "ECOWAS",
    # EAEU
    "eurasian economic union": "EAEU", "eaeu": "EAEU",
    # Andean Community
    "andean community": "CAN",
}

# Pre-compile org patterns once at import time
_ORG_PATTERNS: dict = {
    k: re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE)
    for k in INTL_ORGS_MAP
}

# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

INTERNATIONAL_KEYWORDS: List[str] = [
    # Core IR vocabulary
    "diplomacy", "trade", "military", "sanctions", "united nations",
    "nato", "g7", "g20", "security", "foreign", "territorial",
    "rights", "conference", "international", "law", "peace",
    "cooperation", "border", "visa", "immigration", "refugee",
    "terrorism", "nuclear", "climate", "dispute", "maritime",
    "cybersecurity", "global", "economy", "humanitarian", "aid",
    "war", "defense", "court", "conflict", "embassy", "budget",
    "envoy", "mediation", "resolution", "finance", "development",
    "crisis", "relief", "control", "regional", "alliance",
    "negotiation", "peacekeeping", "multilateral",
    "treaty", "agreement", "summit", "sanction", "embargo",
    "bilateral", "trilateral", "tariff", "minister", "ambassador",
    # Extended IR / political vocabulary (from Colab v1)
    "authorize", "counterintelligence", "parley", "parliamentary vote",
    "de escalation", "demobilization", "democratic backsliding",
    "autocratization", "extradition", "bailout", "veto",
    "ultimatum", "pull out", "sovereignty", "blockade", "petition",
    "annexation", "non proliferation", "blacklist", "deploy",
    "hostage taking", "detain", "skirmish", "exchange fire",
    "force projection", "ratify", "martial law", "assassination",
    "capital flows", "stock market", "agriculture", "industry",
    "mineral", "regulation", "monetary", "restructuring",
    "investment", "financial", "withdrawal", "apology",
    "restitution", "compensation", "protest", "freedom",
    "vulnerability", "protection", "human rights", "peacekeepers",
    "asylum", "enforcement", "illicit", "smuggling", "illegal",
    "organization", "criminal", "rebel", "information", "operation",
    "misinformation", "disinformation", "trafficking", "drugs",
    "oversight", "attack", "signing", "sign", "army", "troops",
    "deployment", "lawsuit", "warfare", "deport", "occupy",
    "ceasefire", "drone", "ethnic", "expulsion", "emergency",
    "diplomats", "diplomatic", "displacement", "migration",
    "emigration", "displaced", "remittances", "disaster",
    "drought", "hurricane", "earthquake", "flood", "resource",
    "extraction", "environmental", "terrorist", "economic",
]

_KEYWORD_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in INTERNATIONAL_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Text normalisation (accent-strip for consistent matching)
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Lowercase + strip accents + collapse non-alphanumeric to spaces."""
    text = unidecode(str(text)).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# spaCy NER — lazy-loaded, NER pipeline only (no parser/tagger for speed)
# ---------------------------------------------------------------------------

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load(
                "en_core_web_sm",
                disable=["parser", "tagger", "lemmatizer", "attribute_ruler"],
            )
            logger.debug("spaCy NER model loaded for intl_filter.")
        except OSError:
            logger.warning(
                "spaCy en_core_web_sm not found. "
                "NER-based country detection disabled. "
                "Run: python -m spacy download en_core_web_sm"
            )
    return _nlp


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_countries_ner(text: str) -> Set[str]:
    """Use spaCy NER + pycountry to find sovereign countries in *text*."""
    nlp = _get_nlp()
    if nlp is None:
        return set()
    found: Set[str] = set()
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC"):
            try:
                c = pycountry.countries.lookup(ent.text)
                found.add(c.alpha_3)
            except LookupError:
                pass
    return found


def _detect_orgs(norm_text: str) -> Set[str]:
    """Return the set of recognised international organisation codes in *norm_text*."""
    found: Set[str] = set()
    for term, pattern in _ORG_PATTERNS.items():
        if pattern.search(norm_text):
            found.add(INTL_ORGS_MAP[term])
    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def passes_international_filter(
    text: str,
    title: str = "",
    min_countries: int = 2,
) -> Tuple[bool, dict]:
    """Check whether an article passes the international-context filter.

    Args:
        text:          Translated English article body.
        title:         Translated English headline (concatenated for scanning).
        min_countries: Minimum distinct countries required when no org is found
                       (default 2).  One country + one org also passes.

    Returns:
        (passes, details) where:
          passes  — True if both criteria are satisfied.
          details — diagnostic dict:
              keywords_found  (list[str])
              countries_found (list[str])  — ISO3 codes
              orgs_found      (list[str])  — organisation codes (EU, NATO, …)
              keyword_pass    (bool)
              country_pass    (bool)
    """
    combined = f"{title} {text}".strip()
    norm_text = _norm(combined)

    # ── Criterion 1: semantic — at least one IR keyword ──────────────
    keywords_found = sorted(set(
        m.group().lower() for m in _KEYWORD_PATTERN.finditer(norm_text)
    ))
    keyword_pass = len(keywords_found) >= 1

    # ── Criterion 2: structural — countries + orgs ───────────────────
    mapper = get_mapper()

    # Layer A: alias / demonym patterns (fast regex via CountryMapper)
    countries_alias: Set[str] = set(mapper.extract_countries_from_text(combined))

    # Layer B: spaCy NER + pycountry (catches proper nouns not in alias list)
    countries_ner: Set[str] = _detect_countries_ner(combined)

    countries_found = sorted(countries_alias | countries_ner)
    orgs_found = sorted(_detect_orgs(norm_text))

    n_countries = len(countries_found)
    n_orgs = len(orgs_found)

    # Pass if: ≥ min_countries sovereign states  OR  ≥1 country + ≥1 org
    country_pass = n_countries >= min_countries or (n_countries >= 1 and n_orgs >= 1)

    passes = keyword_pass and country_pass

    details = {
        "keywords_found": keywords_found,
        "countries_found": countries_found,
        "orgs_found": orgs_found,
        "keyword_pass": keyword_pass,
        "country_pass": country_pass,
    }

    if passes:
        logger.debug(
            f"PASSED — keywords={keywords_found[:3]}, "
            f"countries={countries_found}, orgs={orgs_found}"
        )
    else:
        logger.debug(
            f"FAILED — keyword_pass={keyword_pass}, "
            f"country_pass={country_pass} "
            f"({n_countries} countries, {n_orgs} orgs)"
        )

    return passes, details
