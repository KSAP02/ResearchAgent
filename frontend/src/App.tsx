import { useState } from "react";
import { runResearch, type ResearchResponse } from "./api/client";

export default function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await runResearch(question));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: "2rem auto", padding: "0 1rem", fontFamily: "system-ui" }}>
      <h1>Agentic Research Assistant</h1>
      <form onSubmit={submit} style={{ display: "flex", gap: 8 }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a technical research question..."
          style={{ flex: 1, padding: 8 }}
        />
        <button disabled={loading || question.trim().length < 3}>
          {loading ? "Researching..." : "Run"}
        </button>
      </form>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {result && (
        <section>
          <p>
            Run #{result.run_id} · Retries: {result.retry_count} · Evidence sufficient:{" "}
            {String(result.evidence_sufficient)}
          </p>
          <pre style={{ whiteSpace: "pre-wrap" }}>{result.report}</pre>
        </section>
      )}
    </main>
  );
}
