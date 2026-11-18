"""FastAPI entry point for the research assistant service."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.sqlite import init_db, list_runs, save_run
from db.vector_store import get_client, init_vector_store
from graph.workflow import build_graph
from routers import admin, user
from schemas import ResearchRequest, ResearchResponse

graph = build_graph()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    init_vector_store()
    yield


app = FastAPI(title="Agentic Research Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,  # read once at startup
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(user.router)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "sqlite": str(s.sqlite_path),
        "milvus_collections": get_client().list_collections(),
        "llm_model": s.llm.model,
        "embedding_model": s.embeddings.model,
    }


@app.get("/api/config")
def config() -> dict:
    """Active (non-secret) configuration, so tuning changes can be verified."""
    return get_settings().public_summary()


@app.post("/api/research", response_model=ResearchResponse)
def research(req: ResearchRequest) -> ResearchResponse:
    s = get_settings()
    try:
        result = graph.invoke(
            {
                "question": req.question,
                "retry_count": 0,
                "max_retries": s.evidence.max_retries,
            }
        )
    except Exception as exc:  # surface graph failures as a clean 500
        raise HTTPException(status_code=500, detail=f"Workflow failed: {exc}") from exc

    run_id = save_run(
        question=result["question"],
        report=result.get("report", ""),
        retry_count=result.get("retry_count", 0),
        sufficient=result.get("evidence_sufficient", False),
        papers=result.get("papers", []),
    )
    return ResearchResponse(
        run_id=run_id,
        question=result["question"],
        queries=result.get("queries", []),
        papers=result.get("papers", []),
        analysis=result.get("analysis", ""),
        evidence_sufficient=result.get("evidence_sufficient", False),
        retry_count=result.get("retry_count", 0),
        report=result.get("report", ""),
    )


@app.get("/api/runs")
def runs(limit: int = 20) -> list[dict]:
    return list_runs(limit)
