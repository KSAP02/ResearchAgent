# Project Scaffold Recipe: LangChain/LangGraph Agent as a Service

How this repo was scaffolded, so the same layout can be reused for a new
LangChain/LangGraph agent project. Follow the steps in order: at the end you
have a FastAPI backend running a LangGraph `StateGraph`, a TypeScript (React +
Vite) frontend, Milvus Lite + SQLite storage, and a `docker-compose` stack that
runs it all, verified end to end with stub nodes before any LLM code is written.

---

## 1. Stack

| Layer           | Choice                                   | Why |
|-----------------|------------------------------------------|-----|
| Agent graph     | LangGraph (`StateGraph`) + LangChain core | Shared state, conditional edges, cycles |
| LLM + embeddings| OpenAI via `langchain-openai`            | `ChatOpenAI` + `OpenAIEmbeddings` |
| Hyperparameters | `config/config.toml` (pydantic-settings TOML source) | Tune without touching code; two-way synced with an Admin page |
| UI routing      | `react-router-dom` + collapsible sidebar  | Pages added as sidebar entries |
| Backend API     | FastAPI + Uvicorn                        | Frontend calls it over HTTP |
| Vector DB       | Milvus Lite (`pymilvus` + `milvus-lite`)  | Single local file, no server |
| SQL DB          | SQLite (stdlib `sqlite3`)                | Single local file, zero setup |
| Frontend        | React + TypeScript + Vite                | Built to static files, served by nginx |
| Containers      | Docker + docker compose                  | One command runs both services |

Secrets go in `.env`, system hyperparameters in `config/config.toml` (Admin page), per-user preferences in SQLite (Settings page). See Steps 1, 2 and 8b.

## 2. Final layout

```text
<project>/
├── backend/
│   ├── app.py                 # FastAPI entry point (uvicorn app:app)
│   ├── config.py              # Settings: env (.env) > config.toml > defaults; hot reload
│   ├── llm.py                 # get_llm() / get_embeddings() factories
│   ├── form_schema.py         # Pydantic model -> form description for the UI
│   ├── user_settings.py       # per-user preference models
│   ├── routers/
│   │   ├── admin.py           # GET/PUT /api/admin/config  (config.toml)
│   │   └── user.py            # GET/PUT /api/user/settings (SQLite)
│   ├── schemas.py             # API request/response models
│   ├── agents/                # one file per graph node
│   │   ├── planner.py
│   │   ├── researcher.py      # researcher + retriever nodes
│   │   ├── analyst.py
│   │   ├── fact_checker.py    # evidence checker (drives the retry loop)
│   │   └── reporter.py
│   ├── tools/                 # plain functions the agents call
│   │   ├── arxiv_search.py
│   │   ├── pdf_extractor.py
│   │   └── vector_retriever.py
│   ├── graph/
│   │   ├── state.py           # TypedDict shared state
│   │   └── workflow.py        # StateGraph, edges, conditional routing
│   ├── db/
│   │   ├── sqlite.py          # run history
│   │   └── vector_store.py    # Milvus Lite client + collection init
│   ├── Dockerfile             # built with repo root as context
│   └── Dockerfile.dockerignore
├── frontend/
│   ├── src/
│   │   ├── main.tsx           # BrowserRouter + UserSettingsProvider
│   │   ├── App.tsx            # sidebar layout + routes
│   │   ├── styles.css         # design tokens (light/dark) + components
│   │   ├── api/client.ts      # typed fetch wrapper for /api/*
│   │   ├── components/        # Sidebar, FieldInput, Icons
│   │   ├── context/UserSettings.tsx
│   │   └── pages/             # Home, Settings, Admin
│   ├── index.html
│   ├── package.json / package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts         # dev proxy /api -> localhost:8000
│   ├── nginx.conf             # prod proxy /api -> backend:8000
│   ├── Dockerfile
│   └── .dockerignore
├── data_warehouse/            # local Milvus Lite + SQLite files (git-ignored)
│   └── .gitkeep
├── MD_files/                  # project docs (see "Docs layout" below)
│   ├── build_plan.md          # starts empty: idea, goals, phases
│   ├── database.md            # starts empty: every table/collection + schema
│   ├── build_phases/          # one record per finished phase
│   │   └── phase_NN_<name>.md
│   └── learning_notes.md      # (optional) what each phase taught
├── <name>_venv/               # local venv for IDE support (git-ignored)
├── requirements.txt           # shared by local venv + backend image
├── config/
│   └── config.toml            # ALL hyperparameters (committed, no secrets)
├── docker-compose.yml
├── .env.example               # committed; .env is not
├── .gitignore
├── .gitattributes             # * text=auto eol=lf (files go into Linux images)
├── CLAUDE.md                  # progress log + working rules
└── README.md
```

