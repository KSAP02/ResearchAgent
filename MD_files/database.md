# Database Design

Every table, collection and file the project stores data in, with its schema and
status. **Update this file whenever a schema changes** (see `CLAUDE.md`).

Status legend: ✅ **live** (exists now) · 🟡 **planned** (proposed; finalised in the listed phase) · ⚪ **external** (not ours to manage)

---

## 1. Where data lives

| Store | Location (Docker) | Holds | Status |
|-------|-------------------|-------|--------|
| SQLite `app.db` | `/data/app.db` (volume `research_data`) | Application data: runs, papers, user settings | ✅ |
| Milvus Lite `milvus.db` | `/data/milvus.db` (same volume) | Passage chunks + embeddings | ✅ (empty until Phase 5) |
| SQLite `checkpoints.db` | `/data/checkpoints.db` | LangGraph checkpoints (workflow state per step) | 🟡 Phase 7 |
| `settings/config.toml` | bind-mounted `./settings` | System hyperparameters | ✅ |
| `.env` | host only | Secrets (API keys) | ✅ |
| ~~LangSmith~~ | (not used) | Replaced by our own `trace_spans` + eval tables | — |

**Why separate `checkpoints.db`?** Checkpoints are *workflow state* managed by
LangGraph (its own schema and growth pattern); `app.db` is *application data*
we design. Keeping them apart means either can be reset without touching the other.

**Local (non-Docker) paths:** the same files under `<repo>/data_warehouse/`.
**Reset everything:** `docker compose down -v`.

---

## 2. Entity overview

```mermaid
erDiagram
    research_runs ||--o{ run_papers : "found"
    papers ||--o{ run_papers : "appears in"
    papers ||--o{ paper_passages : "chunked into (Milvus)"
    research_runs ||--o| checkpoints : "thread_id (Phase 7)"
    user_settings

    research_runs {
        int id PK
        text question
        text status
        text thread_id
        text config_json
        text report
        text report_json
    }
    papers {
        text arxiv_id PK
        text title
        text pdf_url
        text ingest_status
    }
    run_papers {
        int run_id FK
        text arxiv_id FK
        text found_by_query
        int research_round
    }
    paper_passages {
        int pk PK
        float_vector vector
        text text
        text arxiv_id
        int page
    }
    user_settings {
        text user_id PK
        text data_json
    }
```

---

## 3. SQLite `app.db`

### 3.1 `research_runs` ✅ live (migration 2)

One row per research question asked. Created as `running` before the graph
starts (so trace spans can reference it), then finished as `completed` / `failed`.

```sql
CREATE TABLE research_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    question            TEXT NOT NULL,
    report              TEXT,               -- final report (markdown)
    retry_count         INTEGER,            -- research loops taken
    evidence_sufficient INTEGER,            -- 0/1
    papers_json         TEXT,               -- list of paper dicts (temporary, see below)
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    -- migration 2 (Phase 2)
    status              TEXT NOT NULL DEFAULT 'completed', -- running | completed | failed (+ interrupted, Phase 8)
    config_json         TEXT,               -- snapshot of all config sections used (no secrets)
    queries_json        TEXT,               -- planner output
    rationale           TEXT,               -- planner's explanation
    duration_ms         INTEGER,            -- wall-clock run time
    total_tokens        INTEGER,            -- input + output tokens over all LLM spans
    est_cost_usd        REAL,               -- from [pricing]; NULL when prices are 0
    error               TEXT,               -- failure message
    updated_at          TEXT
);
```

Rows from before migration 2 keep `status='completed'` and NULLs in the new columns.

**Still planned:**

| Column | Type | Phase | Why |
|--------|------|-------|-----|
| `thread_id` | TEXT UNIQUE | 7 | Links the run to its LangGraph checkpoint thread |
| `report_json` | TEXT | 10 | Structured `Report` (sections, references) |

`papers_json` is replaced by the `run_papers` table in Phase 3 and then dropped.

### 3.2 `user_settings` ✅ live

Per-user preferences (Settings page). One row per user; single user `default` for now.

