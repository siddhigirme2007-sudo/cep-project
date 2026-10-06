"""
modules/analysis.py
----------------------------------------------------------------------
Compares each extracted test value against its own printed reference
range and assigns Low / Normal / High / Unable to determine.

Rule (from the spec, followed exactly, no exceptions):
    value < low   -> Low
    value > high  -> High
    otherwise     -> Normal
    range missing or ambiguous -> Unable to determine (never guessed)

Primary path: the compiled C binary (native/classify), which is the
single source of truth for this decision. Falls back to an identical
pure-Python comparison if the binary hasn't been built yet.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from config.settings import CLASSIFY_BIN
from modules.extraction import TestRow


@dataclass
class AnalyzedTest:
    test_name: str
    value: str
    unit: str
    reference_low: str
    reference_high: str
    reference_text: str
    status: str          # "Low" | "Normal" | "High" | "Unable to determine"
    distance: float = 0.0
    percent: float = 0.0


def _classify_native(value: str, low: str, high: str) -> tuple[str, float, float] | None:
    if not CLASSIFY_BIN.exists():
        return None
    try:
        result = subprocess.run(
            [str(CLASSIFY_BIN), value or "nan", low or "nan", high or "nan"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) != 3:
        return None
    status_raw, distance, percent = parts
    try:
        return status_raw, float(distance), float(percent)
    except ValueError:
        return None


def _classify_python(value: str, low: str, high: str) -> tuple[str, float, float]:
    try:
        v, lo, hi = float(value), float(low), float(high)
        if lo > hi:
            return "UNCERTAIN", 0.0, 0.0
    except (TypeError, ValueError):
        return "UNCERTAIN", 0.0, 0.0

    if v < lo:
        distance = lo - v
        percent = (distance / lo * 100) if lo else 0.0
        return "LOW", distance, percent
    if v > hi:
        distance = v - hi
        percent = (distance / lo * 100) if lo else 0.0
        return "HIGH", distance, percent
    return "NORMAL", 0.0, 0.0


_STATUS_LABELS = {
    "LOW": "Low",
    "HIGH": "High",
    "NORMAL": "Normal",
    "UNCERTAIN": "Unable to determine",
}


def analyze_row(row: TestRow) -> AnalyzedTest:
    native = _classify_native(row.value, row.reference_low, row.reference_high)
    status_raw, distance, percent = native if native is not None else _classify_python(
        row.value, row.reference_low, row.reference_high
    )

    reference_text = row.reference_text or (
        f"{row.reference_low}-{row.reference_high}" if row.reference_low and row.reference_high else "Not printed on report"
    )

    return AnalyzedTest(
        test_name=row.test_name,
        value=row.value,
        unit=row.unit,
        reference_low=row.reference_low or "",
        reference_high=row.reference_high or "",
        reference_text=reference_text,
        status=_STATUS_LABELS.get(status_raw, "Unable to determine"),
        distance=distance,
        percent=percent,
    )


def analyze_rows(rows: list[TestRow]) -> list[AnalyzedTest]:
    return [analyze_row(r) for r in rows]