Every `agents/`, `tools/`, `graph/`, `db/` folder gets an empty `__init__.py`.

## 3. Step by step

### Step 1: Root files

```bash
mkdir -p backend/{agents,tools,graph,db,routers} frontend/src/{api,components,context,pages} \
         config data_warehouse MD_files/build_phases
touch backend/{agents,tools,graph,db,routers}/__init__.py data_warehouse/.gitkeep
touch MD_files/build_plan.md MD_files/database.md MD_files/build_phases/.gitkeep
```

**Docs layout (`MD_files/`):** create these empty at the start and fill them in as the project grows:

| File | Purpose | Updated when |
|------|---------|--------------|
| `build_plan.md` | Idea, goals, outcomes, phases with done-criteria | At planning time; tick phases as they finish |
| `database.md` | Every store (SQL tables, vector collections, checkpoint DBs, external services) with schema, status (live/planned) and a change log | **Every schema change** |
| `build_phases/phase_NN_<name>.md` | Record of a finished phase: what was built, DB changes, tests, decisions, issues | When a phase is done |
| `CLAUDE.md` (root) | Working rules, architecture, progress checklist, changelog | After every feature |

**`.gitignore`**: create it *first*, before any `.env` exists:

```gitignore
.env
.env.*
!.env.example
data_warehouse/*
!data_warehouse/.gitkeep
__pycache__/
*.py[cod]
.venv/
<name>_venv/
node_modules/
*.tsbuildinfo
dist/
```

**Split config in two:**

| File | Holds | Committed? |
|------|-------|-----------|
| `.env` | Secrets + deployment values (`OPENAI_API_KEY`, `CORS_ORIGINS`, `DATA_DIR`, `CONFIG_PATH`) | No (`.env.example` is) |
| `config/config.toml` | Every hyperparameter you might tune | Yes |

**`.env.example`**:

```env
OPENAI_API_KEY=
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
# DATA_DIR=      # unset locally -> <repo>/data_warehouse; compose sets /data
# CONFIG_PATH=   # unset locally -> <repo>/config/config.toml; compose sets /app/config/config.toml
# Override any config.toml value as SECTION__KEY, e.g. LLM__MODEL=gpt-4.1
```

**`config/config.toml`**: one table per concern; every node reads its knobs from here:

```toml
[llm]
provider = "openai"
model = "gpt-4.1-mini"
temperature = 0.2
max_tokens = 2000
timeout_s = 60
max_retries = 2

[embeddings]
provider = "openai"
model = "text-embedding-3-small"
dimension = 1536           # must match the model and the Milvus collection
batch_size = 64

[planner]
num_queries = 4

[research]
max_results_per_query = 5
max_papers_per_run = 12
sort_by = "relevance"
request_delay_s = 3.0

[ingest]
max_pdfs_per_run = 8
max_pdf_mb = 20
download_timeout_s = 30
chunk_size = 1000
chunk_overlap = 150

[retrieval]
top_k = 8
metric = "COSINE"
score_threshold = 0.0

[evidence]
max_retries = 2            # graph cycle cap
min_supported_ratio = 0.7

[report]
max_citations = 15

[storage]
sqlite_filename = "app.db"
milvus_filename = "milvus.db"
milvus_collection = "paper_passages"
```

