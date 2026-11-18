import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type RunStats, type RunSummary } from "../api/client";
import StatusPill from "../components/StatusPill";
import { fmtCompact, fmtCost, fmtMs, fmtWhen } from "../format";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

/** Run history + analytics. Every run links to its trace. */
export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [stats, setStats] = useState<RunStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .listRuns()
      .then((r) => {
        setRuns(r.runs);
        setStats(r.stats);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="page wide">
      <div className="page-head">
        <h1>Runs</h1>
        <p>Every research run with its trace, token usage and cost.</p>
      </div>

      {error && <div className="banner error">{error}</div>}

      {stats && (
        <div className="stats">
          <Stat
            label="Runs"
            value={fmtCompact(stats.runs)}
            sub={stats.failed ? `${stats.failed} failed` : "none failed"}
          />
          <Stat label="Avg duration" value={fmtMs(stats.avg_duration_ms)} sub="completed runs" />
          <Stat label="Tokens" value={fmtCompact(stats.total_tokens)} sub="all traced runs" />
          <Stat
            label="Est. cost"
            value={fmtCost(stats.total_cost_usd)}
            sub={stats.total_cost_usd == null ? "set prices in Admin → Pricing" : "all runs"}
          />
        </div>
      )}

      {runs && runs.length === 0 && <div className="card status-text">No runs yet. Ask a question on Home.</div>}

      {runs && runs.length > 0 && (
        <div className="card flush">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Question</th>
                  <th>Status</th>
                  <th>Model</th>
                  <th className="num">Queries</th>
                  <th className="num">Loops</th>
                  <th className="num">Duration</th>
                  <th className="num">Tokens</th>
                  <th className="num">Cost</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr
                    key={r.id}
                    className="clickable"
                    tabIndex={0}
                    onClick={() => navigate(`/runs/${r.id}`)}
                    onKeyDown={(e) => e.key === "Enter" && navigate(`/runs/${r.id}`)}
                  >
                    <td className="muted">{r.id}</td>
                    <td className="question-cell" title={r.question}>
                      {r.question}
                    </td>
                    <td>
                      <StatusPill status={r.status} />
                    </td>
                    <td className="muted nowrap">
                      {r.model ?? "—"}
                      {r.reasoning_effort ? ` · ${r.reasoning_effort}` : ""}
                    </td>
                    <td className="num">{r.num_queries ?? "—"}</td>
                    <td className="num">{r.retry_count ?? "—"}</td>
                    <td className="num">{fmtMs(r.duration_ms)}</td>
                    <td className="num">{fmtCompact(r.total_tokens)}</td>
                    <td className="num">{fmtCost(r.est_cost_usd)}</td>
                    <td className="muted nowrap">{fmtWhen(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
