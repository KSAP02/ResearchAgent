"""Report generator: produce the final cited report. (stub)"""
from graph.state import ResearchState


def report_node(state: ResearchState) -> dict:
    # TODO: LLM report with passage-level citations.
    lines = [f"# Report: {state['question']}", ""]
    if not state.get("evidence_sufficient"):
        lines += ["> Note: evidence was judged insufficient after the maximum number of retries.", ""]
    lines += [state.get("analysis", ""), "", "## Sources"]
    for i, p in enumerate(state.get("papers", []), 1):
        lines.append(f"[{i}] {p.get('title')} - {p.get('url')}")
    return {"report": "\n".join(lines)}
