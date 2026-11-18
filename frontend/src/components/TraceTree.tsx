import { Fragment, useMemo, useState } from "react";
import type { Span } from "../api/client";
import { fmtCompact, fmtMs, pretty } from "../format";

interface Node {
  span: Span;
  children: Node[];
  depth: number;
}

function buildTree(spans: Span[]): Node[] {
  const byId = new Map<string, Node>();
  spans.forEach((s) => byId.set(s.span_id, { span: s, children: [], depth: 0 }));
  const roots: Node[] = [];
  for (const s of spans) {
    const node = byId.get(s.span_id)!;
    const parent = s.parent_span_id ? byId.get(s.parent_span_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  const setDepth = (n: Node, d: number) => {
    n.depth = d;
    n.children.forEach((c) => setDepth(c, d + 1));
  };
  roots.forEach((r) => setDepth(r, 0));
  return roots;
}

const TYPE_LABEL: Record<string, string> = {
  graph: "graph",
  node: "node",
  chain: "chain",
  llm: "LLM",
  tool: "tool",
  retriever: "retriever",
};

/** Messages from an LLM span's inputs, if present. */
function messagesOf(span: Span): { role: string; content: unknown }[] | null {
  const inp = span.inputs as { messages?: unknown } | null;
  return inp && Array.isArray(inp.messages) ? (inp.messages as { role: string; content: unknown }[]) : null;
}

function SpanDetail({ span }: { span: Span }) {
  const messages = span.span_type === "llm" ? messagesOf(span) : null;
  const out = span.outputs as { content?: unknown } | null;
  const params = span.metadata?.invocation_params;
  const { invocation_params: _p, ...restMeta } = span.metadata ?? {};

  return (
    <div className="span-detail">
      {span.error && (
        <div className="banner error">
          <pre>{span.error}</pre>
        </div>
      )}
      {span.span_type === "llm" && (
        <div className="kv">
          <span>Model</span>
          <b>{span.model ?? "—"}</b>
          <span>Input tokens</span>
          <b>{span.prompt_tokens ?? "—"}</b>
          <span>Output tokens</span>
          <b>
            {span.completion_tokens ?? "—"}
            {span.reasoning_tokens ? ` (${span.reasoning_tokens} reasoning)` : ""}
          </b>
        </div>
      )}
      {messages ? (
        <>
          <h4>Prompt sent to the model</h4>
          {messages.map((m, i) => (
            <div key={i} className="msg">
              <div className="msg-role">{m.role}</div>
              <pre>{typeof m.content === "string" ? m.content : pretty(m.content)}</pre>
            </div>
          ))}
          <h4>Response</h4>
          <pre className="code">{out && "content" in out ? pretty(out.content) : pretty(span.outputs)}</pre>
          {params != null && (
            <details>
              <summary>Request parameters (what LangChain sent to the API)</summary>
              <pre className="code">{pretty(params)}</pre>
            </details>
          )}
        </>
      ) : (
        <>
          <h4>Input</h4>
          <pre className="code">{pretty(span.inputs)}</pre>
          <h4>Output</h4>
          <pre className="code">{pretty(span.outputs)}</pre>
        </>
      )}
      {Object.keys(restMeta).length > 0 && (
        <details>
          <summary>Metadata</summary>
          <pre className="code">{pretty(restMeta)}</pre>
        </details>
      )}
    </div>
  );
}

/** Expandable call tree with a timing bar per span (offset + duration on the run's timeline). */
export default function TraceTree({ spans }: { spans: Span[] }) {
  const roots = useMemo(() => buildTree(spans), [spans]);
  // Start with chains collapsed, except those that contain an LLM call (the interesting part).
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const hasLlm = (n: Node): boolean => n.span.span_type === "llm" || n.children.some(hasLlm);
    const ids = new Set<string>();
    const visit = (n: Node) => {
      if (n.span.span_type === "chain" && !hasLlm(n)) ids.add(n.span.span_id);
      n.children.forEach(visit);
    };
    buildTree(spans).forEach(visit);
    return ids;
  });
  const [selected, setSelected] = useState<string | null>(null);

  const t0 = useMemo(() => Math.min(...spans.map((s) => Date.parse(s.started_at))), [spans]);
  const total = useMemo(
    () =>
      Math.max(
        1,
        ...spans.map((s) => Date.parse(s.ended_at ?? s.started_at) - t0),
        ...spans.map((s) => (s.duration_ms ?? 0) + Date.parse(s.started_at) - t0),
      ),
    [spans, t0],
  );

  if (spans.length === 0) return <p className="status-text">No trace recorded for this run.</p>;

  const toggle = (id: string) =>
    setCollapsed((c) => {
      const next = new Set(c);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const rows: JSX.Element[] = [];
  const walk = (n: Node) => {
    const s = n.span;
    const open = !collapsed.has(s.span_id);
    const offset = ((Date.parse(s.started_at) - t0) / total) * 100;
    const width = Math.max(0.6, ((s.duration_ms ?? 0) / total) * 100);
    const isSel = selected === s.span_id;
    rows.push(
      <Fragment key={s.span_id}>
        <div
          className={`trace-row${isSel ? " selected" : ""}${s.status === "error" ? " errored" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => setSelected(isSel ? null : s.span_id)}
          onKeyDown={(e) => e.key === "Enter" && setSelected(isSel ? null : s.span_id)}
        >
          <div className="trace-name" style={{ paddingLeft: n.depth * 16 }}>
            {n.children.length > 0 ? (
              <button
                className="caret"
                aria-label={open ? "Collapse" : "Expand"}
                onClick={(e) => {
                  e.stopPropagation();
                  toggle(s.span_id);
                }}
              >
                {open ? "▾" : "▸"}
              </button>
            ) : (
              <span className="caret-spacer" />
            )}
            <span className={`type type-${s.span_type}`}>{TYPE_LABEL[s.span_type] ?? s.span_type}</span>
            <span className="span-name">{s.name}</span>
            {s.span_type === "llm" && s.prompt_tokens != null && (
              <span className="muted small">
                {fmtCompact((s.prompt_tokens ?? 0) + (s.completion_tokens ?? 0))} tok
              </span>
            )}
            {s.status === "error" && <span className="tag danger">error</span>}
          </div>
          <div className="trace-bar-track" title={`${s.name}: starts at ${fmtMs(Date.parse(s.started_at) - t0)}, takes ${fmtMs(s.duration_ms)}`}>
            <div
              className={`trace-bar${s.span_type === "llm" ? " llm" : ""}`}
              style={{ left: `${offset}%`, width: `${Math.min(width, 100 - offset)}%` }}
            />
          </div>
          <div className="trace-dur">{fmtMs(s.duration_ms)}</div>
        </div>
        {isSel && <SpanDetail span={s} />}
      </Fragment>,
    );
    if (open) n.children.forEach(walk);
  };
  roots.forEach(walk);

  return (
    <div className="trace">
      <div className="trace-row trace-head">
        <div className="trace-name">Step</div>
        <div className="trace-axis">
          <span>0</span>
          <span>{fmtMs(total)}</span>
        </div>
        <div className="trace-dur">Time</div>
      </div>
      {rows}
    </div>
  );
}
