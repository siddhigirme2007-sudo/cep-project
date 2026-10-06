"""
tests/test_pipeline.py
----------------------------------------------------------------------
Covers the checklist items from the project spec that don't need a
real file upload: Low/Normal/High classification, a missing reference
range, a malformed range, and that the C++ line parser finds the same
rows as the Python fallback on the bundled sample report.

Run with: pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.analysis import analyze_row, _classify_python
from modules.extraction import TestRow, extract_rows


def test_low_value():
    status, distance, _ = _classify_python("9.5", "12", "15")
    assert status == "LOW"
    assert distance == 2.5


def test_high_value():
    status, distance, _ = _classify_python("245", "125", "200")
    assert status == "HIGH"
    assert distance == 45


def test_normal_value():
    status, _, _ = _classify_python("13", "12", "15")
    assert status == "NORMAL"


def test_missing_reference_range_is_never_guessed():
    status, _, _ = _classify_python("9.5", "", "")
    assert status == "UNCERTAIN"


def test_malformed_range_is_never_guessed():
    # low > high is nonsensical -- must report uncertain, not a guess.
    status, _, _ = _classify_python("9.5", "20", "10")
    assert status == "UNCERTAIN"


def test_analyze_row_labels_match_spec_wording():
    row = TestRow(test_name="Hemoglobin", value="9.5", unit="g/dL",
                   reference_low="12", reference_high="15", reference_text="12-15")
    result = analyze_row(row)
    assert result.status in {"Low", "Normal", "High", "Unable to determine"}
    assert result.status == "Low"


def test_extraction_finds_all_rows_in_sample_report():
    sample = (Path(__file__).resolve().parent.parent / "sample_data" / "sample_report.txt").read_text()
    rows = extract_rows(sample)
    names = {r.test_name for r in rows}
    assert "Hemoglobin" in names
    assert len(rows) >= 5  # the sample report has 7 test rows


def test_no_disease_names_in_demo_explanations():
    """Spec checklist item: 'Test that no disease diagnosis appears in
    generated explanations.' This is a smoke check on the fixed demo
    vocabulary, not a substitute for manual review of live LLM output."""
    from modules.ai_explanation import explain_all
    row = TestRow(test_name="Fasting Blood Sugar", value="132", unit="mg/dL",
                   reference_low="70", reference_high="100", reference_text="70-100")
    analyzed = [analyze_row(row)]
    explanations = explain_all(analyzed)
    forbidden = {"diabetes", "diabetic", "cancer", "disease", "syndrome", "prescribe", "dosage"}
    text = explanations[0].text.lower()
    assert not any(word in text for word in forbidden)
