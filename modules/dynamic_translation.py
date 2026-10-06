"""
modules/dynamic_translation.py
----------------------------------------------------------------------
Dynamic translation engine for medical test names and explanations.

When a test name is NOT found in the local medical_terms dictionary,
this module uses the Gemini API to:
1. Translate the test name into the target language
2. Generate a complete patient-friendly explanation in the target language

This makes the system truly universal — it can handle ANY legitimate
medical/laboratory test name, not just the ~100 pre-defined ones.

Safety rules (enforced in every prompt):
- Never diagnose a disease
- Never prescribe medicines or treatment
- Never claim certainty about a medical condition
- Preserve all numerical values, units, and reference ranges exactly
- Use only the supplied result and reference range
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import NamedTuple

from config.settings import GEMINI_API_KEY, SYSTEM_PROMPT

# Timeout for Gemini API calls (seconds). Short so it never blocks rendering.
_TIMEOUT = 6

_LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
}

# ── Status phrase templates in each language (used to build safe explanations)
_STATUS_PHRASES: dict[str, dict[str, str]] = {
    "Low": {
        "en": "below the reference range printed on your report",
        "hi": "आपकी रिपोर्ट पर छपी संदर्भ सीमा से कम",
        "mr": "तुमच्या अहवालावर दिलेल्या संदर्भ श्रेणीपेक्षा कमी",
    },
    "Normal": {
        "en": "within the reference range printed on your report",
        "hi": "आपकी रिपोर्ट पर छपी संदर्भ सीमा के भीतर",
        "mr": "तुमच्या अहवालावर दिलेल्या संदर्भ श्रेणीमध्ये",
    },
    "High": {
        "en": "above the reference range printed on your report",
        "hi": "आपकी रिपोर्ट पर छपी संदर्भ सीमा से अधिक",
        "mr": "तुमच्या अहवालावर दिलेल्या संदर्भ श्रेणीपेक्षा जास्त",
    },
}

_SAFETY_SUFFIX: dict[str, str] = {
    "en": (
        "This result alone does not determine the cause. "
        "Please discuss this with a qualified healthcare professional."
    ),
    "hi": (
        "केवल इस परिणाम से कारण निर्धारित नहीं किया जा सकता। "
        "कृपया इसके बारे में किसी योग्य स्वास्थ्य विशेषज्ञ से चर्चा करें।"
    ),
    "mr": (
        "केवळ या निकालावरून कारण निश्चित करता येत नाही. "
        "कृपया याबद्दल पात्र वैद्यकीय तज्ञांशी चर्चा करा."
    ),
}

_UNABLE_SUFFIX: dict[str, str] = {
    "en": (
        "We could not reliably read the reference range for this test "
        "from your report. Please check this with a qualified healthcare professional."
    ),
    "hi": (
        "हम आपकी रिपोर्ट से इस जाँच की संदर्भ सीमा विश्वसनीय रूप से नहीं पढ़ सके। "
        "कृपया किसी योग्य स्वास्थ्य विशेषज्ञ से इसकी जाँच कराएँ।"
    ),
    "mr": (
        "आम्ही तुमच्या अहवालातून या चाचणीची संदर्भ श्रेणी विश्वसनीयपणे वाचू शकलो नाही. "
        "कृपया पात्र वैद्यकीय तज्ञांकडून याची तपासणी करा."
    ),
}


class DynamicResult(NamedTuple):
    translated_name: str       # test name in target language
    explanation: str           # complete explanation in target language
    source: str                # "gemini" | "template"


def _call_gemini(prompt: str) -> str | None:
    """Calls Gemini API. Returns text or None on failure."""
    if not GEMINI_API_KEY:
        return None
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def _extract_json(raw: str) -> dict | None:
    """Extracts the first JSON object from a string (handles markdown fences)."""
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def translate_unknown_test(
    canonical: str,
    lang: str,
    status: str,
    value: str,
    unit: str,
    reference_text: str,
) -> DynamicResult:
    """
    For a medical test name not in the local dictionary, uses Gemini to:
    1. Translate the test name into the target language.
    2. Generate a complete patient-friendly explanation in the target language.

    Falls back to a safe template if Gemini is unavailable.
    All numerical values, units, and reference ranges are passed in and
    must remain unchanged.
    """
    lang_name = _LANG_NAMES.get(lang, lang)
    unit_str = f" {unit}" if unit else ""
    ref_str = f" ({reference_text})" if reference_text else ""

    if GEMINI_API_KEY:
        prompt = f"""{SYSTEM_PROMPT}

