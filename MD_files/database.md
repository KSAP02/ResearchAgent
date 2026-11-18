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
| `config/config.toml` | bind-mounted `./config` | System hyperparameters | ✅ |
| `.env` | host only | Secrets (API keys) | ✅ |
| LangSmith | cloud | Traces, evaluation datasets and results | ⚪ Phase 2 / 10 |

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

### 3.1 `research_runs` ✅ live (columns to be extended)

One row per research question asked.

**Current schema (Phase 0):**

```sql
CREATE TABLE research_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    question            TEXT NOT NULL,
    report              TEXT,               -- final report (markdown)
    retry_count         INTEGER,            -- research loops taken
    evidence_sufficient INTEGER,            -- 0/1
    papers_json         TEXT,               -- list of paper dicts (temporary, see below)
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Planned additions:**

| Column | Type | Phase | Why |
|--------|------|-------|-----|
| `config_json` | TEXT | 2 | Snapshot of `config.toml` used for the run, so experiments can be compared |
| `queries_json` | TEXT | 2 | Planner output |
| `status` | TEXT | 7–9 | `running` / `interrupted` / `completed` / `failed` |
| `thread_id` | TEXT UNIQUE | 7 | Links the run to its LangGraph checkpoint thread |
| `error` | TEXT | 7 | Failure message, for resume |
| `report_json` | TEXT | 10 | Structured `Report` (sections, references) |
| `updated_at` | TEXT | 7 | Last state change |

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

### 3.5 `run_events` ❔ undecided (Phase 9)

Node-level progress log for the UI timeline. Might not be needed if the
checkpointer (Phase 7) and streaming (Phase 9) cover it. We'll decide in Phase 9.

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
| LLM traces, token usage, latency | LangSmith (Phase 2+) |
| Evaluation datasets + scores | LangSmith (Phase 10) |
| Original PDFs | Not kept; downloaded, chunked, then discarded (only chunks are stored) |

---

## 7. Conventions

- **Migrations:** today tables are created with `CREATE TABLE IF NOT EXISTS` in
  `backend/db/sqlite.py`. The first column change (Phase 2, `config_json`) brings in a
  lightweight migration step: a `schema_version` table + ordered `ALTER TABLE`
  steps run at startup. No Alembic unless this grows.
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
