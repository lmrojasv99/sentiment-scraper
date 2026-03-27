"""Translation Module — MarianMT via Hugging Face Transformers.

Detects the source language of article text, splits it into
sentence-aware chunks (≤512 chars), and translates to English using
Helsinki-NLP MarianMT models with direct tokenizer + model batching.

Key improvements over the pipeline-based approach:
  - Batch tokenization with padding for faster multi-chunk articles
  - GPU / MPS / CPU auto-selection
  - Correct model IDs for 90+ languages (patched known 404 paths)
  - Models cached per language code for reuse across articles
"""

import gc
import logging
import re
from typing import Optional, Tuple

import torch
from langdetect import detect, LangDetectException
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logger = logging.getLogger(__name__)

# Sentences are grouped into chunks of at most this many characters
MAX_CHUNK_CHARS = 512

# Number of chunks translated in a single forward pass
BATCH_SIZE = 16

# ---------------------------------------------------------------------------
# Compute device
# ---------------------------------------------------------------------------
if torch.cuda.is_available():
    _DEVICE = torch.device("cuda")
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    _DEVICE = torch.device("mps")
else:
    _DEVICE = torch.device("cpu")

# ---------------------------------------------------------------------------
# Model map: langdetect code → HuggingFace model ID
# ---------------------------------------------------------------------------
# Base list: all codes that have a standard Helsinki-NLP/opus-mt-{lang}-en model
_BASE_LANGS = [
    'af', 'am', 'ar', 'az', 'be', 'bg', 'bi', 'bn', 'ca', 'cs', 'cy', 'da',
    'de', 'ee', 'eo', 'es', 'et', 'eu', 'fi', 'fj', 'fr', 'ga', 'gl',
    'gv', 'ha', 'he', 'hi', 'ho', 'ht', 'hu', 'hy', 'id', 'ig', 'is',
    'it', 'ja', 'ka', 'kg', 'kj', 'kl', 'ko', 'lg', 'ln', 'lu', 'lv',
    'mg', 'mh', 'mk', 'ml', 'mr', 'ms', 'mt', 'ng', 'nl', 'no', 'ny', 'om',
    'pa', 'pl', 'rn', 'ru', 'rw', 'sg', 'sk', 'sl', 'sm',
    'sn', 'sq', 'ss', 'st', 'sv', 'sw', 'th', 'ti', 'tl', 'tn', 'to', 'tr',
    'ts', 'tw', 'ty', 'uk', 'ur', 've', 'vi', 'wa', 'xh', 'yo', 'zh',
]

TRANSLATION_MODELS: dict = {lang: f'Helsinki-NLP/opus-mt-{lang}-en' for lang in _BASE_LANGS}

# Patch known broken / renamed model paths on HuggingFace Hub
TRANSLATION_MODELS.update({
    'hr': 'Helsinki-NLP/opus-mt-tc-big-sh-en',  # Croatian → Serbo-Croatian big model
    'sh': 'Helsinki-NLP/opus-mt-tc-big-sh-en',  # Serbo-Croatian
    'el': 'Helsinki-NLP/opus-mt-grk-en',         # Greek → Greek-family model
    'lt': 'Helsinki-NLP/opus-mt-tc-big-lt-en',  # Lithuanian → big model
    'pt': 'Helsinki-NLP/opus-mt-ROMANCE-en',     # Portuguese → Romance-family
    'ro': 'Helsinki-NLP/opus-mt-ROMANCE-en',     # Romanian → Romance-family
    'ne': 'Helsinki-NLP/opus-mt-ine-en',         # Nepali → Indo-European family
})