```sql
CREATE TABLE user_settings (
    user_id    TEXT PRIMARY KEY,           -- "default" until auth exists
    data_json  TEXT NOT NULL,              -- UserSettings model as JSON
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

`data_json` shape (validated by `backend/user_settings.py`; invalid or old data falls back to defaults):

```json
{
  "appearance": { "theme": "system", "font_size": "medium", "density": "comfortable", "sidebar_collapsed": false },
  "research":   { "report_length": "standard", "citation_style": "numeric",
                  "review_plan_before_research": false, "show_trace_details": false }
}
```

Stored as JSON (not one column per preference) on purpose: adding a preference
only needs a model change and no migration.

### 3.3 `papers` 🟡 planned (Phase 3, ingest columns in Phase 5)

A cache of arXiv papers, shared across runs (a paper is fetched and embedded once).

```sql
CREATE TABLE papers (
    arxiv_id         TEXT PRIMARY KEY,     -- e.g. "2404.16130" (version stripped)
    title            TEXT NOT NULL,
    authors_json     TEXT,                 -- ["A. Author", ...]
    abstract         TEXT,
    primary_category TEXT,                 -- e.g. "cs.CL"
    published        TEXT,                 -- ISO date
    updated          TEXT,
    abs_url          TEXT,
    pdf_url          TEXT,
    -- Phase 5: ingestion
    ingest_status    TEXT DEFAULT 'pending', -- pending | ingested | abstract_only | failed
    ingest_error     TEXT,
    num_chunks       INTEGER,
    ingested_at      TEXT,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 `run_papers` 🟡 planned (Phase 3)

Which papers each run found, and how (a many-to-many link).

```sql
CREATE TABLE run_papers (
    run_id         INTEGER NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    arxiv_id       TEXT    NOT NULL REFERENCES papers(arxiv_id),
    found_by_query TEXT,                   -- the search query that surfaced it
    research_round INTEGER DEFAULT 0,      -- 0 = first pass, 1+ = evidence-loop retries
    PRIMARY KEY (run_id, arxiv_id)
);
```

### 3.5 `trace_spans` ✅ live (migration 2)

Our own tracing, written by `backend/tracing/recorder.py` (`TraceRecorder`, a LangChain
callback handler). One row per graph / node / chain / LLM / tool / retriever call;
`parent_span_id` builds the tree. Rows are inserted on *start* (`status='running'`) and
updated on *end*, so a run in progress can be inspected. LangGraph's internal plumbing
runs (tagged `langsmith:hidden`) are skipped and their children re-parented.

```sql
CREATE TABLE trace_spans (
    span_id           TEXT PRIMARY KEY,     -- LangChain run_id (UUID)
    run_id            INTEGER NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    parent_span_id    TEXT,                 -- LangChain parent_run_id; NULL = root
    name              TEXT NOT NULL,        -- e.g. "planner", "ChatOpenAI", "search_arxiv"
    span_type         TEXT NOT NULL,        -- graph | node | chain | llm | tool | retriever
    status            TEXT NOT NULL,        -- running | ok | error
    -- (FK enforced: PRAGMA foreign_keys = ON)
    started_at        TEXT NOT NULL,        -- ISO-8601 UTC, ms precision
    ended_at          TEXT,
    duration_ms       INTEGER,
    inputs_json       TEXT,                 -- truncated to [tracing].max_payload_chars
    outputs_json      TEXT,
    error             TEXT,
    model             TEXT,                 -- llm spans only
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,              -- includes reasoning tokens
    reasoning_tokens  INTEGER,              -- reasoning models only
    metadata_json     TEXT                  -- tags, langgraph_node/step/triggers, invocation_params (llm)
);
CREATE INDEX idx_trace_spans_run ON trace_spans(run_id, started_at);
```

### 3.6 `run_events` ❔ undecided (Phase 9)

Node-level progress log for the UI timeline. Probably not needed: `trace_spans`
(Phase 2) plus streaming (Phase 9) should cover it. We'll decide in Phase 9.

```sql
-- sketch only
CREATE TABLE run_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER REFERENCES research_runs(id) ON DELETE CASCADE,
    node       TEXT,          -- planner, researcher, ...
    event      TEXT,          -- started | finished | retry | error
    payload    TEXT,          -- JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Milvus Lite `milvus.db`

### 4.1 Collection `paper_passages` ✅ live (empty), schema changes in Phase 5

**Current (Phase 0, created by `MilvusClient.create_collection` quick setup):**

| Field | Type | Notes |
|-------|------|-------|
| `id` | INT64, primary key, auto_id | |
| `vector` | FLOAT_VECTOR(1536) | dim from `[embeddings].dimension` |
| (dynamic fields) | JSON | quick-setup collections accept any extra keys |

Metric: `[retrieval].metric` (COSINE). Index: AUTOINDEX.

**Planned (Phase 5), managed by `langchain-milvus` `Milvus` vector store:**

| Field | Type | Notes |
|-------|------|-------|
| `pk` | INT64, auto_id | **Passage ID** used in citations (validated in Phase 6) |
| `vector` | FLOAT_VECTOR(1536) | OpenAI `text-embedding-3-small` |
| `text` | VARCHAR | chunk text (`[ingest].chunk_size` chars) |
| `arxiv_id` | VARCHAR | → `papers.arxiv_id`; used as a filter (`arxiv_id in [...]`) |
| `title` | VARCHAR | denormalised for display |
| `page` | INT64 | page number from `PyMuPDFLoader` |
| `chunk_index` | INT64 | order within the paper |
| `source` | VARCHAR | `pdf` or `abstract` (fallback) |

In Phase 5 the hand-made collection is dropped and LangChain creates its own.
Changing the embedding model or dimension needs a new collection name or an empty collection.

---

## 5. LangGraph checkpoints `checkpoints.db` 🟡 planned (Phase 7)

Created and managed by `langgraph-checkpoint-sqlite` (`SqliteSaver.setup()`).
We **don't design or migrate these tables**; we only read them through the API
(`graph.get_state`, `get_state_history`). They store, per `thread_id`: every
checkpoint (the full state after each step), pending writes, and parent links
(used for replay and forks).

Link to app data: `research_runs.thread_id` = LangGraph `thread_id`.

Optional (Phase 7): LangGraph long-term **Store** for memory across threads (for
example "papers this user already knows"). Decide then.

---

## 6. Not stored by us

| Data | Where |
|------|-------|
| Original PDFs | Not kept; downloaded, chunked, then discarded (only chunks are stored) |

---

## 7. Conventions

- **Migrations:** `MIGRATIONS` in `backend/db/sqlite.py` is an ordered list of
  `(version, description, [SQL])`, applied once at startup and recorded in
  `schema_version(version, description, applied_at)`. Never edit an applied
  migration; append a new one. `/api/health` reports the current version.
  Applied: 1 = base tables, 2 = Phase 2 run metadata + `trace_spans`.
- **Connection settings:** `PRAGMA journal_mode=WAL` (reads while a run writes spans),
  `PRAGMA foreign_keys=ON`, 10 s busy timeout.
- **Timestamps:** UTC, ISO-8601 text (`CURRENT_TIMESTAMP`).
- **JSON columns:** `*_json` suffix; always validated through a Pydantic model on read.
- **IDs:** runs = integer autoincrement; papers = arXiv ID without the version;
  passages = Milvus `pk`; LangGraph threads = UUID string.
- **Licensing:** paper text is stored as chunks for personal research and quoted
  with citations; never republished in full.

---

## 8. Change log

| Date | Change |
|------|--------|
| 2026-11-18 | Phase 0: `research_runs`; Milvus `paper_passages` (384-dim, later 1536-dim, empty) |
| 2026-11-18 | Phase 1: `user_settings` table (JSON prefs) |
| 2026-11-18 | Documented planned schema: `papers`, `run_papers`, `research_runs` additions, Milvus Phase 5 fields, `checkpoints.db` |
| 2026-11-18 | Decided: no LangSmith. Planned `trace_spans` (Phase 2) + `research_runs` status/duration/tokens/cost columns |
| 2026-11-18 | **Migration 2 (Phase 2), live:** `schema_version` table; `research_runs` + status, config_json, queries_json, rationale, duration_ms, total_tokens, est_cost_usd, error, updated_at; `trace_spans` (+ `reasoning_tokens`) with index on (run_id, started_at); WAL + foreign keys on |
