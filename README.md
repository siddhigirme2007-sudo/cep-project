# MediExplain AI

**Multilingual Medical Report Simplifier with Voice & Visual Analytics**  
*A college project prototype (2nd-year BTech CSE, AI/DS).*

MediExplain AI helps patients understand complex laboratory reports in plain language. A user uploads a lab report (PDF/JPG/JPEG/PNG), and the application OCR-reads it, extracts test parameters, compares each value against the reference range **printed on that same report**, visualizes the results with interactive charts, explains them simply in **English, Marathi, or Hindi**, and reads the report aloud with speech synthesis.

> **Safety Disclaimer:** MediExplain AI never diagnoses a disease, never prescribes medicines, and never invents a reference range. It is strictly for educational reference and report understanding.

---

## ✨ Key Features

- ⭐ **Visual Result Charts**: Interactive horizontal gauge bar for each test showing Low, Normal, or High regions with an exact value marker pin.
- 🔍 **Search Tests & Filter Toolbar**: Instant search for specific tests (e.g. Hemoglobin, Glucose, WBC) with quick status filtering (All, Low, Normal, High).
- 📑 **Download PDF Summary**: Export simplified report summaries as styled PDF documents with full multilingual Unicode support (Hindi, Marathi, English) via `html2pdf.js`.
- 📈 **Report Comparison**: Compare current lab reports against older saved reports side-by-side with delta values (`+2.6 g/dL`) and trend status badges (`Improved 🟢`, `Attention 🔴`, `Stable 🔵`).
- 👤 **User History Dashboard**: Save analyzed reports locally into an SQLite database (`database/db.py`), view saved historical reports, compare trends over time, or delete old records.
- 🔊 **Listen to Full Report**: One-click audio playback that reads the entire simplified report out loud in your chosen language using browser speech synthesis.
- 🤖 **Google Gemini API Integration**: Uses Google Gemini (`gemini-flash-latest`) for live AI explanations and fluent Marathi & Hindi translations, with automatic offline demo fallbacks.

---

## 🛠️ Architecture & Polyglot Stack

This project is built using a deliberate polyglot architecture:

| Layer | Technology | Function |
|---|---|---|
| **Frontend** | HTML5 / CSS3 / JavaScript | Single-page UI with custom design system, interactive charts, PDF export, voice synthesis, search, history & comparison. |
| **Backend API** | Python (Flask) | JSON REST API orchestrating OCR → Extraction → Analysis → AI Explanation → Translation → SQLite Storage. |
| **Data Extraction** | C++ (`native/parse_lines.cpp`) | High-speed C++ parser for extracting test names, values, units, and ranges from raw OCR text line-by-line. |
| **Classification** | C (`native/classify.c`) | Fast C executable for deterministic Low / Normal / High classification against reference ranges. |
| **Database** | SQLite (`database/db.py`) | Privacy-focused optional report history storage. |

*Note: Python automatically falls back to pure-Python implementations if native C/C++ binaries are not compiled.*

---

## 📁 Project Structure

```text
mediexplain-ai/
├── app.py                     # Flask backend & JSON API routes
├── requirements.txt           # Python dependencies
├── .env                       # Local environment variables (API keys)
├── .env.example               # Template environment configuration
├── config/settings.py         # Config, Gemini/Anthropic settings, language definitions
├── database/
│   ├── db.py                  # SQLite database manager (Report History)
│   └── mediexplain.db         # SQLite database file (created automatically)
├── modules/
│   ├── ocr.py                 # Tesseract OCR & OpenCV image preprocessing
│   ├── extraction.py          # Native C++ / Python fallback line extractor
│   ├── analysis.py            # Native C / Python fallback classification
│   ├── ai_explanation.py      # Gemini / Anthropic LLM explanations & demo fallback
│   ├── translation.py         # Gemini API / deep-translator / offline phrase table
│   └── text_to_speech.py      # gTTS / Web Speech API voice handler
├── native/
│   ├── classify.c             # C reference-range classifier
│   ├── parse_lines.cpp        # C++ OCR text parser
│   └── build.bat / build.sh   # Compilation scripts for Windows / Linux
├── static/
│   ├── css/style.css          # Design system, layout, and visual chart CSS
│   └── js/app.js              # Application router, speech, PDF export & search logic
├── templates/
│   └── index.html             # Main single-page application UI
├── sample_data/               # Sample lab report image & text for testing
└── tests/                     # Pytest suite for classification & pipeline logic
```

---

## 🔑 Step-by-Step Google Gemini API Key Integration Guide

MediExplain AI uses **Google Gemini 1.5 Flash** to generate live, patient-friendly medical explanations and perform fluent translations into **Marathi (`mr`)**, **Hindi (`hi`)**, and **English (`en`)**.

Follow these exact steps to obtain and integrate your API key:

### Step 1: Obtain a Free Google Gemini API Key
1. Go to **[Google AI Studio](https://aistudio.google.com/app/apikey)** in your web browser.
2. Sign in with any standard Google account.
3. Click the blue **"Create API Key"** button.
4. Copy the generated API key string (starts with `AIzaSy...`).

### Step 2: Configure the API Key in Your Project
1. Open the [`.env`](file:///c:/Users/Admin/Downloads/mediexplain-ai%20%282%29/mediexplain-ai/.env) file located in the project root directory (a template `.env` file is already created for you).
2. Add or paste your API key as follows:
   ```env
   # Paste your Google Gemini API key below:
   GEMINI_API_KEY=AIzaSyYourActualKeyHere
   
   # Optional: set preferred model
   MEDIEXPLAIN_LLM_MODEL=gemini-flash-latest
   ```
3. Save the `.env` file.

### Step 3: Run / Restart the Application
Start or restart your Flask server:
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

### Step 4: Verification & Fallback Behavior
- When `GEMINI_API_KEY` is present, the app status badge will show live AI mode, generating tailored LLM explanations and translating explanations directly into Marathi and Hindi.
- If no key is set or network is offline, the app automatically switches to **Demo Mode**, utilizing safe pre-written template explanations and offline translation phrase tables so the application always works.

---

## 🧪 Testing

Run the automated test suite using `pytest`:

```bash
pytest tests/
```

Tests verify:
- Low / Normal / High classification logic.
- Missing or malformed reference ranges.
- C++ line parser vs. Python fallback consistency.
- Safety checks ensuring no disease names or diagnoses are generated.

---

## 🛡️ Safety & Privacy Principles

1. **No Stored Image Bytes**: Uploaded report images are analyzed in-memory and deleted immediately after processing.
2. **Explicit History Saving**: Data is only saved to local SQLite history if the user explicitly clicks "Save Report to History".
3. **No Invented Ranges**: If a reference range cannot be clearly read from the report, the status is labeled *"Unable to determine"* rather than guessed.
4. **Non-Diagnostic**: Strictly provides plain-language explanations of test definitions and status relative to printed report reference ranges.

---

## 📜 License & Academic Note

Developed as a student project prototype for BTech CSE (AI/DS). Not intended for medical diagnosis or clinical treatment.
