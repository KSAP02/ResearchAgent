# Phase 2: LangChain fundamentals + our own tracing ✅

**Date:** 2026-11-18

## Built
- **Planner (real):** `ChatPromptTemplate | get_llm().with_structured_output(ResearchPlan)`
  named `plan_queries`; returns `queries` + `rationale`; cleans/dedupes to
  `[planner].num_queries`; on an LLM error falls back to the raw question and adds a warning.
- **LLM config for reasoning models:** `[llm].model_kind` (reasoning → sends
  `reasoning_effort`; standard → sends `temperature`), `reasoning_effort` ∈
  none/low/medium/high/xhigh, `max_tokens` 8000. The Admin page hides the
  field that doesn't apply (`visible_when`). Model: `gpt-6-luna`.
- **Own tracing:** `backend/tracing/recorder.py` `TraceRecorder(BaseCallbackHandler)`
  records graph/node/chain/LLM/tool/retriever spans (inputs, outputs, errors,
  timing, tokens incl. reasoning, request parameters incl. the structured-output
  JSON schema); skips LangGraph's hidden plumbing runs.
- **Runs lifecycle:** run row created as `running` with a config snapshot →
  graph invoked with the recorder → finished as `completed`/`failed` with
  duration, tokens and estimated cost (`[pricing]`, 0 = not shown).
- **DB:** migration system (`MIGRATIONS` + `schema_version`), migration 2 (run
  metadata + `trace_spans`), WAL + foreign keys.
- **API:** `GET /api/runs` (`{runs, stats}`), `GET /api/runs/{id}`, `GET /api/runs/{id}/trace`.
- **UI:** Runs page (stat tiles + table), RunDetail (plan, trace tree with timing
  bars and per-span prompt/response/params, report, config snapshot), Home shows
  the plan + "View trace".

## Database changes
Migration 2. See `MD_files/database.md` §3.1, §3.5, §7.

## Tests (Docker)
- Migration applied on the existing DB (old runs kept, `status='completed'`).
- Probed `gpt-6-luna`: temperature rejected (only default 1), `minimal` effort
  rejected, structured output OK.
- 6 real runs: effort low/medium/high, num_queries 2/6, bad model name → fallback + warning.
- Trace tree verified (graph → node → chain → LLM; retry loop visible), screenshots.

## Decisions
- No LangSmith: own callback-based tracing stored in SQLite.
- Prices are user-entered in `[pricing]` (no reliable price source for new models).
- The run row is created *before* the graph runs so spans can reference it.

## Issues hit
- `minimal` reasoning effort isn't supported by this model; the API lists the valid values.
- Structured-output request params arrive as a Python class; the recorder
  converts them to the JSON schema actually sent.
