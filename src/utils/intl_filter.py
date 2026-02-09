"""International Context Filter.

Filters articles for international relevance using two criteria
(BOTH must be satisfied):
  1. At least one international-relations keyword is present in the text.
  2. At least two distinct sovereign countries are mentioned in the text.

Designed to run on TRANSLATED ENGLISH text so that keyword and country
detection work reliably regardless of original article language.
"""

import logging
import re
from typing import List, Tuple

from src.utils.country_mapper import get_mapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword list — case-insensitive matching
# ---------------------------------------------------------------------------
INTERNATIONAL_KEYWORDS: List[str] = [
    "diplomacy", "trade", "military", "sanctions", "united nations",
    "nato", "g7", "g20", "security", "foreign", "territorial",
    "rights", "conference", "international", "law", "peace",
    "cooperation", "border", "visa", "immigration", "refugee",
    "terrorism", "nuclear", "climate", "dispute", "maritime",
    "cybersecurity", "global", "economy", "humanitarian", "aid",
    "war", "defense", "court", "conflict", "embassy", "budget",
    "envoy", "mediation", "resolution", "finance", "development",
    "change", "crisis", "relief", "control", "regional", "alliance",
    "negotiation", "peacekeeping", "multilateral",
    # Additional high-value keywords
    "treaty", "agreement", "summit", "sanction", "embargo",
    "bilateral", "trilateral", "tariff", "minister", "ambassador",
]

# Pre-compile a single regex for fast keyword scanning
_KEYWORD_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in INTERNATIONAL_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def passes_international_filter(
    text: str,
    title: str = "",
    min_countries: int = 2,
) -> Tuple[bool, dict]:
    """Check whether an article passes the international-context filter.

    Args:
        text:  Translated English article body.
        title: Translated English headline (optional — concatenated for scanning).
        min_countries: Minimum distinct countries required (default 2).

    Returns:
        (passes, details) where:
          passes  — True if both criteria are met.
          details — dict with diagnostic info:
              keywords_found   (list[str])
              countries_found   (list[str])  — ISO3 codes
              keyword_pass      (bool)
              country_pass      (bool)
    """
    combined = f"{title} {text}".strip()
    combined_lower = combined.lower()

    # --- Criterion 1: keywords ---
    keywords_found = list(set(m.group().lower() for m in _KEYWORD_PATTERN.finditer(combined_lower)))
    keyword_pass = len(keywords_found) >= 1

    # --- Criterion 2: ≥ min_countries distinct countries ---
    mapper = get_mapper()
    countries_found = mapper.extract_countries_from_text(combined)
    country_pass = len(countries_found) >= min_countries

    passes = keyword_pass and country_pass

    details = {
        "keywords_found": sorted(keywords_found),
        "countries_found": countries_found,
        "keyword_pass": keyword_pass,
        "country_pass": country_pass,
    }

    if passes:
        logger.debug(
            f"Article PASSED filter — keywords={keywords_found[:5]}, "
            f"countries={countries_found}"
        )
    else:
        logger.debug(
            f"Article FAILED filter — keyword_pass={keyword_pass}, "
            f"country_pass={country_pass} ({len(countries_found)} countries)"
        )

    return passes, details
