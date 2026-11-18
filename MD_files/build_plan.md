# Build Plan: Agentic Research & Analysis Assistant

> **Purpose:** learn LangGraph and LangChain properly by building a real,
> working research assistant. Every phase adds a working feature **and** teaches
> a new part of the framework, so you finish with both a complete app and a
> mental model of the framework from several angles.
>
> Source brief: `agentic_research_assistant_project_brief.md`. Progress is tracked
> in `CLAUDE.md`; per-phase learnings go in `MD_files/learning_notes.md`.

---

## 1. Idea

A research assistant that answers a technical question **from papers, not from
model memory**. It plans search queries, finds arXiv papers, reads them, compares
approaches, checks that each claim is backed by a retrieved passage (looping back
to research when it isn't), and writes a cited report.

The app gives us something real to build. What we're really after is what each
phase teaches.

## 2. Learning goals

By the end you should be able to explain, and choose between:

| Area | You'll understand |
|------|-------------------|
| LangChain core | Runnables, prompts, chaining calls with `\|` (LCEL), messages, structured output, invoke/batch/stream |
| Tools | `@tool`, tool schemas, `bind_tools`, tool calls, `ToolNode`, the ReAct loop |
| Retrieval | Documents, loaders, splitters, embeddings, vector stores, retrievers, search strategies |
| LangGraph state | State schemas, reducers, messages state, input/output/private state |
| LangGraph control flow | Edges, conditional edges, cycles, `Command`, `Send` (map-reduce), subgraphs, recursion limits |
| Persistence | Checkpointers, threads, state history, replay/fork (time travel) |
| Human-in-the-loop | `interrupt()`, `Command(resume=...)`, approve/edit flows |
| Streaming | `stream_mode` values (`updates`, `values`, `messages`, `custom`), custom progress events |
| Observability & eval | Callbacks and the run tree (our own tracing + analytics UI), an evaluation harness, comparing config variants |
| Alternative paradigms | Graph API vs Functional API vs prebuilt agents: when to pick which |

## 3. Final outcome (definition of done)

- [ ] Minimal matte UI: sidebar navigation, Home with a question bar, Admin and Settings pages.
- [ ] Admin page and `config.toml` stay in sync both ways (edit either one, the other updates).
- [ ] Settings page stores per-user preferences that affect the UI and the research run.
- [ ] Planner produces focused queries (structured output).
- [ ] Researcher is a real **tool-calling** agent over the arXiv API, with queries run in parallel.
- [ ] PDFs are loaded, split, embedded (OpenAI) and stored in Milvus Lite; passages are retrieved.
- [ ] Analyst + evidence checker run a bounded loop that triggers real research retries.
- [ ] Runs are checkpointed: history, replay from any step, resume after failure.
- [ ] Optional human approval of the research plan before searching.
- [ ] Live progress and report text stream into the UI.
- [ ] Final report with numbered citations that resolve to real passages; weak evidence flagged.
- [ ] Every run has a trace in the UI (node and LLM spans, tokens, latency, cost); at least one config-vs-config evaluation done.
- [ ] Everything runs with `docker compose up`, documented in the README.

## 4. Principles

- **One concept cluster per phase.** Build with the framework's own abstraction
  first; hand-roll only when we want to see what the abstraction hides.
- **Always working.** Each phase ends with the full stack running in Docker:
  health check → end-to-end run → restart → persistence check.
- **Every tunable goes in `config.toml`**, never hard-coded, and is editable from the Admin page.
- **Experiment, then write it down.** Each phase includes config experiments and
  questions to think through; record the findings in `learning_notes.md`.
- **Honest output:** unsupported claims are flagged, never presented as fact.
- After each phase: update `CLAUDE.md`, commit, push.

### Phase template

Each phase below lists:
- **Concepts:** what you'll learn.
- **Build:** what gets added to the app.
- **Experiment:** `config.toml` knobs to turn and what to watch for.
- **Think about:** questions that show the framework from another angle.
- **Done when:** the acceptance check.

---

## 5. Phases

### Phase 0: Scaffold ✅
FastAPI + LangGraph skeleton with stub nodes, Milvus Lite + SQLite in a Docker
volume, React/TS frontend behind nginx, `config.toml` + `/api/config`, retry loop
exercised by a stub.

---

### Phase 1: UI shell, Admin config sync, user Settings ✅ (done)
**Concepts:** none from LangGraph. This phase builds the panel you'll use to
experiment in every later phase. (It does show configuration as data: a schema
generating its own UI.)

**Build: frontend**
- **Design:** minimalistic and matte, with low-saturation colours, no gradients or
  heavy shadows, generous spacing, one accent colour, light and dark themes via CSS
  variables. Starting palette (we'll adjust it after seeing it):

  | Token | Light | Dark |
  |-------|-------|------|
  | background | `#ECEAE6` | `#1D1E1C` |
  | surface | `#F5F4F1` | `#262724` |
  | sidebar | `#E2DFD9` | `#181917` |
  | border | `#D3CFC8` | `#34352F` |
  | text | `#2A2A28` | `#E4E1DA` |
  | muted text | `#6E6A63` | `#9A968E` |
  | accent (sage) | `#6F8572` | `#8FA592` |

- **Layout:** collapsible left **sidebar** + content area, with routing (`react-router`).
  Sidebar items: **Home**, **Settings**, **Admin**. New pages later (Runs,
  Papers, Evaluations) slot in as sidebar entries.
- **Home:** a centred question bar (submit with Enter), result area below (for now
  the stub report; later phases add progress, citations, plan review).
- **Admin page** (system hyperparameters = `config.toml`):
  - The form is **generated from the backend's config schema** (sections →
    cards, fields → inputs by type, with descriptions and min/max), so any
    keys added in later phases appear automatically.
  - Save sends only changed fields; validation errors are shown inline.
  - Fields that need care (`embeddings.dimension`, `storage.*`) are marked
    "requires reset/restart" and ask for confirmation.
  - Shows when the file was last changed and refreshes on external edits.
- **Settings page** (per-user preferences, stored in SQLite, *not* `config.toml`):
  theme (light/dark/system), density/font size, default report length
  (brief/standard/detailed), show agent trace detail, "review plan before
  research" (wired up in Phase 8), citation style. Preferences not yet used by
  the backend are labelled with the phase that wires them up.

**Build: backend (only the config/settings API)**
- Move config to **`settings/config.toml`** and bind-mount the **directory**
  (`./settings:/app/settings`, read-write). A single-file mount points to the file
  that existed at container start and goes stale when an editor saves by
  replacing the file.
- `GET /api/admin/config` → `{schema, values, mtime}` (JSON Schema from the
  Pydantic models, with descriptions).
- `PUT /api/admin/config` → validate with Pydantic → write with **`tomlkit`**
  (keeps comments and ordering) → hot-reload settings.
- **Hot reload:** check the file's mtime on each request; reload when it
  changes. Clear the cached settings and LLM/embedding clients. Nodes read
  `get_settings()` at call time, never at import.
- File → UI: the Admin page polls `mtime` every few seconds (or on window focus)
  and refreshes.
- `GET/PUT /api/user/settings`: a `user_settings` table in SQLite (one default user for now).

**Experiment:** edit `settings/config.toml` in your editor and watch the Admin page
update; change `evidence.max_retries` in the UI and watch the file change and the
next run's behaviour change.

**Think about:** which settings belong to the *system* (admin) and which to the
*user*? Which changes are safe while live, and which need a restart or a data reset?

**Done when:** both sync directions work without a container restart, user
settings persist across restarts, and the UI looks right in both themes.

---

### Phase 2: LangChain fundamentals + our own tracing (Planner) ✅ (done)
**Concepts:** the **Runnable** interface (`invoke`, `batch`, `stream`, `ainvoke`),
`ChatPromptTemplate`, messages (`SystemMessage`/`HumanMessage`/`AIMessage`),
chaining with `prompt | llm` (LCEL), `with_structured_output(PydanticModel)` (and
what it does under the hood), **`RunnableConfig`** (`callbacks`, `tags`,
`metadata`, `run_name`), **callbacks** (`BaseCallbackHandler`: chain/LLM/tool
start, end and error events), the **run tree** (`run_id` / `parent_run_id`),
and `usage_metadata` (token counts). This is the same mechanism hosted
tracing tools like LangSmith are built on; here we build it ourselves.

**Build:**
- Real **planner**: `ChatPromptTemplate | get_llm().with_structured_output(ResearchPlan)`
  → `{queries, rationale}`; on an LLM error, fall back to the raw question.
- **`TraceRecorder` callback handler** passed via `graph.invoke(..., config={"callbacks": [...]})`.
  It records every graph node, chain and LLM call as a *span*: name, type,
  parent, start/end, duration, inputs/outputs (truncated), model, prompt and
  completion tokens, and errors. Spans are stored in a SQLite `trace_spans` table.
- Each run stores a **config snapshot** + planner queries + status, duration,
  total tokens and estimated cost (prices per model in `config.toml` `[pricing]`).
- First real **schema migration** (`schema_version` table + ordered steps).
- API: `GET /api/runs` (list + stats), `GET /api/runs/{id}`, `GET /api/runs/{id}/trace`.
- UI: a new **Runs** page in the sidebar: run history with an analytics strip
  (runs, average duration, tokens, estimated cost) and a run detail view with
  the **trace tree** (expand a node → its LLM calls → prompt, response, tokens,
  latency). Home shows the planner's queries and a "View trace" link.

**Experiment:** `[llm].temperature` 0 vs 0.9, `[planner].num_queries`, a
different `[llm].model`. Compare queries, tokens, latency and cost side by side
on the Runs page; each run's config snapshot shows exactly what was used.

**Think about:** a graph node is just a function, and a chain is just a Runnable.
What does the graph add on top of a chain? How do callbacks reach nested calls
without you passing them down by hand? What does `with_structured_output` send
to the model to get JSON back?

**Done when:** the planner returns LLM queries and every run has a browsable
trace with token counts in the UI.

---

### Phase 3: Tools and tool calling (Researcher as an agent)
**Concepts:** `@tool` and tool schemas (docstring and type hints become what the
LLM sees), `bind_tools`, `AIMessage.tool_calls`, `ToolMessage`, **`MessagesState`
and the `add_messages` reducer**, the prebuilt **`ToolNode`** and
**`tools_condition`**, the ReAct loop, `recursion_limit`.

**Build:**
- `search_arxiv` as a real LangChain `@tool` (arXiv API, rate-limited, de-duplicated).
- Researcher = a small **agent loop**: an LLM with tools bound decides which searches
  to run (and can refine them) until it has enough candidates.
- Papers saved to SQLite (`papers` table) and shown on Home.

**Experiment:** `[research].max_results_per_query`, tool docstring wording, an
iteration cap on the agent. Watch in the traces how the LLM chooses tool calls.

**Think about:** in Phase 0 we called `search_arxiv()` directly. What changes
when the *LLM* decides to call it? What's gained and what's lost in control,
cost and predictability? Compare with `create_react_agent` (prebuilt).

**Done when:** real arXiv papers come back and the traces show tool calls chosen by the model.

---

### Phase 4: State design, reducers, parallel fan-out
**Concepts:** state schemas in depth (`TypedDict` vs Pydantic), **reducers**
(`Annotated[list, operator.add]`, custom de-duplicating reducers), **input/output
schemas** and private state, the **`Send` API** for map-reduce, parallel
execution steps ("supersteps").

**Build:**
- Planner fans out with `Send("research_query", {...})`, one per query, all run in parallel.
- A `papers` reducer merges results and drops duplicates by arXiv ID (this
  replaces the manual merge from Phase 0).
- The graph exposes a clean input schema (`question`) and output schema (`report`, ...).

**Experiment:** num_queries 2 vs 6: time per run and duplicate rate.

**Think about:** what happens to state when two parallel nodes write the same key
with and without a reducer? Why does LangGraph make you declare how to merge?

**Done when:** queries run in parallel (visible in the trace) and papers are de-duplicated by the reducer.

---

### Phase 5: The LangChain retrieval stack (ingest + retrieve)
**Concepts:** `Document`, **document loaders** (`PyMuPDFLoader`), **text
splitters** (`RecursiveCharacterTextSplitter`), **embeddings**
(`OpenAIEmbeddings`), the **VectorStore** abstraction (`langchain-milvus` on Milvus
Lite), **retrievers** (`as_retriever`, `search_type` similarity / MMR /
score threshold, metadata filters).

**Build:**
- Ingest node: download PDFs (size/time caps) → load → split (with page metadata)
  → embed → store in Milvus; abstract fallback for failed/malformed PDFs; skip
  papers already stored.
- Retrieve node: retriever over Milvus, filtered to this run's papers.
- The `langchain-milvus` vector store takes over creating the Milvus collection
  (replacing the hand-made one from Phase 0).

**Experiment:** `chunk_size`/`chunk_overlap`, `top_k`, `similarity` vs `mmr`,
`score_threshold`. Compare the passages you get back for the same question.

**Think about:** what does the VectorStore/Retriever abstraction buy you? Swap
Milvus for an in-memory store in one line. What would a retriever that isn't a
vector store look like (keyword search, arXiv abstracts)?

**Done when:** passages with paper + page appear for a real question.

---

### Phase 6: Control flow: the evidence loop and subgraphs
**Concepts:** conditional edges vs **`Command(goto=..., update=...)`** (routing
from inside a node), **cycles** with explicit caps vs `recursion_limit`,
**subgraphs** (a compiled graph used as a node; shared vs separate state keys),
structured LLM judges.

**Build:**
- Analyst: structured `Analysis {approaches, claims[{text, passage_ids}], comparison}`;
  passage IDs checked against what was actually retrieved.
- Evidence checker: `EvidenceAssessment {verdicts, gaps, sufficient}`; gaps become new queries.
- The research → ingest → retrieve section becomes a **subgraph**; the parent graph loops it.
- Real retry loop capped by `[evidence].max_retries` and `min_supported_ratio`.

**Experiment:** `min_supported_ratio` 0.5 vs 0.9, `max_retries` 0/1/3. How many
loops happen, and how does report quality change?

**Think about:** conditional edge vs `Command`: where should routing logic live?
Why use a subgraph instead of more nodes? What's the risk of an LLM deciding
when to stop?

**Done when:** a vague question triggers a genuine retry and the verdicts are visible.

---

### Phase 7: Persistence: checkpointers and time travel
**Concepts:** **checkpointers** (`SqliteSaver` from `langgraph-checkpoint-sqlite`),
**threads** (`thread_id`), `get_state`, `get_state_history`, **replay and
fork** from a past checkpoint, `update_state`, resuming after failure, the
long-term **Store** compared with checkpoints.

**Build:**
- Graph compiled with a SQLite checkpointer (in the data volume); each run = a thread.
- Extend the **Runs** page (built in Phase 2) with checkpoint state per step and "re-run from this step".
- Resume a run that failed mid-way (for example, an LLM error during analysis).

**Experiment:** fork a past run at the evidence checker with a different
`min_supported_ratio`, then compare the two branches.

**Think about:** checkpoints vs our own `research_runs` table: what's the
difference between *workflow state* and *application data*? What does
persistence make possible that a stateless graph can't do?

**Done when:** you can open any past run, inspect each step, and replay/fork it.

---

### Phase 8: Human-in-the-loop
**Concepts:** **`interrupt()`**, **`Command(resume=...)`**, why interrupts need a
checkpointer, approve/edit/reject patterns, static breakpoints (`interrupt_before`).

**Build:**
- With "review plan before research" on (Settings page), the graph pauses after
  the planner. The UI shows the queries to approve, edit or reject, then resumes.

**Experiment:** edit the plan by hand vs accept the LLM's, then compare the reports.

**Think about:** where in an agent is human review worth the friction? How does
"pause and resume" work with no process waiting in memory?

**Done when:** the plan review works from the UI and resumes the same thread.

---

### Phase 9: Streaming
**Concepts:** `stream_mode` = `updates` / `values` / `messages` / `custom`,
`get_stream_writer()` for custom progress events, streaming from inside
subgraphs (`subgraphs=True`), async (`astream`), Server-Sent Events.

**Build:**
- `POST /api/research` starts a run in the background → `run_id`; `GET
  /api/runs/{id}/stream` sends events over SSE (nginx buffering off).
- Home: live progress timeline (nodes light up, retry loops visible) and the
  report text streaming in token by token.

**Experiment:** compare the same run under each `stream_mode`. What does each one show?

**Think about:** what's the difference between streaming *state*, *updates*, and
*tokens*, and which does each UI element need?

**Done when:** progress and report text stream live in the UI.

---

### Phase 10: Report, citations and evaluation
**Concepts:** structured output for long documents, citation-checking functions
(plain code inside the graph), **our own evaluation harness** (a dataset of
questions, code checks + LLM-as-judge, results in SQLite and shown in the UI),
comparing experiments.

**Build:**
- Report node: `Report {summary, sections, comparison_table, limitations, references}`
  with `[n]` citations that resolve to passages; "weak evidence" section; length
  follows the user's Settings preference.
- Home renders markdown with clickable citations (passage + paper link).
- A small evaluation dataset (5–10 questions) and evaluators: citation validity,
  groundedness, coverage. Run it against two `config.toml` variants.

**Experiment:** model A vs model B, or top_k 4 vs 12, scored on the dataset.

**Think about:** how do you know a change made the agent *better*? What can be
checked with code and what needs a judge?

**Done when:** every `[n]` resolves, and you have one evaluation comparison recorded.

---

### Phase 11: Same problem, other paradigms (capstone)
**Concepts:** the LangGraph **Functional API** (`@entrypoint`, `@task`), the
prebuilt `create_react_agent`, a plain LCEL chain: the same problem built three
ways.

**Build:**
- Re-implement a slice (plan → search → summarise) with the Functional API and
  with a prebuilt agent; compare code size, control, debuggability and traces.
- README: architecture diagram, setup, how state/routing/retries work, and
  "when to use which" notes based on what you found.

**Think about:** for your next agent project, which paradigm would you start with, and why?

**Done when:** you have a written comparison in `learning_notes.md` and the README is complete.

---

## 6. Concept → phase map

| Concept | Phase |
|---------|-------|
| Runnables, prompts, LCEL, structured output, callbacks / own tracing | 2 |
| Tools, `bind_tools`, `ToolNode`, ReAct, `add_messages` | 3 |
| Reducers, input/output schemas, `Send` | 4 |
| Loaders, splitters, embeddings, vector stores, retrievers | 5 |
| `Command`, cycles, subgraphs | 6 |
| Checkpointers, threads, time travel | 7 |
| `interrupt`, `Command(resume)` | 8 |
| Streaming modes, custom events | 9 |
| Evaluation harness (our own) | 10 |
| Functional API, prebuilt agents | 11 |

## 7. How `config.toml` grows

| Phase | Sections added/used |
|-------|---------------------|
| 1 | Admin page for all existing sections |
| 2 | `[llm]`, `[planner]`, `[pricing]`, `[tracing]` (payload truncation) |
| 3 | `[research]` (+ agent iteration cap) |
| 4 | `[planner].num_queries` drives the fan-out |
| 5 | `[ingest]`, `[embeddings]`, `[retrieval]` (+ `search_type`) |
| 6 | `[evidence]`, `[analysis]` |
| 7–9 | `[runtime]` (checkpointing, streaming options) |
| 10 | `[report]`, `[eval]` |

## 8. Per-phase checklist

1. Build only that phase's scope.
2. Add deps to the root `requirements.txt` / `frontend/package.json`.
3. Expose new tunables in `settings/config.toml` (they show up on the Admin page automatically).
4. `docker compose up -d --build` → health → end-to-end run → restart/persistence.
5. Run the phase's experiment; write findings, answers and a **Workflow walkthrough**
   (outcome, graph picture, node code, step-by-step trigger flow with real run examples,
   pieces-at-work table, SVG diagrams) in `MD_files/learning_notes.md`.
6. Update `CLAUDE.md` (progress + changelog) and `project_scaffold.md` if the scaffold changed.
7. Commit and push to `origin/main`.

## 9. Data sources & costs

| Source | What we use it for | Access | Cost |
|--------|--------------------|--------|------|
| **arXiv API** (`export.arxiv.org/api/query`) | Search: titles, authors, abstracts, dates, PDF links | Official API, Atom XML, no key | Free |
| **arXiv PDFs** (`arxiv.org/pdf/<id>`) | Full text for passages | Direct download of individual PDFs | Free |
| OpenAI | LLM calls + embeddings | API key | **Paid** (per token) |
| ~~LangSmith~~ | Not used (decided 2026-11-18): tracing and evaluation are built in-house on LangChain callbacks | — | — |
| *Optional later:* Semantic Scholar, OpenAlex | Citation counts, related papers, wider coverage | Official APIs (free) | Free |

- **No scraping.** Everything goes through official APIs or direct PDF links.
- **Freshness:** searches run *on demand* for each question, so results always
  include the latest arXiv listings. arXiv announces new papers once per weekday
  (~20:00 US Eastern). There's no daily crawl; a scheduled "watch a topic" job
  could be added later as a feature.
- **arXiv terms:** about 1 request every 3 s, a single connection, and only
  individual PDF downloads (bulk mirroring would need their S3 bulk-data
  service). Our caps in `config.toml` keep us well inside this.
- **Licences:** each paper has its own licence. Storing text for personal
  research and quoting passages with citations is fine; don't republish full texts.

## 10. Decisions & risks

| Item | Decision / mitigation |
|------|-----------------------|
| LLM + embeddings | OpenAI (`gpt-4.1-mini`, `text-embedding-3-small` 1536-dim), tunable |
| Config live sync | Mount the `config/` directory (not a single file); `tomlkit` writes in place; mtime-based hot reload |
| Unsafe live changes | Embedding dimension/storage fields need confirmation; dimension change → new collection |
| Admin page has no auth | Fine for local single-user use; add auth before any shared deployment |
| Milvus Lite is single-process | One uvicorn worker; all Milvus access via the API. Move to Milvus standalone if we ever need more processes |
| arXiv rate limits | ~1 req / 3 s, small result counts, cache papers in SQLite |
| Embedding/LLM cost | Caps on papers/PDFs/chunks per run in `config.toml`; skip re-embedding |
| Observability | **No LangSmith.** Own tracing via callbacks → SQLite `trace_spans` → Runs page (Phase 2); own eval harness (Phase 10) |
