"""Shared state passed between LangGraph nodes."""
from typing import TypedDict


class ResearchState(TypedDict, total=False):
    question: str             # original user question
    queries: list[str]        # focused search queries from the planner
    papers: list[dict]        # paper metadata (title, url, arxiv_id, ...)
    passages: list[dict]      # retrieved passages with source references
    analysis: str             # analyst's comparison of findings
    evidence_sufficient: bool
    evidence_gaps: list[str]  # what the checker says is missing
    retry_count: int          # research loops completed so far
    max_retries: int          # hard cap to prevent endless cycles
    report: str               # final cited report
