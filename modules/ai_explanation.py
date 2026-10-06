"""
modules/ai_explanation.py
----------------------------------------------------------------------
Turns one AnalyzedTest into a short, patient-friendly explanation.

Two modes:
- Live mode (GEMINI_API_KEY set): calls Gemini directly in the target
  language, asking it to produce fully translated output.
- Demo/fallback mode (no key, or the API call fails): uses the
  centralized medical_terms.build_explanation() which generates
  complete, grammatically correct Hindi / Marathi / English explanations
  with no mixing of languages.

Pipeline:
    AnalyzedTest + lang
        → try Gemini API (returns text in target language)
        → fallback: medical_terms.build_explanation()
"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import DEMO_MODE, GEMINI_API_KEY, LLM_MODEL, SYSTEM_PROMPT
from modules.analysis import AnalyzedTest
from modules.medical_terms import (
    build_explanation,
    translated_test_name,
    _get_description,   # used for Gemini context (English description)
)


@dataclass
class Explanation:
    text: str
    source: str  # "llm" | "demo_template"


def _call_gemini(test: AnalyzedTest, lang: str = "en") -> str | None:
    if not GEMINI_API_KEY:
        return None
    import json
    import urllib.request

    # Build the English description for grounding context
    canonical = test.test_name
    en_desc = _get_description(canonical, "en")

    lang_instruction = {
        "en": (
            "Write a 2-3 sentence patient-friendly explanation in plain English. "
            "Do not diagnose diseases or prescribe treatment."
        ),
        "hi": (
            "रोगी के लिए 2-3 वाक्यों में सरल हिंदी में स्पष्टीकरण लिखें। "
            "पूरा उत्तर केवल हिंदी में होना चाहिए — कोई भी अंग्रेज़ी शब्द "
            "न हो (परीक्षण का नाम, संख्याएँ और इकाइयाँ जैसे g/dL को छोड़कर)। "
            "कोई बीमारी का नाम न लें, कोई दवा न सुझाएँ।"
        ),
        "mr": (
            "रुग्णासाठी 2-3 वाक्यांत सोप्या मराठीत स्पष्टीकरण लिहा. "
            "संपूर्ण उत्तर फक्त मराठीत असावे — कोणताही इंग्रजी शब्द नसावा "
            "(चाचणीचे नाव, संख्या आणि g/dL सारख्या एककांशिवाय). "
            "कोणताही आजार सांगू नका, कोणतीही औषधे सुचवू नका."
        ),
    }

    user_message = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Test name: {canonical}\n"
        f"What it measures: {en_desc}\n"
        f"Result: {test.value} {test.unit}\n"
        f"Reference range on report: {test.reference_text}\n"
        f"Status (do not recompute): {test.status}\n\n"
        f"{lang_instruction.get(lang, lang_instruction['en'])}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({"contents": [{"parts": [{"text": user_message}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def _call_anthropic(test: AnalyzedTest) -> str | None:
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        en_desc = _get_description(test.test_name, "en")
        user_message = (
            f"Test name: {test.test_name}\n"
            f"What it measures: {en_desc}\n"
            f"Result: {test.value} {test.unit}\n"
            f"Reference range: {test.reference_text}\n"
            f"Status (pre-computed, do not recompute): {test.status}\n\n"
            "Write a 2-3 sentence patient-friendly explanation following "
            "your system instructions exactly. Do not diagnose or prescribe."
        )
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=250,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        parts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip() or None
    except Exception:
        return None


def explain(test: AnalyzedTest, lang: str = "en") -> Explanation:
    """
    Returns a patient-friendly Explanation in the target language.
    Tries Gemini API first (responds in target language), then falls
    back to the local medical_terms templates which are 100% correct
    in English, Hindi, and Marathi with no language mixing.
    """
    if not DEMO_MODE:
        gemini_text = _call_gemini(test, lang)
        if gemini_text:
            return Explanation(text=gemini_text, source="llm")
        anthropic_text = _call_anthropic(test)
        if anthropic_text:
            # Anthropic returns English — translate via medical_terms fallback
            return Explanation(
                text=build_explanation(
                    test.test_name, lang, test.status,
                    test.value, test.unit, test.reference_text,
                ),
                source="demo_template",
            )

    # Demo mode or all API calls failed — use local templates
    return Explanation(
        text=build_explanation(
            test.test_name, lang, test.status,
            test.value, test.unit, test.reference_text,
        ),
        source="demo_template",
    )


def explain_all(tests: list[AnalyzedTest], lang: str = "en") -> list[Explanation]:
    return [explain(t, lang) for t in tests]
