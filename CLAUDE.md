# CLAUDE.md: Agentic Research Assistant

LangGraph research assistant: takes a technical question, plans queries, searches
arXiv, retrieves passages, analyzes them, checks the evidence (looping back to
research if it's weak), and produces a cited report. Brief: `MD_files/agentic_research_assistant_project_brief.md`.
Reusable scaffold recipe: `project_scaffold.md`.

## Working rules

- **Update this file after every feature or meaningful progress**: tick the
  progress checklist, add a dated entry to the changelog, and update the
  architecture/API sections if they changed.
- **Run and test only in Docker** (`docker compose up -d --build`). Milvus Lite
  doesn't run on Windows, so the backend is never run directly on the host.
- Test after every change: health check, an end-to-end `POST /api/research`, and
  a restart to confirm data persists.
- In Git Bash, prefix `docker compose exec` commands that use container paths
  with `MSYS_NO_PATHCONV=1`.
- Never commit `.env` or the data files in `data_warehouse/`.

## Stack

| Layer      | Choice |
|------------|--------|
| Agents     | LangChain + LangGraph (`StateGraph`) |
| Backend    | FastAPI (`backend/app.py`), Python 3.12 container |
| Vector DB  | Milvus Lite: `/data/milvus.db` in volume `research_data` |
| SQL DB     | SQLite: `/data/app.db` in volume `research_data` |
| Frontend   | React + TypeScript + Vite, served by nginx (proxies `/api` to the backend) |
| LLM        | TBD (`.env.example` currently assumes OpenAI `gpt-4.1-mini`) |

## Run

```bash
docker compose up -d --build
curl localhost:3000/api/health
curl -X POST localhost:3000/api/research -H "Content-Type: application/json" -d '{"question":"Graph RAG retrieval accuracy"}'
```

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs
- Wipe data: `docker compose down -v`

## Architecture

Graph: `START → planner → researcher → retriever → analyst → evidence_checker → (researcher | report) → END`.
The checker loops back to the researcher until the evidence is sufficient or
`retry_count >= max_retries` (`MAX_RESEARCH_RETRIES`, default 2).

| Path | Role |
|------|------|
| `backend/app.py` | FastAPI routes; initializes the DBs at startup |
| `backend/config.py` | Settings from env vars; `DATA_DIR` (`/data` in Docker) |
| `backend/graph/state.py` | `ResearchState` TypedDict |
| `backend/graph/workflow.py` | `build_graph()`, `route_after_check()` |
| `backend/agents/*.py` | One file per node |
| `backend/tools/*.py` | arXiv search, PDF extraction, vector retrieval |
| `backend/db/sqlite.py` | `research_runs` table: `save_run`, `list_runs` |
| `backend/db/vector_store.py` | Milvus client; collection `paper_passages` (dim 384) |
| `frontend/src/api/client.ts` | Typed client for `/api/*` |

API: `GET /api/health`, `POST /api/research`, `GET /api/runs`.

## Progress

- [x] Scaffold: folder layout, FastAPI, LangGraph skeleton, Docker + compose, volume
- [x] Milvus Lite + SQLite initialized in the Docker volume
- [x] Retry loop working end to end (with stub nodes)
- [ ] Choose LLM provider/model; add LLM client
- [ ] Planner: LLM query decomposition (structured output)
- [ ] Researcher: real arXiv API search
- [ ] PDF extraction (PyMuPDF) with error handling
- [ ] Embeddings + Milvus insert/search in the retriever
- [ ] Analyst: LLM comparison over passages
- [ ] Evidence checker: LLM judge that produces gaps
- [ ] Report generator: passage-level citations
- [ ] Frontend: show the run progress, sources and run history
- [ ] README with architecture diagram, screenshot and example report

## Changelog

- **2026-11-18**: Scaffold built. All nodes and tools are stubs (the checker
  forces one retry on purpose). Tested in Docker: health check OK, the
  research run did 1 retry, and the run stayed in SQLite after a backend
  restart. Switched the frontend build image to `node:22-slim` because the
  Alpine build fails.