### Step 2: Backend config (`backend/config.py`)

- One Pydantic `BaseModel` per TOML table (`LLMConfig`, `EmbeddingsConfig`, ...),
  nested as fields on a `pydantic-settings` `BaseSettings`. Collect them in a
  `SECTION_MODELS = {"llm": LLMConfig, ...}` dict.
- Every field carries UI metadata, which drives the Admin form:
  `Field(0.2, ge=0, le=2, description="...", json_schema_extra={"step": 0.1, "label": "...", "requires_restart": True, "danger": "..."})`.
  Use `Literal[...]` for choices (rendered as a select). The class docstring
  becomes the section description.
- `SettingsConfigDict(env_file=".env", env_nested_delimiter="__", toml_file=CONFIG_PATH)`,
  where `CONFIG_PATH = os.environ.get("CONFIG_PATH", <repo>/config/config.toml)`.
- Override `settings_customise_sources` to add `TomlConfigSettingsSource`.
  Precedence: **init > env > .env > config.toml > defaults**.
- `data_dir` defaults to `<repo>/data_warehouse`; Docker sets `DATA_DIR=/data`.
- Derived properties: `sqlite_path`, `milvus_uri` (built from `[storage]`).
- `public_summary()` dumps the config minus secrets for `GET /api/config`, so you
  can confirm what's actually loaded after a tweak.
- **Hot reload:** `get_settings()` keeps a cached `Settings` plus the file's
  `st_mtime_ns`; when the mtime changes it rebuilds. If the new file is invalid
  it **keeps the last good settings** and records the error (`last_load_error()`).
  `force_reload()` is called after the Admin page writes. Always call
  `get_settings()` at use time; never keep a module-level copy.

### Step 2b: Model factories (`backend/llm.py`)

- `get_llm()` → `ChatOpenAI(model, temperature, max_tokens, timeout, max_retries)` from `[llm]`.
- `get_embeddings()` → `OpenAIEmbeddings(model, dimensions, chunk_size)` from `[embeddings]`.
- The clients are cached **per distinct config tuple** (`lru_cache` on a helper that takes
  model/temperature/... as arguments), so a hot-reloaded config produces a new
  client automatically. Imports are lazy so stubs run without an API key.
- Nodes always call these and never construct clients themselves.

### Step 3: Storage (`backend/db/`)

- `sqlite.py`: `get_conn()` context manager (commit + close), `init_db()` runs
  `CREATE TABLE IF NOT EXISTS`, plus `save_run()` / `list_runs()`.
- `vector_store.py`: `MilvusClient(settings.milvus_uri)` (a file path makes it
  Milvus Lite), cached with `@lru_cache`; `init_vector_store()` creates the
  collection with `dimension = [embeddings].dimension` and `metric_type =
  [retrieval].metric`. If an existing collection has a different dimension, it
  is recreated only when empty; otherwise startup fails with a clear message
  (change `[storage].milvus_collection` or `docker compose down -v`).

### Step 4: Graph (`backend/graph/`)

- `state.py`: a `TypedDict(total=False)` holding everything nodes share
  (question, queries, papers, passages, analysis, evidence flags,
  `retry_count`, `max_retries`, report).
- `workflow.py`: `build_graph()` registers nodes, adds linear edges, and one
  `add_conditional_edges` from the checker:

```python
def route_after_check(state):
    if state.get("evidence_sufficient"):
        return "report"
    if state.get("retry_count", 0) >= state.get("max_retries", 2):
        return "report"          # hard cap: never loop forever
    return "researcher"
```

Flow: `START → planner → researcher → retriever → analyst → evidence_checker →
(researcher | report) → END`.

### Step 5: Nodes and tools as stubs

