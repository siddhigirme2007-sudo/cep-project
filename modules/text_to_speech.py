"""
modules/text_to_speech.py
----------------------------------------------------------------------
Generates a playable audio file for one explanation's text.

Live path: gTTS (Google Text-to-Speech), which supports English,
Marathi and Hindi voices and needs an internet connection.
A strict timeout (3 s per call) prevents this from blocking the
entire API response — the frontend already uses the browser's own
speechSynthesis API as a complete, always-available fallback.

Fallback path: if gTTS isn't installed, the network call fails, or
the timeout fires, returns success=False with audio_file=None.
The frontend handles this gracefully and uses browser TTS instead,
so the "Listen" button always works even fully offline.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path

from config.settings import OUTPUT_DIR

_LANG_MAP = {"en": "en", "mr": "mr", "hi": "hi"}

# Maximum seconds we'll wait for a gTTS network call before giving up
# and falling back to browser speechSynthesis.
# Set to 0 to skip gTTS entirely (use browser TTS always).
# Only increase this if you have a reliable fast internet connection
# and want server-side audio files.
_GTTS_TIMEOUT_S = 5


@dataclass
class TTSResult:
    success: bool
    audio_file: str | None = None  # relative path under outputs/, or None
    error: str | None = None


def synthesize(text: str, lang: str) -> TTSResult:
    if not text.strip():
        return TTSResult(success=False, error="No text to speak.")

    try:
        from gtts import gTTS
    except ImportError:
        return TTSResult(success=False, error="gTTS not installed; using browser voice instead.")

    gtts_lang = _LANG_MAP.get(lang, "en")

    # Cache by content hash so repeated requests for the same
    # explanation + language don't regenerate audio every time.
    digest = hashlib.sha256(f"{gtts_lang}:{text}".encode("utf-8")).hexdigest()[:16]
    filename = f"tts_{digest}.mp3"
    out_path: Path = OUTPUT_DIR / filename

    # Serve cached file immediately — no network call needed.
    if out_path.exists():
        return TTSResult(success=True, audio_file=filename)

    # Run gTTS in a thread with a strict timeout so we never block
    # the Flask response for more than _GTTS_TIMEOUT_S seconds.
    result: list[TTSResult] = []

    def _run() -> None:
        try:
            tts = gTTS(text=text, lang=gtts_lang)
            tts.save(str(out_path))
            result.append(TTSResult(success=True, audio_file=filename))
        except Exception as exc:  # noqa: BLE001
            result.append(TTSResult(
                success=False,
                error=f"TTS service unavailable ({exc}); using browser voice instead.",
            ))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_GTTS_TIMEOUT_S)

    if result:
        return result[0]

    # Timeout hit — browser speechSynthesis will handle playback.
    return TTSResult(
        success=False,
        error="TTS timed out; using browser voice instead.",
    )
