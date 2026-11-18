import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type RunDetail as Run, type Span } from "../api/client";
import StatusPill from "../components/StatusPill";
import TraceTree from "../components/TraceTree";
import { fmtCompact, fmtCost, fmtMs, parseDbTime, pretty } from "../format";

export default function RunDetail() {
  const { id } = useParams();
  const runId = Number(id);
  const [run, setRun] = useState<Run | null>(null);
  const [spans, setSpans] = useState<Span[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(runId)) return;
    Promise.all([api.getRun(runId), api.getTrace(runId)])
      .then(([r, t]) => {
        setRun(r);
        setSpans(t.spans);
      })
      .catch((e: Error) => setError(e.message));
  }, [runId]);

  if (error) {
    return (
      <div className="page wide">
        <Link to="/runs" className="back">
          ← Runs
        </Link>
        <div className="banner error">{error}</div>
      </div>
    );
  }
  if (!run || !spans) return <div className="page wide status-text">Loading...</div>;

  const llm = run.config?.llm;
  const llmSpans = spans.filter((s) => s.span_type === "llm");
  const reasoning = llmSpans.reduce((a, s) => a + (s.reasoning_tokens ?? 0), 0);

  return (
    <div className="page wide">
      <Link to="/runs" className="back">
        ← Runs
      </Link>
      <div className="page-head">
        <h1 className="run-title">{run.question}</h1>
        <div className="meta">
          <StatusPill status={run.status} />
          <span>Run #{run.id}</span>
          <span>{parseDbTime(run.created_at).toLocaleString()}</span>
          {llm && (
            <span>
              {String(llm.model)} ·{" "}
              {llm.model_kind === "reasoning" ? `reasoning ${String(llm.reasoning_effort)}` : `temp ${String(llm.temperature)}`}
            </span>
          )}
          <span>{fmtMs(run.duration_ms)}</span>
          <span>
            {fmtCompact(run.total_tokens)} tokens{reasoning ? ` (${fmtCompact(reasoning)} reasoning)` : ""}
          </span>
          <span>{fmtCost(run.est_cost_usd)}</span>
          <span>{llmSpans.length} LLM call{llmSpans.length === 1 ? "" : "s"}</span>
          <span>{run.retry_count ?? 0} research loop{run.retry_count === 1 ? "" : "s"}</span>
        </div>
      </div>

      {run.error && (
        <div className="banner error">
          <pre>{run.error}</pre>
        </div>
      )}

      {run.queries && run.queries.length > 0 && (
        <section className="card">
          <div className="card-head">
            <h2>Plan</h2>
            {run.rationale && <p>{run.rationale}</p>}
          </div>
          <ol className="queries">
            {run.queries.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ol>
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Trace</h2>
          <p>Every graph node, chain and LLM call, recorded by our callback handler. Click a step for its inputs and outputs.</p>
        </div>
        <TraceTree spans={spans} />
      </section>

      {run.report && (
        <section className="card">
          <div className="card-head">
            <h2>Report</h2>
          </div>
          <pre className="report">{run.report}</pre>
        </section>
      )}

      {run.config && (
        <section className="card">
          <details>
            <summary>Config snapshot used for this run</summary>
            <pre className="code">{pretty(run.config)}</pre>
          </details>
        </section>
      )}
    </div>
  );
}
