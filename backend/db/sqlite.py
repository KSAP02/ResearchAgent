"""SQLite store (stdlib sqlite3, no ORM): runs, trace spans, user settings.

Schema changes go through MIGRATIONS (ordered, applied once, tracked in
schema_version). Document every change in MD_files/database.md.
"""
import json
import sqlite3
from contextlib import contextmanager

from config import get_settings

# (version, description, statements). Never edit an applied migration; add a new one.
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "base tables", [
        """CREATE TABLE IF NOT EXISTS research_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT NOT NULL,
            report      TEXT,
            retry_count INTEGER,
            evidence_sufficient INTEGER,
            papers_json TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS user_settings (
            user_id    TEXT PRIMARY KEY,
            data_json  TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
    ]),
    (2, "phase 2: run metadata + trace_spans", [
        "ALTER TABLE research_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'",
        "ALTER TABLE research_runs ADD COLUMN config_json TEXT",
        "ALTER TABLE research_runs ADD COLUMN queries_json TEXT",
        "ALTER TABLE research_runs ADD COLUMN rationale TEXT",
        "ALTER TABLE research_runs ADD COLUMN duration_ms INTEGER",
        "ALTER TABLE research_runs ADD COLUMN total_tokens INTEGER",
        "ALTER TABLE research_runs ADD COLUMN est_cost_usd REAL",
        "ALTER TABLE research_runs ADD COLUMN error TEXT",
        "ALTER TABLE research_runs ADD COLUMN updated_at TEXT",
        """CREATE TABLE trace_spans (
            span_id           TEXT PRIMARY KEY,
            run_id            INTEGER NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            parent_span_id    TEXT,
            name              TEXT NOT NULL,
            span_type         TEXT NOT NULL,
            status            TEXT NOT NULL,
            started_at        TEXT NOT NULL,
            ended_at          TEXT,
            duration_ms       INTEGER,
            inputs_json       TEXT,
            outputs_json      TEXT,
            error             TEXT,
            model             TEXT,
            prompt_tokens     INTEGER,
            completion_tokens INTEGER,
            reasoning_tokens  INTEGER,
            metadata_json     TEXT
        )""",
        "CREATE INDEX idx_trace_spans_run ON trace_spans(run_id, started_at)",
    ]),
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(get_settings().sqlite_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Apply pending migrations in order."""
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")  # concurrent reads while a run writes spans
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        for version, description, statements in MIGRATIONS:
            if version <= current:
                continue
            for stmt in statements:
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_version (version, description) VALUES (?, ?)", (version, description))


def schema_version() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]


# ---------------------------------------------------------------- runs
def create_run(question: str, config: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO research_runs (question, status, config_json, updated_at)"
            " VALUES (?, 'running', ?, CURRENT_TIMESTAMP)",
            (question, json.dumps(config)),
        )
        return cur.lastrowid


def finish_run(run_id: int, *, status: str, result: dict | None, duration_ms: int,
               total_tokens: int, est_cost_usd: float | None, error: str | None = None) -> None:
    result = result or {}
    with get_conn() as conn:
        conn.execute(
            """UPDATE research_runs SET
                 status = ?, report = ?, retry_count = ?, evidence_sufficient = ?, papers_json = ?,
                 queries_json = ?, rationale = ?, duration_ms = ?, total_tokens = ?, est_cost_usd = ?,
                 error = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                status,
                result.get("report"),
                result.get("retry_count"),
                int(bool(result.get("evidence_sufficient"))) if result else None,
                json.dumps(result.get("papers", [])),
                json.dumps(result.get("queries", [])),
                result.get("rationale"),
                duration_ms,
                total_tokens,
                est_cost_usd,
                error,
                run_id,
            ),
        )


def _run_row_to_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    for key in ("config_json", "queries_json", "papers_json"):
        raw = d.pop(key, None)
        d[key.removesuffix("_json")] = json.loads(raw) if raw else None
    if d.get("evidence_sufficient") is not None:
        d["evidence_sufficient"] = bool(d["evidence_sufficient"])
    return d


def list_runs(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, question, status, retry_count, evidence_sufficient, duration_ms, total_tokens,
                      est_cost_usd, created_at, json_extract(config_json, '$.llm.model') AS model,
                      json_extract(config_json, '$.llm.reasoning_effort') AS reasoning_effort,
                      json_array_length(queries_json) AS num_queries
               FROM research_runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("evidence_sufficient") is not None:
            d["evidence_sufficient"] = bool(d["evidence_sufficient"])
        out.append(d)
    return out


def run_stats() -> dict:
    with get_conn() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS runs,
                      SUM(status = 'completed') AS completed,
                      SUM(status = 'failed') AS failed,
                      AVG(CASE WHEN status = 'completed' THEN duration_ms END) AS avg_duration_ms,
                      SUM(total_tokens) AS total_tokens,
                      SUM(est_cost_usd) AS total_cost_usd
               FROM research_runs"""
        ).fetchone()
    return dict(r)


def get_run(run_id: int) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    return _run_row_to_dict(r) if r else None


# ---------------------------------------------------------------- trace spans
def insert_span(span: dict) -> None:
    cols = ", ".join(span)
    marks = ", ".join("?" for _ in span)
    with get_conn() as conn:
        conn.execute(f"INSERT OR REPLACE INTO trace_spans ({cols}) VALUES ({marks})", tuple(span.values()))


def update_span(span_id: str, fields: dict) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE trace_spans SET {sets} WHERE span_id = ?", (*fields.values(), span_id))


def get_spans(run_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trace_spans WHERE run_id = ? ORDER BY started_at, rowid", (run_id,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for key in ("inputs_json", "outputs_json", "metadata_json"):
            raw = d.pop(key)
            d[key.removesuffix("_json")] = json.loads(raw) if raw else None
        out.append(d)
    return out


def run_token_totals(run_id: int) -> dict:
    with get_conn() as conn:
        r = conn.execute(
            """SELECT COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                      COALESCE(SUM(completion_tokens), 0) AS completion_tokens
               FROM trace_spans WHERE run_id = ? AND span_type = 'llm'""",
            (run_id,),
        ).fetchone()
    return dict(r)


# ---------------------------------------------------------------- user settings
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
