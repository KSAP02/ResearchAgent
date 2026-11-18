"""LangGraph workflow: plan -> research -> retrieve -> analyze -> check -> (retry | report)."""
from langgraph.graph import END, START, StateGraph

from agents.analyst import analyst_node
from agents.fact_checker import evidence_checker_node
from agents.planner import planner_node
from agents.reporter import report_node
from agents.researcher import researcher_node, retriever_node
from graph.state import ResearchState


def route_after_check(state: ResearchState) -> str:
    """Loop back to research when evidence is weak, unless the retry cap is hit."""
    if state.get("evidence_sufficient"):
        return "report"
    if state.get("retry_count", 0) >= state.get("max_retries", 2):
        return "report"
    return "researcher"


def build_graph():
    g = StateGraph(ResearchState)

    g.add_node("planner", planner_node)
    g.add_node("researcher", researcher_node)
    g.add_node("retriever", retriever_node)
    g.add_node("analyst", analyst_node)
    g.add_node("evidence_checker", evidence_checker_node)
    g.add_node("report", report_node)

    g.add_edge(START, "planner")
    g.add_edge("planner", "researcher")
    g.add_edge("researcher", "retriever")
    g.add_edge("retriever", "analyst")
    g.add_edge("analyst", "evidence_checker")
    g.add_conditional_edges(
        "evidence_checker",
        route_after_check,
        {"researcher": "researcher", "report": "report"},
    )
    g.add_edge("report", END)

    return g.compile()
