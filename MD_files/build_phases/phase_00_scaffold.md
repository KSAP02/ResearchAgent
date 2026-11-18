# Phase 0: Scaffold ✅

**Date:** 2026-11-18

## Built
- FastAPI service (`backend/app.py`) with `/api/health`, `/api/research`, `/api/runs`, `/api/config`.
- LangGraph `StateGraph` with stub nodes: planner → researcher → retriever →
  analyst → evidence_checker → (retry | report). The stub checker forces one retry.
- Milvus Lite + SQLite in the Docker volume `research_data`.
- React + TypeScript frontend behind nginx (`/api` proxied).
- `config.toml` for hyperparameters; root `requirements.txt` shared with `ra_venv/`.
- OpenAI chosen for the LLM + embeddings (`backend/llm.py` factories).

## Concepts touched
`StateGraph`, `TypedDict` state, nodes returning partial updates,
`add_conditional_edges`, a bounded cycle.

## Tests
Health check, end-to-end run (1 retry), persistence across restart, config
tuning (`evidence.max_retries=0` skips the loop).

## Issues hit
Alpine breaks the Vite build; Milvus Lite has no Windows build and allows only
one process; Git Bash rewrites container paths. See `project_scaffold.md` → Gotchas.
