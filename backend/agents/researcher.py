"""Researcher + retriever nodes. (stubs)"""
from graph.state import ResearchState
from tools.arxiv_search import search_arxiv
from tools.vector_retriever import retrieve_passages


def researcher_node(state: ResearchState) -> dict:
    # On a retry, the evidence checker's gaps become extra search queries.
    queries = state.get("evidence_gaps") or state.get("queries", [])
    papers = list(state.get("papers", []))
    for q in queries:
        papers.extend(search_arxiv(q))
    return {"papers": papers}


def retriever_node(state: ResearchState) -> dict:
    return {"passages": retrieve_passages(state["question"], state.get("papers", []))}
