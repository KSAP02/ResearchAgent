"""Research runs: start a run (traced), list runs with analytics, inspect a run's trace."""
import logging
import time

from fastapi import APIRouter, HTTPException

from config import get_settings
from db.sqlite import create_run, finish_run, get_run, get_spans, list_runs, run_stats
from graph.workflow import build_graph
from schemas import ResearchRequest, ResearchResponse
from tracing.recorder import TraceRecorder

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["runs"])

graph = build_graph()


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float | None:
    p = get_settings().pricing
    if not p.input_per_1m and not p.output_per_1m:
        return None
    return round((prompt_tokens * p.input_per_1m + completion_tokens * p.output_per_1m) / 1_000_000, 6)


@router.post("/research", response_model=ResearchResponse)
def research(req: ResearchRequest) -> ResearchResponse:
    s = get_settings()
    snapshot = s.model_dump(mode="json", exclude={"openai_api_key", "cors_origins", "data_dir"})
    run_id = create_run(req.question, snapshot)

    callbacks = []
    recorder = None
    if s.tracing.enabled:
        recorder = TraceRecorder(run_id, s.tracing.max_payload_chars)
        callbacks.append(recorder)

    t0 = time.perf_counter()
    try:
        result = graph.invoke(
            {"question": req.question, "retry_count": 0, "max_retries": s.evidence.max_retries},
            config={
                "callbacks": callbacks,
                "run_name": "research_graph",
                "tags": ["research"],
                "metadata": {"app_run_id": run_id},
            },
        )
    except Exception as exc:
        duration = int((time.perf_counter() - t0) * 1000)
        tokens = recorder.total_tokens if recorder else None
        cost = _estimate_cost(recorder.prompt_tokens, recorder.completion_tokens) if recorder else None
        finish_run(run_id, status="failed", result=None, duration_ms=duration, total_tokens=tokens,
                   est_cost_usd=cost, error=f"{type(exc).__name__}: {exc}")
        log.exception("run %s failed", run_id)
        raise HTTPException(status_code=500, detail=f"Workflow failed (run {run_id}): {exc}") from exc

    duration = int((time.perf_counter() - t0) * 1000)
    tokens = recorder.total_tokens if recorder else None
    cost = _estimate_cost(recorder.prompt_tokens, recorder.completion_tokens) if recorder else None
    finish_run(run_id, status="completed", result=result, duration_ms=duration, total_tokens=tokens,
               est_cost_usd=cost)

    return ResearchResponse(
        run_id=run_id,
        status="completed",
        question=result["question"],
        queries=result.get("queries", []),
        rationale=result.get("rationale", ""),
        papers=result.get("papers", []),
        analysis=result.get("analysis", ""),
        evidence_sufficient=result.get("evidence_sufficient", False),
        retry_count=result.get("retry_count", 0),
        report=result.get("report", ""),
        warnings=result.get("warnings", []),
        duration_ms=duration,
        total_tokens=tokens,
        est_cost_usd=cost,
    )


@router.get("/runs")
def runs(limit: int = 50) -> dict:
    return {"runs": list_runs(limit), "stats": run_stats()}


@router.get("/runs/{run_id}")
def run_detail(run_id: int) -> dict:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/trace")
def run_trace(run_id: int) -> dict:
    if get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "spans": get_spans(run_id)}