class ArticleTranslator:
    """Translates article text to English using Helsinki-NLP MarianMT models.

    Uses direct AutoTokenizer + AutoModelForSeq2SeqLM for batched inference,
    which is more efficient than the HuggingFace `pipeline` wrapper when
    processing multi-chunk articles.

    Usage:
        translator = ArticleTranslator()
        result = translator.translate(text, title)
        # result["translated_text"], result["language_detected"], result["was_translated"]
    """

    def __init__(self):
        # lang_code -> (AutoTokenizer, AutoModelForSeq2SeqLM)
        self._cache: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate(self, text: str, title: str = "") -> dict:
        """Translate article body (and optionally title) to English.

        Returns dict with keys:
            translated_text   (str)  — English text (original if already English)
            translated_title  (str)  — English title
            language_detected (str)  — ISO-639-1 code from langdetect
            was_translated    (bool) — whether translation was applied
        """
        if not text or not text.strip():
            return {
                "translated_text": text or "",
                "translated_title": title or "",
                "language_detected": "unknown",
                "was_translated": False,
            }

        lang = self._detect_language(text)

        if lang in ("en", "unknown"):
            return {
                "translated_text": text,
                "translated_title": title,
                "language_detected": lang,
                "was_translated": False,
            }

        if lang not in TRANSLATION_MODELS:
            logger.info(f"No MarianMT model for detected language '{lang}'. Returning original.")
            return {
                "translated_text": text,
                "translated_title": title,
                "language_detected": lang,
                "was_translated": False,
            }

        translated_text = self._translate_text(text, lang)
        translated_title = self._translate_text(title, lang) if title and title.strip() else title

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
        """Return ISO-639-1 code detected by langdetect, or 'unknown'."""
        try:
            lang = detect(text[:2000])
            # Normalise Chinese variants
            if lang.startswith('zh'):
                return 'zh'
            return lang
        except LangDetectException:
            logger.warning("Language detection failed; treating as unknown.")
            return "unknown"

    def _get_model(self, lang: str) -> Tuple[Optional[object], Optional[object]]:
        """Return cached (tokenizer, model) for the given language code."""
        if lang not in self._cache:
            model_id = TRANSLATION_MODELS[lang]
            logger.info(f"Loading translation model: {model_id} (device={_DEVICE})")
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_id)
                model = AutoModelForSeq2SeqLM.from_pretrained(model_id).to(_DEVICE)
                model.eval()
                self._cache[lang] = (tokenizer, model)
            except Exception as e:
                logger.error(f"Failed to load {model_id}: {e}")
                return None, None
        return self._cache[lang]

    def _split_sentences(self, text: str) -> list:
        """Split text into sentences using punctuation boundaries."""
        text = text.replace('\n', ' ').strip()
        sentences = [s.strip() for s in re.split(r'(?<=[.!?]) +', text) if s.strip()]
        return sentences if sentences else [text]

    def _chunk_text(self, text: str) -> list:
        """Group sentences into chunks of at most MAX_CHUNK_CHARS characters."""
        sentences = self._split_sentences(text)
        chunks = []
        current = ""

        for sent in sentences:
            if len(sent) > MAX_CHUNK_CHARS:
                # Flush current buffer, then hard-split the oversized sentence
                if current:
                    chunks.append(current)
                    current = ""
                for i in range(0, len(sent), MAX_CHUNK_CHARS):
                    chunks.append(sent[i:i + MAX_CHUNK_CHARS])
                continue

            if len(current) + len(sent) + 1 > MAX_CHUNK_CHARS:
                if current:
                    chunks.append(current)
                current = sent
            else:
                current = f"{current} {sent}".strip()

        if current:
            chunks.append(current)

        return chunks if chunks else [text]

    def _translate_text(self, text: str, lang: str) -> str:
        """Translate text by batching its sentence chunks through MarianMT."""
        tokenizer, model = self._get_model(lang)
        if tokenizer is None:
            return text  # model unavailable — return original

        chunks = self._chunk_text(text)
        translated: list = []

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            try:
                inputs = tokenizer(
                    batch,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512,
                ).to(_DEVICE)
                with torch.no_grad():
                    output_tokens = model.generate(**inputs, max_length=512)
                translated.extend(
                    tokenizer.batch_decode(output_tokens, skip_special_tokens=True)
                )
            except Exception as e:
                logger.warning(f"Batch translation failed ({len(batch)} chunks): {e}")
                translated.extend(batch)  # fall back to original chunks

        return " ".join(translated)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_translator: Optional[ArticleTranslator] = None


def get_translator() -> ArticleTranslator:
    """Return (or lazily create) the global ArticleTranslator instance."""
    global _translator
    if _translator is None:
        _translator = ArticleTranslator()
    return _translator


def translate_article(text: str, title: str = "") -> dict:
    """Convenience wrapper around ArticleTranslator.translate()."""
    return get_translator().translate(text, title)
