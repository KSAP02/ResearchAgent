"""SQLite store for research runs and user settings (stdlib sqlite3, no ORM yet)."""
import json
import sqlite3
from contextlib import contextmanager

from config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT NOT NULL,
    report      TEXT,
    retry_count INTEGER,
    evidence_sufficient INTEGER,
    papers_json TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id    TEXT PRIMARY KEY,
    data_json  TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(get_settings().sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def save_run(question: str, report: str, retry_count: int, sufficient: bool, papers: list[dict]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO research_runs (question, report, retry_count, evidence_sufficient, papers_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (question, report, retry_count, int(sufficient), json.dumps(papers)),
        )
        return cur.lastrowid


def list_runs(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, question, retry_count, evidence_sufficient, created_at"
            " FROM research_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def load_user_settings(user_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT data_json FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    return json.loads(row["data_json"]) if row else None


def save_user_settings(user_id: str, data: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_settings (user_id, data_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)"
            " ON CONFLICT(user_id) DO UPDATE SET data_json = excluded.data_json, updated_at = CURRENT_TIMESTAMP",
            (user_id, json.dumps(data)),
        )
