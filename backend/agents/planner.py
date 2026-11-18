"""Planner: break the question into focused search queries. (stub)"""
from graph.state import ResearchState


def planner_node(state: ResearchState) -> dict:
    # TODO: replace with an LLM call using structured output.
    q = state["question"]
    return {"queries": [q, f"{q} survey", f"{q} benchmark"]}
