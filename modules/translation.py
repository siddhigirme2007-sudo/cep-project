"""
modules/translation.py
----------------------------------------------------------------------
Translation utilities for MediExplain AI.

Primary responsibility:
- Provide translate_safety_notice() for the safety banner
- Provide translate_status() for status badge labels
- Provide translate_test_name() for the test name column
- Provide translate() for free-form LLM-generated English text that
  needs to be translated (Gemini API → deep-translator → no-op)

Demo-template explanations are already generated in the target language
by modules/medical_terms.py and do NOT pass through this module.
"""

from __future__ import annotations

from config.settings import GEMINI_API_KEY, SUPPORTED_LANGUAGES
from modules.medical_terms import (
    SAFETY_NOTICES,
    STATUS_LABELS,
    translated_test_name as _medical_translated_name,
    translated_status as _medical_translated_status,
)


# ─── Public API ─────────────────────────────────────────────────────────────

def translate_safety_notice(lang: str) -> str:
    """Returns the safety disclaimer in the target language."""
    return SAFETY_NOTICES.get(lang, SAFETY_NOTICES["en"])


def translate_status(status: str, lang: str) -> str:
    """Translates a status label (Low/Normal/High/Unable to determine)."""
    return _medical_translated_status(status, lang)


def translate_test_name(canonical: str, lang: str) -> str:
    """Translates a canonical English test name to the target language."""
    return _medical_translated_name(canonical, lang)


def translate(text: str, lang: str) -> str:
    """
    Translates free-form English text (LLM-generated) into the target language.
    Used only when the LLM produces English output that must be translated.
    Falls back gracefully through: Gemini API → deep-translator → original text.
    """
    if lang == "en" or lang not in SUPPORTED_LANGUAGES:
        return text

    # 1. Try Gemini API
    gemini = _gemini_translate(text, lang)
    if gemini:
        return gemini

    # 2. Try deep-translator (Google Translate)
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source="en", target=lang).translate(text)
        if result:
            return result
    except Exception:
        pass

    # 3. Return original — better than garbled output
    return text


# ─── Internal helpers ────────────────────────────────────────────────────────

def _gemini_translate(text: str, lang: str) -> str | None:
    if not GEMINI_API_KEY:
        return None
    import json
    import urllib.request

    lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
    prompt = (
        f"Translate the following patient-friendly medical explanation from English "
        f"into fluent, simple {lang_name}. Keep the medical tone clear and supportive. "
        f"Preserve all numbers, units, and reference ranges exactly as they appear. "
        f"Output only the translation with no explanation:\n\n{text}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None
