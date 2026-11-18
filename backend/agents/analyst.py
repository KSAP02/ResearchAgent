"""Analyst: compare approaches across retrieved passages. (stub)"""
from graph.state import ResearchState


def analyst_node(state: ResearchState) -> dict:
    # TODO: LLM comparison of methods, strengths and limitations.
    n = len(state.get("passages", []))
    return {"analysis": f"[stub] Compared findings across {n} passages."}
