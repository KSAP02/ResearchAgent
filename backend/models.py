"""Structured-output schemas the LLM nodes return.

`llm.with_structured_output(Model)` turns the Pydantic model into a JSON schema
and sends it to the API (OpenAI `response_format` = json_schema, strict). The
API constrains generation to that schema and LangChain parses the reply back
into the model. Field descriptions are part of the prompt the model sees, so
write them as instructions.
"""
from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """A plan for searching arXiv for papers that answer the user's question."""

    rationale: str = Field(
        description="One or two sentences: which sub-topics or angles the queries cover and why."
    )
    queries: list[str] = Field(
        description="Focused arXiv search queries, each 3-10 words, using technical terms a paper "
                    "title or abstract would contain. Each query targets a different angle; no near-duplicates."
    )
