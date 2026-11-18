# Learning Notes

One section per phase: the concept, how we used it, what the experiments
showed, and answers to the phase's "Think about" questions. Answers are based on
what we actually observed in this project (run numbers refer to the Runs page).

---

## Phase 1: UI shell + config sync (no LangGraph)

**Idea:** describe settings once (Pydantic models with metadata) and generate
the form, the validation and the file format from that one description.

- The backend sends `{sections: [{fields: [{type, min, max, description, ...}]}]}`;
  the UI renders whatever it receives, so a new `Field` in `config.py` appears
  on the Admin page with no frontend change. (Proven in Phase 2: `[pricing]`,
  `[tracing]`, `model_kind` and `reasoning_effort` appeared without touching the Admin page.)
- System settings (`config.toml`, Admin) vs user preferences (SQLite, Settings).
- Live sync: mtime-checked hot reload; mount the *directory* because single-file
  bind mounts go stale when an editor saves by replacing the file.

### Think about

**Which settings belong to the system, and which to the user?**
Anything that changes *how the agent works* or what it costs is system config:
models, token limits, retrieval depth, retry caps, prices. Those affect every
user and every result, so they live in one reviewed file (`config.toml`) that's
in git. Anything that only changes *your experience* is a user preference:
theme, report length, whether to review the plan. Two people could pick
differently without affecting each other, so those live per user in the
database. A useful test: "if I change this, does someone else's result change?"
If yes, it's system config.

**Which changes are safe while live, and which need a restart or a data reset?**
- *Safe live:* anything read at call time, such as temperature/effort, top-k,
  number of queries, retry cap. The next run just uses the new value.
- *Restart:* anything read once at startup, such as CORS origins, storage file
  names, the Milvus metric (only applies when a collection is created).
- *Data reset:* anything baked into stored data, especially the embedding model
  and dimension. Old vectors were made by the old model and can't be compared
  with new ones, so the collection must be rebuilt. That's why those fields carry
  a "danger" note and ask for confirmation.

---

## Phase 2: LangChain fundamentals + our own tracing

**Built:** a real planner (`ChatPromptTemplate | ChatOpenAI.with_structured_output(ResearchPlan)`),
a `TraceRecorder` callback handler that records every step into `trace_spans`,
and the Runs page with a trace tree.

### Concepts in one line each
- **Runnable:** the one interface everything shares: `invoke` (one input),
  `batch` (many), `stream` (pieces as they're produced), plus `ainvoke` and friends.
  A prompt template, a model, a parser and a whole compiled graph are all Runnables.
- **LCEL `|`:** `a | b` builds a `RunnableSequence`: the output of `a` becomes the
  input of `b`. The sequence is itself a Runnable (in our trace: `plan_queries`).
- **ChatPromptTemplate:** a Runnable that turns `{"question": ..., "num_queries": 4}`
  into a list of messages (system + human). In the trace it takes about 9 ms and you
  can see the exact rendered prompt.
- **`with_structured_output(Model)`:** returns a new Runnable that asks the API for
  JSON matching the model's schema and parses the reply into a `ResearchPlan` object.
- **RunnableConfig:** the dict passed alongside the input (`callbacks`, `tags`,
  `metadata`, `run_name`, `recursion_limit`). It flows down to every nested call.
- **Callbacks:** objects with hooks such as `on_chain_start/end/error`,
  `on_chat_model_start`, `on_llm_end`, `on_tool_*`. Every Runnable fires them.

### Think about

**A graph node is just a function and a chain is just a Runnable, so what does the graph add?**
A chain is a fixed pipe: data flows one way, step to step, and each step only
sees the previous step's output. The graph adds:
1. **Shared state:** every node reads the whole `ResearchState` and returns only
   the keys it changes; LangGraph merges them. The planner writes `queries` and
   `rationale`; the report node reads `analysis` and `papers` written by others.
2. **Branching on runtime data:** `route_after_check` looks at the state and
   decides the next node.
3. **Cycles:** our trace shows `researcher → retriever → analyst → evidence_checker`
   **twice**. A plain chain can't loop back.
4. Later phases add more: persistence (Phase 7), pausing for a human (8),
   per-node streaming (9).

**When is a chain enough?** When the work is a straight line with no decisions
or loops. The planner on its own *is* a chain: prompt → model → parser. Use a
graph when steps depend on intermediate results, need to loop, or need shared
memory. Use a chain inside a node when the step itself is linear.

**How do callbacks reach nested calls without passing them down by hand?**
We pass the handler once: `graph.invoke(state, config={"callbacks": [recorder]})`.
Then:
1. LangGraph hands each node the run's `RunnableConfig` (that's why
   `planner_node(state, config)` has a `config` parameter).
