"""Request/response models for the HTTP API."""
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Technical research question")


class ResearchResponse(BaseModel):
    run_id: int
    question: str
    queries: list[str]
    papers: list[dict]
    analysis: str
    evidence_sufficient: bool
    retry_count: int
    report: str