You are given a medical laboratory test result. Return ONLY valid JSON with exactly these two fields:
{{
  "translated_name": "<test name translated into {lang_name}>",
  "explanation": "<complete patient-friendly explanation in {lang_name}>"
}}

Rules:
- "translated_name": Translate "{canonical}" into natural {lang_name}. If it is a well-known medical abbreviation (e.g. TSH, HbA1c, CBC), keep the abbreviation but add the {lang_name} expanded meaning in parentheses if helpful.
- "explanation": Write 3-4 sentences in {lang_name} only. Explain what this test measures in simple terms. State that the patient's result is {value}{unit_str}, which is {_STATUS_PHRASES.get(status, {}).get(lang, f"the reported status: {status}")} {ref_str}. End with: "{_SAFETY_SUFFIX.get(lang, _SAFETY_SUFFIX['en'])}"
- Do NOT diagnose any disease.
- Do NOT prescribe medicines or treatment.
- Do NOT change the numbers: {value}, {reference_text}.
- Write entirely in {lang_name} (except the test abbreviation and numbers).
- Output only the JSON object, no extra text.

Test name: {canonical}
Result: {value}{unit_str}
Reference range from report: {reference_text if reference_text else "not available"}
Status (pre-computed, do not change): {status}
"""
        raw = _call_gemini(prompt)
        if raw:
            parsed = _extract_json(raw)
            if parsed and "translated_name" in parsed and "explanation" in parsed:
                t_name = str(parsed["translated_name"]).strip() or canonical
                expl = str(parsed["explanation"]).strip()
                if expl:
                    return DynamicResult(
                        translated_name=t_name,
                        explanation=expl,
                        source="gemini",
                    )

    # ── Gemini unavailable or failed: safe template fallback ──────────────────
    t_name = canonical  # keep English name for unknown tests without Gemini
    lang_or_en = lang if lang in ("en", "hi", "mr") else "en"

    # Build template sentences per language without injecting the English test name,
    # so that the TTS voice doesn't stumble reading English words in a Hindi/Marathi sentence.
    _INTRO: dict[str, str] = {
        "en": "{name} is a laboratory test. Your result is {value}{unit_str}, which is {status_phrase}{ref_str}. {safety}",
        "hi": "यह एक प्रयोगशाला जाँच है। आपका परिणाम {value}{unit_str} है, जो {status_phrase}{ref_str} है। {safety}",
        "mr": "ही एक प्रयोगशाळा चाचणी आहे. तुमचा निकाल {value}{unit_str} आहे, जो {status_phrase}{ref_str} आहे. {safety}",
    }
    _INTRO_UNABLE: dict[str, str] = {
        "en": "{name} is a laboratory test. Your result is {value}{unit_str}. {safety}",
        "hi": "यह एक प्रयोगशाला जाँच है। आपका परिणाम {value}{unit_str} है। {safety}",
        "mr": "ही एक प्रयोगशाळा चाचणी आहे. तुमचा निकाल {value}{unit_str} आहे. {safety}",
    }

    if status in _STATUS_PHRASES and lang_or_en in _STATUS_PHRASES[status]:
        expl = _INTRO.get(lang_or_en, _INTRO["en"]).format(
            name=canonical,
            value=value,
            unit_str=unit_str,
            status_phrase=_STATUS_PHRASES[status][lang_or_en],
            ref_str=ref_str,
            safety=_SAFETY_SUFFIX.get(lang_or_en, _SAFETY_SUFFIX["en"]),
        )
    else:
        expl = _INTRO_UNABLE.get(lang_or_en, _INTRO_UNABLE["en"]).format(
            name=canonical,
            value=value,
            unit_str=unit_str,
            safety=_UNABLE_SUFFIX.get(lang_or_en, _UNABLE_SUFFIX["en"]),
        )

    return DynamicResult(
        translated_name=t_name,
        explanation=expl,
        source="template",
    )


def translate_test_name_dynamic(canonical: str, lang: str) -> str:
    """
    Translates a test name not in the local dictionary using Gemini.
    Returns the English name if translation fails.
    """
    if lang == "en" or not GEMINI_API_KEY:
        return canonical

    lang_name = _LANG_NAMES.get(lang, lang)
    prompt = (
        f"Translate the medical laboratory test name \"{canonical}\" into {lang_name}. "
        f"If it is a known abbreviation (e.g. TSH, HbA1c), keep the abbreviation "
        f"and add the {lang_name} expanded meaning in parentheses if helpful. "
        f"Output only the translated name, nothing else."
    )
    result = _call_gemini(prompt)
    if result and len(result) < 200 and result.strip():
        # Sanity check: reject if it looks like an error or JSON
        if not result.startswith("{") and "\n" not in result.strip():
            return result.strip()
    return canonical