Each node is `def x_node(state) -> dict` returning **only the keys it updates**.
Write them as deterministic stubs first (no LLM, no network) so the whole stack
can be built and tested in Docker before any real logic. The checker stub
returns "insufficient" on the first pass so the retry loop gets exercised.
Then replace the stubs one at a time.

### Step 6: API (`backend/app.py`)

- A `lifespan` context manager calls `init_db()` and `init_vector_store()` on startup.
- Compile the graph once at import: `graph = build_graph()`.
- Routes (all under `/api` so one proxy rule covers them):
  - `GET  /api/health`: status + DB info (used by the compose healthcheck)
  - `POST /api/research`: `graph.invoke({...})`, save run to SQLite, return result
  - `GET  /api/runs`: run history
- Wrap `graph.invoke` in try/except → `HTTPException(500)`.
- `CORSMiddleware` with origins from settings (only needed for non-proxied dev).

### Step 7: Backend container

`requirements.txt` sits at the **repo root** so one file serves both the local
venv and the Docker image:
```text
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.9
pydantic-settings>=2.6
langchain-core>=0.3
langgraph>=0.2
langchain-openai>=0.2
pymilvus>=2.5
# No Windows wheels: installs in Docker (Linux) only, skipped in a Windows venv.
milvus-lite>=2.4; sys_platform != "win32"
```

Local venv (IDE support only; the app runs in Docker):
```bash
python -m venv <name>_venv
<name>_venv/Scripts/python -m pip install -r requirements.txt   # Windows
```

