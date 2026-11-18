# CLAUDE.md: Agentic Research Assistant

LangGraph research assistant: takes a technical question, plans queries, searches
arXiv, retrieves passages, analyzes them, checks the evidence (looping back to
research if it's weak), and produces a cited report. Brief: `MD_files/agentic_research_assistant_project_brief.md`.
Reusable scaffold recipe: `project_scaffold.md`.
**Build plan (phases, goals, outcomes): `MD_files/build_plan.md`.** Follow it
phase by phase.
**Database design: `MD_files/database.md`**: every table/collection, schema, live vs planned.
**Phase records: `MD_files/build_phases/phase_NN_<name>.md`**, one per finished phase.

## Working rules

- **Update this file after every feature or meaningful progress**: tick the
  progress checklist, add a dated entry to the changelog, and update the
  architecture/API sections if they changed.
- **Update `MD_files/database.md` on every schema change** (new table, column,
  collection field, or store): schema, status (live/planned) and its change log.
- **Every phase gets a "Workflow walkthrough" in `MD_files/learning_notes.md`**
  (written by Claude, not the user): outcome in one sentence, the graph picture
  with what changed, what the new/changed node looks like in code, what it
  triggers step by step (with real run examples), and a "pieces at work" table.
  Diagrams are SVG images in `MD_files/images/` (VS Code doesn't render Mermaid).
- **When a phase is finished**, write `MD_files/build_phases/phase_NN_<name>.md`
  (built, DB changes, tests, decisions, issues) and mark it ✅ in `build_plan.md`.
- **Run and test only in Docker** (`docker compose up -d --build`). Milvus Lite
  doesn't run on Windows, so the backend is never run directly on the host.
- Test after every change: health check, an end-to-end `POST /api/research`, and
  a restart to confirm data persists.
- In Git Bash, prefix `docker compose exec` commands that use container paths
  with `MSYS_NO_PATHCONV=1`.
- Never commit `.env` or the data files in `data_warehouse/`.
- **Every tunable goes in `settings/config.toml`**, never hard-coded in nodes.
  Add new settings as Pydantic `Field`s (with description, `ge`/`le`, and a
  `json_schema_extra` label/step) in `backend/config.py` so they appear on
  the Admin page automatically. The file is hot-reloaded on change, so no
  restart is needed except for fields marked `requires_restart`.
- **Nodes must call `get_settings()` / `get_llm()` at run time**, never cache
  settings at import; otherwise hot reload won't reach them.
- **LLM nodes take `(state, config: RunnableConfig)` and pass `config` into
  every chain `.invoke(...)`** so the TraceRecorder sees nested calls. Name
  chains with `.with_config(run_name=...)`. Return structured output via
  Pydantic models in `backend/models.py`; degrade gracefully on LLM errors
  (append to `warnings`).
- **Model is a reasoning model** (`gpt-6-luna`): never send `temperature`;
  `reasoning_effort` ∈ none/low/medium/high/xhigh. `llm.py` handles this via
  `[llm].model_kind`.
- **Schema changes = a new entry in `MIGRATIONS`** (never edit an applied one)
  + update `MD_files/database.md`.
- **System vs user settings:** system hyperparameters → `settings/config.toml`
  (Admin page). Per-user preferences → `backend/user_settings.py` models,
  stored in SQLite (Settings page). Mark preferences that a later phase wires
  up with `json_schema_extra={"phase": N}`.
- **New pages:** add a route in `frontend/src/App.tsx` and an entry in
  `MAIN_NAV`/`BOTTOM_NAV` in `frontend/src/components/Sidebar.tsx`. Use the
  CSS tokens in `styles.css` (matte palette, light/dark); no new colour literals.
- Secrets live in `.env` (OpenAI; optional Semantic Scholar). Never read or
  print `.env` values.
- **No LangSmith** (user decision): observability = our own LangChain
  callback handler → SQLite `trace_spans` → Runs page. Keep
  `LANGSMITH_TRACING=false`.
- **Purpose: the user is learning LangGraph/LangChain by building this.** Use
  the framework's own abstractions (not hand-rolled equivalents) and explain
  the concepts as we go. This is for understanding, not a showcase.
- Milvus Lite is single-process: one uvicorn worker, and never open
  `milvus.db` from a second process while the API runs.
- **Dependencies live in the root `requirements.txt`**, which is shared by the
  local venv (`ra_venv/`, git-ignored) and the backend Docker image. Install
  local deps with `ra_venv/Scripts/python -m pip install -r requirements.txt`.
  The local venv is for editor/IDE support only. `milvus-lite` is skipped on
  Windows via an environment marker.
- Git remote: https://github.com/KSAP02/ResearchAgent (branch `main`).

## Stack

| Layer      | Choice |
|------------|--------|
| Agents     | LangChain + LangGraph (`StateGraph`) |
| Backend    | FastAPI (`backend/app.py`), Python 3.12 container |
| Vector DB  | Milvus Lite: `/data/milvus.db` in volume `research_data` |
| SQL DB     | SQLite: `/data/app.db` in volume `research_data` |
| Frontend   | React + TypeScript + Vite, served by nginx (proxies `/api` to the backend) |
| LLM        | OpenAI `gpt-6-luna` (reasoning model: `reasoning_effort`, no custom temperature) via `langchain-openai` `ChatOpenAI` |
| Embeddings | OpenAI `text-embedding-3-small`, 1536-dim (`OpenAIEmbeddings`) |
| Tuning     | `settings/config.toml` (all hyperparameters, two-way synced with the Admin page); secrets in `.env` |

## Run

```bash
docker compose up -d --build
curl localhost:3000/api/health
curl -X POST localhost:3000/api/research -H "Content-Type: application/json" -d '{"question":"Graph RAG retrieval accuracy"}'
```

- UI: http://localhost:3000 (Home `/`, Settings `/settings`, Admin `/admin`)
- API docs: http://localhost:8000/docs
- Wipe data: `docker compose down -v`

## Architecture

Graph: `START → planner → researcher → retriever → analyst → evidence_checker → (researcher | report) → END`.
The checker loops back to the researcher until the evidence is sufficient or
`retry_count >= max_retries` (`[evidence].max_retries`, default 2).

| Path | Role |
|------|------|
| `requirements.txt` (root) | Python deps for the venv and the backend image |
| `backend/Dockerfile` | Built with the repo root as context; excludes come from `backend/Dockerfile.dockerignore` |
| `backend/app.py` | FastAPI routes; initializes the DBs at startup |
| `settings/config.toml` | Hyperparameters. The `settings/` dir is bind-mounted read-write (directory, not file, so editor saves stay visible) |
| `backend/config.py` | Settings: env/.env > config.toml > defaults; nested section models with UI metadata; mtime-based hot reload (`get_settings`, `force_reload`, `last_load_error`) |
| `backend/form_schema.py` | Turns Pydantic models into form descriptions for the UI; validates partial changes |
| `backend/routers/admin.py` | `GET/PUT /api/admin/config`: read/write config.toml via `tomlkit` (keeps comments), in-place write |
| `backend/user_settings.py`, `backend/routers/user.py` | Per-user preferences models + `GET/PUT /api/user/settings` |
| `backend/llm.py` | `get_llm()` / `get_embeddings()` factories built from config |
| `backend/graph/state.py` | `ResearchState` TypedDict |
| `backend/graph/workflow.py` | `build_graph()`, `route_after_check()` |
| `backend/agents/*.py` | One file per node |
| `backend/tools/*.py` | arXiv search, PDF extraction, vector retrieval |
| `backend/db/sqlite.py` | `MIGRATIONS` + `schema_version`; tables `research_runs`, `trace_spans`, `user_settings` (see `MD_files/database.md`) |
| `backend/tracing/recorder.py` | `TraceRecorder` callback handler: every graph/node/chain/LLM/tool span → `trace_spans` (tokens incl. reasoning, invocation params, errors) |
| `backend/routers/runs.py` | Creates the run row, invokes the graph with `config={"callbacks": [TraceRecorder]}`, finishes the run (status, tokens, cost); runs + trace endpoints |
| `backend/models.py` | Structured-output schemas (`ResearchPlan`) |
| `backend/agents/planner.py` | Real planner: `ChatPromptTemplate \| get_llm().with_structured_output(ResearchPlan)`, fallback to the raw question |
| `backend/db/vector_store.py` | Milvus client; collection `paper_passages` (dim from `[embeddings].dimension`, 1536) |
| `frontend/src/api/client.ts` | Typed client for `/api/*` (`api.*`, `ApiError` with field errors) |
| `frontend/src/styles.css` | Design tokens (matte light/dark), layout, components |
| `frontend/src/components/` | `Sidebar` (nav config), `FieldInput` (renders a backend-described field), `Icons` |
| `frontend/src/context/UserSettings.tsx` | Loads user prefs, applies theme/font/density to `<html>`, optimistic updates |
| `frontend/src/pages/` | `Home` (question bar, plan, View trace link), `Runs` (stat tiles + table), `RunDetail` (plan, trace tree, report, config snapshot), `Admin` (config editor; `visible_when` fields), `Settings` (auto-save) |
| `frontend/src/components/TraceTree.tsx` | Span tree + timing bars; click a span for prompt/response/params |

API: `GET /api/health` (incl. schema_version), `GET /api/config`, `GET/PUT /api/admin/config`, `GET/PUT /api/user/settings`, `POST /api/research` (traced), `GET /api/runs` (`{runs, stats}`), `GET /api/runs/{id}`, `GET /api/runs/{id}/trace`.

## Progress (phases from `MD_files/build_plan.md`)

- [x] Phase 0: Scaffold (FastAPI, stub graph, Milvus Lite + SQLite, React/TS, compose, `config.toml`)
- [x] Phase 1: UI shell (matte, sidebar, Home bar), Admin page with two-way `config.toml` sync, user Settings
- [x] Phase 2: LangChain fundamentals + own tracing via callbacks, Runs page (planner)
- [ ] Phase 3: Tools & tool calling (arXiv researcher agent)
- [ ] Phase 4: State reducers + `Send` fan-out
- [ ] Phase 5: Retrieval stack (loaders, splitters, embeddings, langchain-milvus)
- [ ] Phase 6: Evidence loop, `Command`, subgraphs
- [ ] Phase 7: Checkpointers, time travel, Runs page
- [ ] Phase 8: Human-in-the-loop (`interrupt`)
- [ ] Phase 9: Streaming to the UI
- [ ] Phase 10: Cited report + LangSmith evaluation
- [ ] Phase 11: Functional API / prebuilt comparison + README

## Changelog

- **2026-11-18**: Scaffold built. All nodes and tools are stubs (the checker
  forces one retry on purpose). Tested in Docker: health check OK, the
  research run did 1 retry, and the run stayed in SQLite after a backend
  restart. Switched the frontend build image to `node:22-slim` because the
  Alpine build fails.
- **2026-11-18**: First commit pushed to `origin/main`. Moved `requirements.txt`
  to the repo root (shared with the local venv `ra_venv/`). The backend image
  now builds with the root as its context (`dockerfile: backend/Dockerfile`)
  and excludes files via `backend/Dockerfile.dockerignore`. `milvus-lite` is
  marked Linux/macOS-only. Retested in Docker: health check OK, research run
  OK, and data persisted across the rebuild.
- **2026-11-18**: Added `MD_files/build_plan.md`: idea, goals, outcomes, target
  architecture, and Phases 0–8 (Phase 0 done). Next: Phase 1 (LLM foundation +
  planner); the LLM provider still needs to be chosen.
- **2026-11-18**: Chose OpenAI for the LLM and embeddings (`langchain-openai`).
  Added `config.toml` for all hyperparameters (pydantic-settings TOML source;
  env `SECTION__KEY` overrides), `backend/llm.py` factories, and `GET
  /api/config`. The Milvus collection is now 1536-dim (the empty 384-dim one was
  auto-recreated). `config.toml` is bind-mounted, so tuning only needs a
  restart (tested: `evidence.max_retries=0` skips the loop). Found that Milvus
  Lite is single-process (file lock), so uvicorn must run with one worker.
- **2026-11-18**: Rewrote `MD_files/build_plan.md` as a learning-driven plan
  (Phases 0–11). Each phase has concepts, what to build, experiments and
  questions to think through. Phase 1 = UI shell + Admin page (two-way sync with
  `config.toml`; will move to `config/` with a directory mount) + user Settings.
- **2026-11-18**: **Phase 1 done.** Frontend: matte light/dark design tokens,
  collapsible sidebar (react-router; Workspace: Home / Configure: Settings,
  Admin), Home with an auto-growing question bar + example chips + result
  view, Admin page generated from the backend config schema (dirty tracking,
  sticky save bar, inline validation errors, confirmation for restart/danger
  fields, external-change banner), Settings page with auto-save that applies
  theme/font/density live. Backend: moved config to `config/config.toml` with a
  read-write **directory** mount; mtime-based hot reload (an invalid file keeps
  the last good settings and shows the error); `tomlkit` in-place writes keep
  comments; `form_schema.py`; `user_settings` table. `.env` now lists the
  OpenAI/LangSmith/Semantic Scholar variables. Tested in Docker: UI → file
  write, in-place and replace-on-save file edits picked up live, 422 field
  errors, broken file handled, user settings persisted across restart, all
  routes 200, research run OK, screenshots checked in both themes. Next:
  Phase 2 (LangChain fundamentals + LangSmith).
- **2026-11-18**: Added `MD_files/database.md` (live: `research_runs`,
  `user_settings`, Milvus `paper_passages`; planned: `papers`, `run_papers`,
  `research_runs` columns, Milvus Phase 5 fields, `checkpoints.db`) and
  `MD_files/build_phases/` with records for Phases 0 and 1. The scaffold recipe
  now includes the `MD_files/` docs layout.
- **2026-11-18**: Decided not to use LangSmith. Phase 2 now builds our own
  tracing (LangChain callbacks → `trace_spans` → Runs page with a trace tree,
  tokens and cost) alongside the real planner; Phase 10 uses our own eval harness.
  Updated `build_plan.md` and `database.md`. OpenAI key confirmed visible to the backend.
- **2026-11-18**: **Phase 2 done.** Real planner (`ChatPromptTemplate |
  ChatOpenAI.with_structured_output(ResearchPlan)`, fallback on error) on
  `gpt-6-luna`. Admin: `[llm].model_kind` (reasoning → `reasoning_effort`;
  standard → `temperature`, hidden otherwise via `visible_when`), max_tokens
  8000, new `[pricing]` and `[tracing]` sections. Own tracing: `TraceRecorder`
  callback handler → `trace_spans`; migration system (`schema_version`,
  migration 2). Runs page (stat tiles, table) + RunDetail (trace tree with
  timing bars, prompt/response/params per span, config snapshot). Experiments
  recorded in `learning_notes.md`. Tested in Docker: migration on the existing DB,
  6 real runs, planner fallback with a bad model name, screenshots.
- **2026-11-18**: Hyperparameter file moved by the user to `settings/config.toml`
  (was `config/config.toml`). Updated `CONFIG_PATH` default, Dockerfile (`COPY settings/`),
  compose mount `./settings:/app/settings`, and all docs. Added data-flow diagrams to
  `learning_notes.md`.
- **2026-11-18**: Populated `README.md` (overview, status, features, screenshots,
  stack, quick start, configuration, how it works with diagrams, structure, roadmap,
  docs index, data sources). Screenshots in `MD_files/images/screenshots/`.
- **2026-11-18**: Added a Workflow walkthrough for Phases 1 and 2 to `learning_notes.md`
  (node code, step-by-step trigger flow, pieces at work) + `images/node_lifecycle.svg`;
  the pipeline image now draws the conditional edge as a diamond. Walkthroughs are now a
  per-phase rule.
