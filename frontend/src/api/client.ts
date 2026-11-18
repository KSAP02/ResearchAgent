export interface ResearchResponse {
  run_id: number;
  question: string;
  queries: string[];
  papers: { title: string; url: string }[];
  analysis: string;
  evidence_sufficient: boolean;
  retry_count: number;
  report: string;
}

// Relative path: served via the Vite dev proxy locally, and the nginx proxy in Docker.
export async function runResearch(question: string): Promise<ResearchResponse> {
  const res = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`Request failed (${res.status}): ${await res.text()}`);
  return res.json();
}