2. The node passes it on: `chain.invoke(inputs, config)`.
3. Each Runnable, when it starts, creates a *child* callback manager whose parent
   is its own `run_id`. So every event carries `run_id` and `parent_run_id`.
4. Recent LangChain versions also store the current config in a Python
   **context variable**, so nested calls inherit it even if you forget step 2.

Recording `(run_id, parent_run_id)` for each event rebuilds the tree we see:
`research_graph → planner → plan_queries → ChatPromptTemplate / ChatOpenAI /
_check_refusal / RunnableLambda`. This is exactly how hosted tracers work. They
are a callback handler plus a database plus a UI, which is what we built.

One detail: LangGraph also runs internal "plumbing" Runnables (channel writes
and similar) tagged `langsmith:hidden`. Our recorder skips them and re-attaches
their children to the nearest visible parent, so the tree stays readable.

**What does `with_structured_output` actually send to the model?**
Open the LLM span → "Request parameters". You'll see:
```json
"response_format": {"type": "json_schema",
  "json_schema": {"name": "ResearchPlan", "strict": true,
                  "schema": {"properties": {"rationale": {...}, "queries": {...}}, ...}}}
```
So the Pydantic model is converted to a JSON Schema and sent as OpenAI's
`response_format`. With `strict`, the API **constrains generation** so the
reply must match the schema. The reply arrives as a JSON string in the message
content (visible in the span's Response), and the two extra steps after the
model in the trace do the parsing:
- `_check_refusal`: raises if the model refused instead of answering;
- `RunnableLambda`: parses the JSON into a `ResearchPlan` object.

Takeaways: the **field descriptions are part of the prompt** (the model reads the
schema), so write them as instructions. The schema also costs input tokens: the
planner call uses about 260 input tokens, of which the system prompt is only part.
Other options are `method="function_calling"` (sent as a tool) and `json_mode`
(valid JSON, no schema guarantee).

### Experiments (same question, `gpt-6-luna`)

| Run | Setting | Queries | Total time | LLM time | Tokens (in+out) | Reasoning tokens |
|-----|---------|---------|-----------:|---------:|----------------:|-----------------:|
| 7 | effort **low** | 4 | 4.38 s | 2.87 s | 407 | 56 |
| 6 | effort **medium** | 4 | 5.43 s | 3.99 s | 442 | 94 |
| 8 | effort **high** | 4 | 4.40 s | 3.99 s | 580 | 231 |
| 9 | num_queries **2** (medium) | 2 | 2.88 s | 2.42 s | 392 | 64 |
| 10 | num_queries **6** (medium) | 6 | 3.20 s | 2.81 s | 430 | 60 |
| 11 | model `no-such-model` | 1 (fallback) | 0.63 s | 0.35 s | 0 | 0 |

**What we learned:**
- **Reasoning effort controls hidden thinking.** Reasoning tokens went 56 → 94 → 231
  from low to high (about 4×), and they're billed as output tokens even though you
  never see them. The visible answer stayed the same size.
- **Higher effort gave more specific queries.** Low: "multi-hop graph retrieval
  reranking GraphRAG", "adaptive query expansion…". High: "GraphRAG query focused
  subgraph retrieval", "GraphRAG hybrid vector graph reranking": narrower,
  closer to real paper titles. Whether that finds *better papers* is something
  Phase 3 can check.
- **More queries cost almost nothing here.** 2 vs 6 queries changed total tokens by
  only about 40, because the output is tiny compared with the prompt + schema +
  reasoning. Cost is driven by *input size* and *reasoning*, not by how many items you ask for.
- **Latency is noisy.** Single runs vary by a second or more (network, server
  load), e.g. medium took longer than high. Compare averages of several runs before
  drawing conclusions about speed.
- **Failures degrade instead of crashing.** With a bad model name OpenAI returned
  404 (not retried, since it isn't transient). The planner fell back to the raw
  question, the run still completed, and the warning appeared on Home and in the
  trace (the LLM span is marked `error`). The trade-off is that a degraded run looks
  "completed", so warnings must be visible, which they are.

### Things worth remembering
- A node that calls an LLM should accept `config` and pass it to `.invoke()`.
- Name your chains (`.with_config(run_name="plan_queries")`); the names are what you
  see when debugging.
- Reasoning models: no `temperature`; `reasoning_effort` instead; leave
  `max_tokens` headroom because reasoning counts towards it.

---

## Phase 3: Tools and tool calling
_(to fill in)_