`backend/Dockerfile` is built with the **repo root as context**, so it copies
the root `requirements.txt` and then only `backend/`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY config/ /app/config/              # baked-in default; compose mounts over it
ENV CONFIG_PATH=/app/config/config.toml
# CMD ... --workers 1  (Milvus Lite is single-process)
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/Dockerfile.dockerignore`: BuildKit uses `<Dockerfile>.dockerignore`
next to the Dockerfile, so the root context stays small (keep the venv and
frontend out of it):
```gitignore
**/__pycache__/
**/*.pyc
.git/
.env
<name>_venv/
.venv/
venv/
frontend/
data_warehouse/
MD_files/
*.md
```

### Step 8: Frontend

Hand-written minimal Vite + React + TS (no template generator needed):

- `package.json`: deps `react`, `react-dom`; devDeps `vite`, `@vitejs/plugin-react`,
  `typescript`, `@types/react`, `@types/react-dom`; script `"build": "tsc -b && vite build"`.
- `tsconfig.json`: `"moduleResolution": "bundler"`, `"jsx": "react-jsx"`,
  `"strict": true`, `"noEmit": true`, `"types": ["vite/client"]`, `"include": ["src"]`.
- `vite.config.ts`: dev server proxy `"/api" → "http://localhost:8000"`.
- `src/api/client.ts`: typed interface mirroring the backend response model;
  calls **relative** `/api/...` URLs, which works in both dev (Vite proxy) and
  Docker (nginx proxy).
- Run `npm install` once locally to generate `package-lock.json` (needed by `npm ci`).
- `react-router-dom` for pages; nginx's `try_files $uri /index.html` makes deep
  links like `/admin` work.

### Step 8b: Settings UI pattern (Admin + user Settings)

The same pattern serves both pages:

1. **Backend describes, frontend renders.** `form_schema.describe_section()` turns
   a Pydantic model + current values into
   `{key, title, description, fields: [{key, label, type: enum|bool|int|float|str, options, min, max, step, description, value, requires_restart, danger, phase}]}`.
   `FieldInput.tsx` renders any field from that description.
2. **Partial updates.** `PUT` bodies are `{"changes": {"section": {"key": value}}}`;
   `validate_section_changes()` merges and validates, and returns
   `{"section.key": "message"}` errors as a 422 that the UI shows under each field.
3. **Admin = `config.toml`** (`routers/admin.py`):
   - Writes with `tomlkit` (keeps comments and order), **in place** (`open(path, "w")`,
     same inode) and then `force_reload()`.
   - GET returns the `mtime`; the page polls every 4 s and on window focus. If the
     file changed and there are no local edits, it reloads silently; if there are
     unsaved edits, it shows a "changed on disk" banner.
   - Save bar with a count of unsaved changes; confirmation for `requires_restart` / `danger` fields.
4. **Settings = per-user prefs** (`user_settings.py`, `routers/user.py`): a
   `user_settings(user_id, data_json)` SQLite table, auto-saved on change with an
   optimistic update. `UserSettingsProvider` applies `data-theme` / `data-font` /
   `data-density` on `<html>`, and the CSS tokens react to them.

**Design tokens** (`styles.css`): matte palette as CSS variables, light by
default, dark via `prefers-color-scheme` *unless* `data-theme="light"`, and
forced dark via `data-theme="dark"`. Light: bg `#ECEBE7`, surface `#F5F4F1`,
sidebar `#E3E0DA`, border `#D4D0C9`, text `#2A2A28`, accent sage `#6F8572`.
Dark: bg `#1D1E1C`, surface `#252623`, sidebar `#181917`, text `#E4E1DA`,
accent `#8FA592`.

`frontend/nginx.conf`:
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location /api/ {
        proxy_pass http://backend:8000;   # compose service name
        proxy_read_timeout 300s;          # agent runs are slow
    }
    location / { try_files $uri /index.html; }
}
```

`frontend/Dockerfile` (multi-stage):
```dockerfile
FROM node:22-slim AS build        # NOT alpine, see Gotchas
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

`.dockerignore`: `node_modules/`, `dist/`, `.env`.

### Step 9: `docker-compose.yml`

```yaml
services:
  backend:
    build:
      context: .                      # root, so requirements.txt is visible
      dockerfile: backend/Dockerfile
    ports: ["8000:8000"]
    env_file:
      - path: .env
        required: false        # fresh clones work without .env
    environment:
      DATA_DIR: /data
      CONFIG_PATH: /app/config/config.toml
    volumes:
      - research_data:/data     # Milvus Lite + SQLite persist here
      - ./config:/app/config    # DIRECTORY mount, read-write: Admin writes + live editor edits
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on:
      backend:
        condition: service_healthy

volumes:
  research_data:
```

### Step 10: Verify

```bash
docker compose up -d --build
curl localhost:3000/api/health                       # through nginx -> backend
curl -X POST localhost:3000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question":"Graph RAG retrieval accuracy"}'   # expect retry_count=1
docker compose restart backend && curl localhost:8000/api/runs   # run persisted
curl localhost:8000/api/config                       # active hyperparameters
```

**Tuning loop:** edit `config/config.toml` (or use the Admin page). The change is
live on the next request, no restart needed (except fields marked "restart").
Confirm with `curl localhost:8000/api/config`. (Verified: setting
`[evidence].max_retries = 0` makes the graph skip the retry loop.)

**Sync tests** (all passed): PUT from the API → host file updated, comments kept;
in-place host edit → picked up live; editor-style replace-on-save → picked up
live; invalid PUT → 422 per field; invalid hand edit → last good settings kept and
the error shown on the Admin page.

Open http://localhost:3000 for the UI (`/`, `/settings`, `/admin`), and
http://localhost:8000/docs for the FastAPI Swagger UI.

## 4. Data locations

| Mode              | DATA_DIR                    | Files |
|-------------------|-----------------------------|-------|
| Local (no Docker) | `<repo>/data_warehouse/`    | `app.db`, `milvus.db` |
| docker compose    | `/data` → volume `<project>_research_data` | same |

Wipe Docker data: `docker compose down -v`.

## 5. Gotchas hit while scaffolding

1. **Alpine breaks the Vite build.** On `node:22-alpine`, `vite build` fails with
   `Code is nested too deeply ... react-dom/client.js`. Rollup's native parser
   overflows musl's small default thread stack. Use `node:22-slim` for the
   build stage (nginx alpine for serving is fine).
2. **Milvus Lite has no Windows wheels.** It runs on Linux/macOS only.
   Convention for this project: the backend runs and is tested **only inside
   Docker**, never directly on the host.
3. **Git Bash rewrites container paths.** `docker compose exec backend ls /data`
   becomes `C:/Program Files/Git/data`. Prefix with `MSYS_NO_PATHCONV=1`.
4. **`env_file` must be optional** (`required: false`, Compose ≥ 2.24) or a
   fresh clone without `.env` won't start.
5. **Keep every API route under `/api`** so a single nginx `location /api/` and a
   single Vite proxy rule cover them, and the frontend never needs absolute URLs.
6. **Commit `package-lock.json`**: the frontend Dockerfile uses `npm ci`.
7. **Moving `requirements.txt` out of `backend/` breaks a `build: ./backend`
   context.** Switch to `context: .` + `dockerfile: backend/Dockerfile` and add
   `backend/Dockerfile.dockerignore`, or the whole repo (including the venv)
   gets sent to Docker.
8. **Ignore build artifacts:** add `*.tsbuildinfo` to `.gitignore`. `tsc -b`
   writes `frontend/tsconfig.tsbuildinfo`.
9. **Milvus Lite is single-process.** It file-locks `milvus.db`; a second process
   (e.g. `docker compose exec backend python -c "...MilvusClient..."`) fails with
   `DataDirLockedError` while the API is running. Run uvicorn with **one worker**,
   and inspect Milvus through an API endpoint, not a separate script.
10. **Changing the embedding model changes the vector dimension.** An existing
    collection can't change dimension; recreate it (auto if empty) or use a new
    collection name.
11. **Single-file bind mounts go stale.** Mounting `./config.toml:/app/config.toml`
    attaches the file as it was when the container started. Editors that save by
    writing a new file and renaming it leave the container reading the old copy
    until a restart. Mount the **directory** (`./config:/app/config`) instead.
12. **Hot reload only works if nothing caches settings at import.** Read
    `get_settings()` inside functions, and key LLM client caches on the config
    values. CORS origins are read once at startup (restart to change).
13. **Python `write_text` on Windows writes CRLF.** Pass `newline="\n"` when
    writing repo files from scripts (`.gitattributes` normalises them on commit anyway).
14. **Reasoning models reject `temperature`.** Models like `gpt-6-luna` only accept
    the default temperature and take `reasoning_effort` instead (here: none/low/
    medium/high/xhigh; `minimal` is rejected). Reasoning tokens count towards
    `max_tokens`, so give them headroom (8000). Probe a new model's parameters
    with a tiny script before wiring it in.
15. **Pass the node's `config` into nested `.invoke()` calls.** A node declared as
    `def node(state, config: RunnableConfig)` gets the run's callbacks; if it
    calls a chain without passing `config`, those calls still trace in recent
    LangChain via context vars, but passing it explicitly is clearer and keeps
    tags/metadata.

## 6. Reusing for a new agent

1. Copy this layout; rename the nodes in `agents/` and the fields in `graph/state.py`.
2. Keep the stub-first approach: get `docker compose up` + an end-to-end curl
   passing with stubs, then replace stubs one node at a time, re-testing after each.
3. Rename the compose volume and Milvus collection to match the new project.
4. Reuse the **observability pattern**: a LangChain `BaseCallbackHandler`
   (`tracing/recorder.py`) passed via `graph.invoke(..., config={"callbacks": [...]})`
   records every node/chain/LLM span to SQLite, and a Runs page shows the tree.
   No external tracing service is needed. Pair it with the `MIGRATIONS` list +
   `schema_version` table in `db/sqlite.py` for schema changes.
5. Start `MD_files/` with empty `build_plan.md` and `database.md` plus a
   `build_phases/` folder; write the plan before Phase 1 and document every
   table in `database.md` as it's created.
6. Keep the settings pattern: new hyperparameters = new `Field`s in a section
   model; they show up on the Admin page automatically. New user preferences =
   new fields in `user_settings.py`.
