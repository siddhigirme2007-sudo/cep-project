"""
modules/extraction.py
----------------------------------------------------------------------
Turns raw OCR text into a list of structured candidate test rows:
{ test_name, value, unit, reference_low, reference_high, reference_text }

Primary path: pipe the OCR text into the compiled C++ helper
(native/parse_lines), which is fast and battle-tested against a fixed
regex grammar for "name value unit low-high" style rows.

Fallback path: a pure-Python re-implementation of the same grammar, used
automatically if the native binary hasn't been compiled yet (see
native/build.sh) — so the app runs on a fresh checkout with zero setup.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from config.settings import PARSE_LINES_BIN
from modules.medical_terms import normalize_test_name


@dataclass
class TestRow:
    test_name: str        # canonical English name (normalized)
    value: str
    unit: str
    reference_low: str
    reference_high: str
    reference_text: str


_ROW_RE = re.compile(
    r"""^(?P<name>.*?[A-Za-z][A-Za-z\)\]\.\s]*?)\s+
        (?P<value>-?\d+(?:\.\d+)?)\s*
        (?P<unit_a>[A-Za-z\u00b5/%]*)\s*
        [:\-]?\s*(?:\(?\s*Ref\.?:?\s*)?
        (?P<low>-?\d+(?:\.\d+)?)\s*
        (?:-|\u2013|to)\s*
        (?P<high>-?\d+(?:\.\d+)?)\s*\)?\s*
        (?P<unit_b>[A-Za-z\u00b5/%]*)\s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _extract_python_fallback(raw_text: str) -> list[TestRow]:
    rows: list[TestRow] = []
    for raw_line in raw_text.splitlines():
        line = _normalize(raw_line)
        if len(line) < 4:
            continue
        m = _ROW_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        if not name:
            continue
        unit = m.group("unit_a").strip() or m.group("unit_b").strip()
        low, high = m.group("low"), m.group("high")
        try:
            if float(low) > float(high):
                low, high = "", ""
        except ValueError:
            low, high = "", ""
        rows.append(TestRow(
            test_name=normalize_test_name(name),   # ← normalize here
            value=m.group("value"),
            unit=unit,
            reference_low=low,
            reference_high=high,
            reference_text=f"{low}-{high}" if low else "",
        ))
    return rows


def _extract_native(raw_text: str) -> list[TestRow] | None:
    if not PARSE_LINES_BIN.exists():
        return None
    try:
        result = subprocess.run(
            [str(PARSE_LINES_BIN)],
            input=raw_text,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    rows: list[TestRow] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 6:
            continue
        name, value, unit, low, high, ref_text = parts
        rows.append(TestRow(normalize_test_name(name), value, unit, low, high, ref_text))
    return rows


def extract_rows(raw_text: str) -> list[TestRow]:
    """Extracts candidate lab-test rows from raw OCR text.

    Tries the compiled C++ parser first (native/parse_lines); falls
    back to an equivalent pure-Python implementation if it isn't
    built yet, so nothing about the app is blocked on compiling C++.
    """
    native_rows = _extract_native(raw_text)
    if native_rows is not None:
        return native_rows
    return _extract_python_fallback(raw_text)
