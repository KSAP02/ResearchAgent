import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { api, type ResearchResponse } from "../api/client";
import { ArrowUpIcon } from "../components/Icons";
import { fmtCompact, fmtCost, fmtMs } from "../format";

const EXAMPLES = [
  "Recent approaches to improving retrieval accuracy in Graph RAG",
  "How do long-context LLMs compare to RAG on QA benchmarks?",
  "Methods for detecting hallucinations in LLM outputs",
];

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const canSubmit = question.trim().length >= 3 && !loading;

  async function submit() {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.runResearch(question.trim()));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  function autoGrow(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  const showHero = !result && !loading && !error;

  return (
    <div className="page">
      <div className={`home${showHero ? "" : " has-result"}`}>
        {showHero && (
          <>
            <h1>What would you like to research?</h1>
            <p className="sub">Ask a technical question. Answers are built from arXiv papers, with citations.</p>
          </>
        )}

        <div className="ask">
          <textarea
            ref={inputRef}
            rows={1}
            value={question}
            placeholder="Ask a research question..."
            onChange={(e) => {
              setQuestion(e.target.value);
              autoGrow(e.target);
            }}
            onKeyDown={onKeyDown}
            autoFocus
          />
          <button className="send-btn" onClick={() => void submit()} disabled={!canSubmit} aria-label="Run research">
            <ArrowUpIcon />
          </button>
        </div>

        {showHero && (
          <div className="chips">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="chip"
                onClick={() => {
                  setQuestion(ex);
                  inputRef.current?.focus();
                }}
              >
                {ex}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="thinking">
            <span className="dot" /> Planning and researching...
          </div>
        )}

        {error && (
          <div className="result">
            <div className="banner error">{error}</div>
          </div>
        )}

        {result && (
          <div className="result">
            <div className="meta">
              <span>Run #{result.run_id}</span>
              <span>{fmtMs(result.duration_ms)}</span>
              <span>{fmtCompact(result.total_tokens)} tokens</span>
              {result.est_cost_usd != null && <span>{fmtCost(result.est_cost_usd)}</span>}
              <span>Research loops: {result.retry_count}</span>
              <Link to={`/runs/${result.run_id}`} className="link">
                View trace →
              </Link>
            </div>
            {result.warnings.map((w) => (
              <div key={w} className="banner warn">
                {w}
              </div>
            ))}
            <div className="card">
              <h3>Research plan</h3>
              {result.rationale && <p className="rationale">{result.rationale}</p>}
              <ol className="queries">
                {result.queries.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ol>
            </div>
            <div className="card">
              <h3>Report (later nodes are still stubs)</h3>
              <pre className="report">{result.report}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
