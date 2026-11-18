"""FastAPI entry point for the research assistant service."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.sqlite import init_db, schema_version
from db.vector_store import get_client, init_vector_store
from routers import admin, runs, user

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    init_vector_store()
    yield


app = FastAPI(title="Agentic Research Assistant", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,  # read once at startup
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(user.router)
app.include_router(runs.router)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "sqlite": str(s.sqlite_path),
        "schema_version": schema_version(),
        "milvus_collections": get_client().list_collections(),
        "llm_model": s.llm.model,
        "embedding_model": s.embeddings.model,
    }


@app.get("/api/config")
def config() -> dict:
    """Active (non-secret) configuration, so tuning changes can be verified."""
    return get_settings().public_summary()
