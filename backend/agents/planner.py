"""Planner node: break the question into focused arXiv search queries.

LangChain concepts used here:
- ChatPromptTemplate: a Runnable that turns a dict of variables into chat messages.
- `prompt | llm.with_structured_output(ResearchPlan)`: LCEL composes Runnables
  into one RunnableSequence; invoking it runs prompt -> model -> parser.
- with_structured_output: the reply comes back as a validated ResearchPlan object.
- .with_config(run_name=...): names the chain, which is the name shown in our trace.

The node receives the graph's RunnableConfig and passes it on, so our
TraceRecorder callback sees the chain and the LLM call nested under this node.
"""
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from config import get_settings
from graph.state import ResearchState
from llm import get_llm
from models import ResearchPlan

log = logging.getLogger(__name__)

PLANNER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a research librarian planning an arXiv literature search.\n"
            "Break the user's question into exactly {num_queries} focused search queries.\n"
            "Guidelines:\n"
            "- Cover different angles: core methods, recent improvements, evaluation/benchmarks, "
            "limitations or comparisons, as relevant to the question.\n"
            "- Use the technical vocabulary that appears in paper titles and abstracts.\n"
            "- Keep each query short (3-10 words). No boolean operators, quotes or site filters.\n"
            "- Don't repeat the question verbatim unless it is already a good search query.",
        ),
        ("human", "Question: {question}"),
    ]
)


def build_planner_chain():
    """prompt | structured LLM. Built per call so config changes (hot reload) apply."""
    return (PLANNER_PROMPT | get_llm().with_structured_output(ResearchPlan)).with_config(run_name="plan_queries")


def _clean(queries: list[str], limit: int) -> list[str]:
    seen, out = set(), []
    for q in queries:
        q = " ".join(q.split())
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:limit]


def planner_node(state: ResearchState, config: RunnableConfig) -> dict:
    question = state["question"]
    n = get_settings().planner.num_queries
    try:
        plan: ResearchPlan = build_planner_chain().invoke({"question": question, "num_queries": n}, config)
        queries = _clean(plan.queries, n) or [question]
        return {"queries": queries, "rationale": plan.rationale}
    except Exception as exc:  # LLM/API failure -> degrade gracefully, keep the run going
        log.warning("planner failed, falling back to the raw question: %s", exc)
        return {
            "queries": [question],
            "rationale": "",
            "warnings": [f"Planner failed ({type(exc).__name__}); used the question as the only query."],
        }
