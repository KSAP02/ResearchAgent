"""Evidence checker: decide whether claims are supported. (stub)"""
from graph.state import ResearchState


def evidence_checker_node(state: ResearchState) -> dict:
    # TODO: LLM judge over analysis vs. passages.
    # Stub: the first pass is "insufficient" so the retry loop is exercised.
    retry_count = state.get("retry_count", 0)
    sufficient = retry_count >= 1
    return {
        "evidence_sufficient": sufficient,
        "evidence_gaps": [] if sufficient else [f"{state['question']} evaluation"],
        "retry_count": retry_count if sufficient else retry_count + 1,
    }
