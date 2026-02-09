"""Translation Module — MarianMT via Hugging Face Transformers.

Detects the source language of article text, chunks it into
sentence-aware segments (≤500 chars), and translates to English
using Helsinki-NLP MarianMT opus-mt-{src}-en models.

Caches one pipeline per source language for reuse across articles.
"""

import logging
from typing import Optional, Tuple

import spacy
from langdetect import detect, LangDetectException
from transformers import pipeline as hf_pipeline

logger = logging.getLogger(__name__)

# Maximum characters per chunk for MarianMT input
MAX_CHUNK_CHARS = 500

# Languages supported by Helsinki-NLP opus-mt-{src}-en models.
# Key = langdetect code, Value = MarianMT model suffix.
# Extend this dict as needed.
SUPPORTED_LANGUAGES = {
    "es": "es",   # Spanish
    "fr": "fr",   # French
    "de": "de",   # German
    "pt": "pt",   # Portuguese
    "it": "it",   # Italian
    "nl": "nl",   # Dutch
    "ru": "ru",   # Russian
    "ar": "ar",   # Arabic
    "zh-cn": "zh",  # Chinese (simplified)
    "zh-tw": "zh",  # Chinese (traditional)
    "ja": "jap",    # Japanese
    "ko": "ko",    # Korean
    "tr": "tr",    # Turkish
    "pl": "pl",    # Polish
    "uk": "uk",    # Ukrainian
    "vi": "vi",    # Vietnamese
    "sv": "sv",    # Swedish
    "da": "da",    # Danish
    "no": "no",    # Norwegian
    "fi": "fi",    # Finnish
    "ro": "ro",    # Romanian
    "cs": "cs",    # Czech
    "hu": "hu",    # Hungarian
    "bg": "bg",    # Bulgarian
    "hr": "hr",    # Croatian (use OPUS-MT tc-big model or sla)
    "hi": "hi",    # Hindi
    "bn": "bn",    # Bengali
    "th": "th",    # Thai
    "id": "id",    # Indonesian
    "ms": "ms",    # Malay
    "tl": "tl",    # Tagalog/Filipino
    "sw": "swc",   # Swahili
    "he": "he",    # Hebrew
    "fa": "fa",    # Farsi/Persian
    "ur": "ur",    # Urdu
    "af": "af",    # Afrikaans
    "sq": "sq",    # Albanian
    "ka": "ka",    # Georgian
    "mk": "mk",    # Macedonian
    "sk": "sk",    # Slovak
    "sl": "sl",    # Slovenian
    "lt": "lt",    # Lithuanian
    "lv": "lv",    # Latvian
    "et": "et",    # Estonian
}


class ArticleTranslator:
    """Translates article text to English using MarianMT.

    Usage:
        translator = ArticleTranslator()
        result = translator.translate(text)
        # result = {"translated_text": "...", "language_detected": "es", "was_translated": True}
    """

    def __init__(self):
        # Cache: language_code -> transformers pipeline
        self._pipelines: dict = {}
        # Load spaCy English model for sentence segmentation
        try:
            self._nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy en_core_web_sm not found. Falling back to simple sentence splitting.")
            self._nlp = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate(self, text: str, title: str = "") -> dict:
        """Translate article body (and optionally title) to English.

        Returns dict with keys:
            translated_text  (str) — English text (or original if already English)
            translated_title (str) — English title
            language_detected (str) — ISO-639-1 code detected by langdetect
            was_translated   (bool) — whether translation was applied
        """
        if not text or not text.strip():
            return {
                "translated_text": text or "",
                "translated_title": title or "",
                "language_detected": "unknown",
                "was_translated": False,
            }

        lang = self._detect_language(text)

        # If English or undetectable, return as-is
        if lang in ("en", "unknown"):
            return {
                "translated_text": text,
                "translated_title": title,
                "language_detected": lang,
                "was_translated": False,
            }

        # Check if we have a MarianMT model for this language
        marian_code = SUPPORTED_LANGUAGES.get(lang)
        if marian_code is None:
            logger.info(f"No MarianMT model for detected language '{lang}'. Returning original text.")
            return {
                "translated_text": text,
                "translated_title": title,
                "language_detected": lang,
                "was_translated": False,
            }

        # Translate body
        translated_text = self._translate_text(text, marian_code)

        # Translate title (if provided and non-empty)
        translated_title = title
        if title and title.strip():
            translated_title = self._translate_text(title, marian_code)

        return {
            "translated_text": translated_text,
            "translated_title": translated_title,
            "language_detected": lang,
            "was_translated": True,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_language(self, text: str) -> str:
        """Detect language using langdetect. Returns ISO-639-1 code or 'unknown'."""
        try:
            # Use first 2000 chars for speed
            sample = text[:2000]
            lang = detect(sample)
            logger.debug(f"Detected language: {lang}")
            return lang
        except LangDetectException:
            logger.warning("Language detection failed; treating as unknown.")
            return "unknown"

    def _get_pipeline(self, marian_code: str):
        """Get or create a cached MarianMT pipeline for a given language."""
        if marian_code not in self._pipelines:
            model_name = f"Helsinki-NLP/opus-mt-{marian_code}-en"
            logger.info(f"Loading translation model: {model_name}")
            try:
                self._pipelines[marian_code] = hf_pipeline(
                    "translation",
                    model=model_name,
                    device=-1,  # CPU; set to 0 for GPU
                )
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
                return None
        return self._pipelines[marian_code]

    def _chunk_text(self, text: str) -> list:
        """Split text into sentence-aware chunks of ≤ MAX_CHUNK_CHARS."""
        if self._nlp is not None:
            doc = self._nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        else:
            # Fallback: split on period + space
            import re as _re
            sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", text) if s.strip()]

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # If a single sentence exceeds max, hard-split it
            if len(sentence) > MAX_CHUNK_CHARS:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                # Split long sentence by MAX_CHUNK_CHARS
                for i in range(0, len(sentence), MAX_CHUNK_CHARS):
                    chunks.append(sentence[i : i + MAX_CHUNK_CHARS])
                continue

            if len(current_chunk) + len(sentence) + 1 > MAX_CHUNK_CHARS:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                current_chunk = f"{current_chunk} {sentence}".strip()

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [text]

    def _translate_text(self, text: str, marian_code: str) -> str:
        """Translate text using the MarianMT pipeline with chunking."""
        translator = self._get_pipeline(marian_code)
        if translator is None:
            return text  # Fallback: return original

        chunks = self._chunk_text(text)
        translated_chunks = []

        for chunk in chunks:
            try:
                result = translator(chunk, max_length=512)
                translated_chunks.append(result[0]["translation_text"])
            except Exception as e:
                logger.warning(f"Translation failed for chunk ({len(chunk)} chars): {e}")
                translated_chunks.append(chunk)  # Keep original on failure

        return " ".join(translated_chunks)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_translator: Optional[ArticleTranslator] = None


def get_translator() -> ArticleTranslator:
    """Get or create the global ArticleTranslator instance."""
    global _translator
    if _translator is None:
        _translator = ArticleTranslator()
    return _translator


def translate_article(text: str, title: str = "") -> dict:
    """Convenience wrapper around ArticleTranslator.translate()."""
    return get_translator().translate(text, title)
