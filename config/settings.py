"""
Central configuration for MediExplain AI.

Everything that might change between machines (API keys, folders,
which native binaries to call) lives here so the rest of the codebase
never hard-codes a path or a secret.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Automatically load .env file if present
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        for line in _env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

# --- Folders -----------------------------------------------------------
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
NATIVE_DIR = BASE_DIR / "native"
DB_PATH = BASE_DIR / "database" / "mediexplain.db"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# --- Native binaries -----------------------------------------------------
# Built by native/build.sh (or build.bat on Windows). analysis.py and
# extraction.py fall back to a pure-Python implementation automatically
# if a binary is missing, so the app still runs before you compile them.
CLASSIFY_BIN = NATIVE_DIR / ("classify.exe" if os.name == "nt" else "classify")
PARSE_LINES_BIN = NATIVE_DIR / ("parse_lines.exe" if os.name == "nt" else "parse_lines")

# Windows often needs an explicit path to tesseract.exe; leave blank on
# Linux/macOS where it's normally already on PATH after installation.
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
if not TESSERACT_CMD and os.name == "nt":
    possible_tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
    ]
    for p in possible_tesseract_paths:
        if os.path.exists(p):
            TESSERACT_CMD = p
            break


# --- Uploads -------------------------------------------------------------
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_UPLOAD_MB = 15

# --- Languages -----------------------------------------------------------
SUPPORTED_LANGUAGES = {
    "en": "English",
    "mr": "Marathi",
    "hi": "Hindi",
}
# Kept separate from SUPPORTED_LANGUAGES so the UI can show them as
# "coming soon" per the spec's future-scope section, without any code
# path treating them as usable yet.
PLANNED_LANGUAGES = {
    "gu": "Gujarati", "kn": "Kannada", "ta": "Tamil",
    "te": "Telugu", "bn": "Bengali", "pa": "Punjabi",
}

# --- AI / LLM --------------------------------------------------------------
# Never hard-code a key. Reads from the environment (see .env.example).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("MEDIEXPLAIN_LLM_MODEL", "gemini-flash-latest" if GEMINI_API_KEY else "claude-sonnet-4-6")

# If no key is configured, the app runs in DEMO_MODE: it uses safe,
# template-based explanations instead of calling an LLM, so the whole
# pipeline can still be demonstrated end-to-end offline.
DEMO_MODE = not bool(GEMINI_API_KEY or ANTHROPIC_API_KEY)

SAFETY_DISCLAIMER = (
    "For educational/report-understanding purposes only. This does not "
    "provide diagnosis or treatment. Consult a qualified healthcare "
    "professional."
)

SYSTEM_PROMPT = """You are MediExplain AI, a medical-report explanation assistant.
Your job is to simplify laboratory-report information for general understanding.
Use only the extracted information supplied to you. Explain what a test measures
in simple language and explain whether the supplied result is below, within, or
above the supplied reference range. Do not diagnose a disease. Do not name a
disease based on the result. Do not prescribe medicines, dosage, supplements, or
treatment. Do not claim certainty when OCR/extraction is uncertain. Do not
invent reference ranges. Encourage the user to consult a qualified healthcare
professional for interpretation and medical decisions. Keep the response concise
and easy to understand."""
