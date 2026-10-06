"""
app.py
----------------------------------------------------------------------
MediExplain AI — Flask backend.

Serves the frontend (templates/index.html + static/) and a small JSON
API that runs the full pipeline:

    upload -> OCR -> extraction (C++) -> analysis (C) ->
    explanation (LLM or demo template) -> translation -> TTS

Run:
    python app.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template

from config.settings import (
    ALLOWED_EXTENSIONS, DEMO_MODE, MAX_UPLOAD_MB, OUTPUT_DIR,
    SAFETY_DISCLAIMER, SUPPORTED_LANGUAGES, PLANNED_LANGUAGES, UPLOAD_DIR,
)
from modules import ocr, extraction, analysis, ai_explanation, translation, text_to_speech
from modules.translation import translate_test_name, translate_status
from database import db

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.get("/")
def index():
    return render_template(
        "index.html",
        languages=SUPPORTED_LANGUAGES,
        planned_languages=PLANNED_LANGUAGES,
        demo_mode=DEMO_MODE,
        safety_disclaimer=SAFETY_DISCLAIMER,
    )


@app.get("/api/config")
def api_config():
    return jsonify({
        "languages": SUPPORTED_LANGUAGES,
        "planned_languages": PLANNED_LANGUAGES,
        "demo_mode": DEMO_MODE,
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "max_upload_mb": MAX_UPLOAD_MB,
    })


@app.post("/api/analyze")
def api_analyze():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file was included in the request."}), 400

    file = request.files["file"]
    lang = request.form.get("language", "en")
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    if file.filename == "":
        return jsonify({"success": False, "error": "No file was selected."}), 400
    if not _allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "Unsupported file type. Please upload a PDF, JPG, JPEG, or PNG.",
        }), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    saved_path: Path = UPLOAD_DIR / saved_name
    file.save(saved_path)

    try:
        ocr_result = ocr.extract_text(saved_path)
        if not ocr_result.success:
            return jsonify({"success": False, "error": ocr_result.error}), 422

        rows = extraction.extract_rows(ocr_result.text)
        if not rows:
            return jsonify({
                "success": False,
                "error": (
                    "No recognizable test rows were found in this report. "
                    "Try a clearer scan, or a report with a simple table layout."
                ),
                "raw_text_preview": ocr_result.text[:800],
            }), 422

        analyzed = analysis.analyze_rows(rows)
        explanations = ai_explanation.explain_all(analyzed, lang)

        tests_payload = []
        for test, expl in zip(analyzed, explanations):
            # Demo templates are generated directly in target language.
            # Only translate if LLM returned English text.
            if expl.source == "demo_template" or lang == "en":
                translated_text = expl.text
            else:
                translated_text = translation.translate(expl.text, lang)

            tts_result = text_to_speech.synthesize(translated_text, lang)
            tests_payload.append({
                "test_name":          test.test_name,           # canonical English
                "display_test_name":  translate_test_name(test.test_name, lang),  # translated
                "value":              test.value,
                "unit":               test.unit,
                "reference_low":      test.reference_low,
                "reference_high":     test.reference_high,
                "reference_text":     test.reference_text,
                "status":             test.status,              # English (Low/Normal/High)
                "display_status":     translate_status(test.status, lang),  # translated
                "explanation":        translated_text,
                "explanation_source": expl.source,
                "audio_file":         tts_result.audio_file,
                "audio_error":        tts_result.error,
            })

        return jsonify({
            "success": True,
            "language": lang,
            "demo_mode": DEMO_MODE,
            "safety_notice": translation.translate_safety_notice(lang),
            "ocr_warnings": ocr_result.warnings,
            "tests": tests_payload,
        })
    finally:
        # Uploaded file bytes are never kept longer than one request.
        try:
            saved_path.unlink(missing_ok=True)
        except OSError:
            pass


@app.get("/outputs/<path:filename>")
def serve_audio(filename: str):
    return send_from_directory(OUTPUT_DIR, filename)


@app.post("/api/reports")
def api_save_report():
    payload = request.get_json(force=True)
    report_id = db.save_report(payload.get("language", "en"), payload.get("summary", {}))
    return jsonify({"success": True, "id": report_id})


@app.get("/api/reports")
def api_list_reports():
    return jsonify({"success": True, "reports": db.list_reports()})


@app.get("/api/reports/<int:report_id>")
def api_get_report(report_id: int):
    report = db.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": "Report not found."}), 404
    return jsonify({"success": True, "report": report})


@app.delete("/api/reports/<int:report_id>")
def api_delete_report(report_id: int):
    deleted = db.delete_report(report_id)
    return jsonify({"success": deleted})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
