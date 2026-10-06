"""
database/db.py
----------------------------------------------------------------------
Minimal SQLite storage for report history, entirely optional.

Per the spec's privacy requirements: nothing is stored unless the user
explicitly chooses "Save this result" in the UI, and every saved
report can be deleted from the Results Dashboard. No file bytes or
images are ever stored in the database, only the extracted/analyzed
summary needed to redisplay a past result.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from config.settings import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    language TEXT NOT NULL,
    summary_json TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def save_report(language: str, summary: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO reports (created_at, language, summary_json) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), language, json.dumps(summary)),
        )
        return cur.lastrowid


def list_reports() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, language, summary_json FROM reports ORDER BY id DESC"
        ).fetchall()
    return [{
        "id": r[0],
        "created_at": r[1],
        "language": r[2],
        "summary": json.loads(r[3]) if r[3] else {}
    } for r in rows]


def get_report(report_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, created_at, language, summary_json FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "created_at": row[1], "language": row[2],
        "summary": json.loads(row[3]),
    }


def delete_report(report_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        return cur.rowcount > 0
