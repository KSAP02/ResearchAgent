"""Application settings.

Precedence (highest first): env vars / .env  >  settings/config.toml  >  defaults below.
- Secrets and deployment values (OPENAI_API_KEY, DATA_DIR, CORS_ORIGINS) come from env.
- Hyperparameters live in settings/config.toml (path from CONFIG_PATH).
- Nested values can be overridden from env with SECTION__KEY, e.g. LLM__MODEL=gpt-4.1.

Hot reload: get_settings() re-reads the file whenever its mtime changes, so edits
made in an editor or via the Admin page apply without a restart. Always call
get_settings() at use time; never keep a module-level copy.

Field metadata (description, ge/le, json_schema_extra) drives the Admin page form.
Extras understood by the UI: label, step, requires_restart, danger, phase.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", _REPO_ROOT / "settings" / "config.toml"))

RESTART = {"requires_restart": True}


class LLMConfig(BaseModel):
    """Chat model used by every LLM node."""

    provider: Literal["openai"] = Field("openai", description="LLM provider.")
    model: str = Field("gpt-6-luna", description="OpenAI chat model name, e.g. gpt-6-luna.")
    model_kind: Literal["reasoning", "standard"] = Field(
        "reasoning",
        description="Reasoning models take a reasoning effort and reject custom temperature; "
                    "standard models take a temperature.",
        json_schema_extra={"label": "Model type"})
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh"] = Field(
        "medium", description="How much the model thinks before answering. Higher = slower, more tokens.",
        json_schema_extra={"visible_when": {"model_kind": "reasoning"}})
    temperature: float = Field(0.2, ge=0, le=2, description="Higher = more varied output (standard models only).",
                               json_schema_extra={"step": 0.1, "visible_when": {"model_kind": "standard"}})
    max_tokens: int = Field(8000, ge=64, le=64000,
                            description="Max output tokens per LLM call. Reasoning tokens count towards this limit.")
    timeout_s: int = Field(60, ge=5, le=600, description="Per-request timeout.", json_schema_extra={"label": "Timeout (s)"})
    max_retries: int = Field(2, ge=0, le=10, description="API-level retries on transient errors.", json_schema_extra={"label": "API retries"})


class EmbeddingsConfig(BaseModel):
    """Embedding model for passages in Milvus."""

    provider: Literal["openai"] = Field("openai", description="Embeddings provider.")
    model: str = Field("text-embedding-3-small", description="Embedding model name.",
                       json_schema_extra={"danger": "Changing the model makes stored vectors incompatible."})
    dimension: int = Field(1536, ge=64, le=4096, description="Vector size; must match the model and the Milvus collection.",
                           json_schema_extra={**RESTART, "danger": "Needs a new/empty Milvus collection and a backend restart."})
    batch_size: int = Field(64, ge=1, le=2048, description="Texts embedded per API call.")


class PlannerConfig(BaseModel):
    """Breaks the question into search queries."""

    num_queries: int = Field(4, ge=1, le=10, description="Focused search queries generated per question.")


class ResearchConfig(BaseModel):
    """arXiv search behaviour."""

    max_results_per_query: int = Field(5, ge=1, le=50, description="arXiv results fetched per query.")
    max_papers_per_run: int = Field(12, ge=1, le=100, description="Cap on unique papers kept per run.")
    sort_by: Literal["relevance", "lastUpdatedDate", "submittedDate"] = Field(
        "relevance", description="arXiv result ordering.")
    request_delay_s: float = Field(3.0, ge=0, le=30, description="Delay between arXiv requests (arXiv asks for ~3 s).",
                                   json_schema_extra={"step": 0.5, "label": "Request delay (s)"})


class IngestConfig(BaseModel):
    """PDF download, extraction and chunking."""

    max_pdfs_per_run: int = Field(8, ge=0, le=50, description="Full PDFs downloaded per run (others use the abstract).")
    max_pdf_mb: int = Field(20, ge=1, le=200, description="Skip PDFs larger than this.", json_schema_extra={"label": "Max PDF size (MB)"})
    download_timeout_s: int = Field(30, ge=5, le=300, description="PDF download timeout.", json_schema_extra={"label": "Download timeout (s)"})
    chunk_size: int = Field(1000, ge=100, le=8000, description="Characters per passage chunk.")
    chunk_overlap: int = Field(150, ge=0, le=2000, description="Overlap between consecutive chunks.")


class RetrievalConfig(BaseModel):
    """Vector search over stored passages."""

    top_k: int = Field(8, ge=1, le=50, description="Passages retrieved per query.", json_schema_extra={"label": "Top K"})
    metric: Literal["COSINE", "IP", "L2"] = Field("COSINE", description="Vector similarity metric.",
                                                  json_schema_extra={**RESTART, "danger": "Applies to newly created collections only."})
    score_threshold: float = Field(0.0, ge=0, le=1, description="Drop passages scoring below this.",
                                   json_schema_extra={"step": 0.05})


class EvidenceConfig(BaseModel):
    """Evidence checker and the research retry loop."""

    max_retries: int = Field(2, ge=0, le=10, description="Research loops before the report is forced (graph cycle cap).", json_schema_extra={"label": "Max research loops"})
    min_supported_ratio: float = Field(0.7, ge=0, le=1, description="Share of claims that must be supported to pass.",
                                       json_schema_extra={"step": 0.05})


class ReportConfig(BaseModel):
    """Final report generation."""

    max_citations: int = Field(15, ge=1, le=100, description="Maximum citations in the final report.")


class PricingConfig(BaseModel):
    """Token prices for cost estimates on the Runs page (USD per 1M tokens, for the model above)."""

    input_per_1m: float = Field(0.0, ge=0, le=1000, description="Price per 1M input tokens. 0 = cost not shown.",
                                json_schema_extra={"label": "Input $ / 1M tokens", "step": 0.01})
    output_per_1m: float = Field(0.0, ge=0, le=1000,
                                 description="Price per 1M output tokens (reasoning tokens are billed as output).",
                                 json_schema_extra={"label": "Output $ / 1M tokens", "step": 0.01})


class TracingConfig(BaseModel):
    """Our own run tracing (LangChain callbacks -> trace_spans table -> Runs page)."""

    enabled: bool = Field(True, description="Record a trace span for every node, chain and LLM call.")
    max_payload_chars: int = Field(6000, ge=200, le=200000,
                                   description="Truncate stored span inputs/outputs to this many characters.",
                                   json_schema_extra={"label": "Max payload chars"})


class StorageConfig(BaseModel):
    """Database file and collection names (inside DATA_DIR)."""

    sqlite_filename: str = Field("app.db", description="SQLite file name.", json_schema_extra=RESTART)
    milvus_filename: str = Field("milvus.db", description="Milvus Lite file name.", json_schema_extra=RESTART)
    milvus_collection: str = Field("paper_passages", description="Milvus collection for passages.",
                                   json_schema_extra=RESTART)


SECTION_MODELS: dict[str, type[BaseModel]] = {
    "llm": LLMConfig,
    "embeddings": EmbeddingsConfig,
    "planner": PlannerConfig,
    "research": ResearchConfig,
    "ingest": IngestConfig,
    "retrieval": RetrievalConfig,
    "evidence": EvidenceConfig,
    "report": ReportConfig,
    "pricing": PricingConfig,
    "tracing": TracingConfig,
    "storage": StorageConfig,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        toml_file=CONFIG_PATH,
        extra="ignore",
    )

    # --- secrets / deployment (env) ---
    openai_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    data_dir: Path = _REPO_ROOT / "data_warehouse"

    # --- hyperparameters (config.toml) ---
    llm: LLMConfig = LLMConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    planner: PlannerConfig = PlannerConfig()
    research: ResearchConfig = ResearchConfig()
    ingest: IngestConfig = IngestConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    evidence: EvidenceConfig = EvidenceConfig()
    report: ReportConfig = ReportConfig()
    pricing: PricingConfig = PricingConfig()
    tracing: TracingConfig = TracingConfig()
    storage: StorageConfig = StorageConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / self.storage.sqlite_filename

    @property
    def milvus_uri(self) -> str:
        return str(self.data_dir / self.storage.milvus_filename)

    def public_summary(self) -> dict:
        """Non-secret view of the active config (for /api/config)."""
        data = self.model_dump(exclude={"openai_api_key"}, mode="json")
        data["openai_api_key_set"] = bool(self.openai_api_key)
        data["config_path"] = str(CONFIG_PATH)
        data["config_file_found"] = CONFIG_PATH.exists()
        return data


# --- hot-reloading cache -------------------------------------------------------
_lock = threading.Lock()
_state: dict = {"settings": None, "mtime": None, "error": None}


def config_mtime() -> int | None:
    try:
        return CONFIG_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        return None


def get_settings() -> Settings:
    """Return current settings, reloading if config.toml changed on disk.

    If the file is edited into an invalid state, the last good settings are kept
    and the error is exposed via last_load_error() (shown on the Admin page).
    """
    mtime = config_mtime()
    with _lock:
        if _state["settings"] is not None and mtime == _state["mtime"]:
            return _state["settings"]
        try:
            s = Settings()
            s.data_dir.mkdir(parents=True, exist_ok=True)
            if _state["settings"] is not None:
                log.info("Reloaded config from %s", CONFIG_PATH)
            _state.update(settings=s, mtime=mtime, error=None)
        except Exception as exc:  # invalid TOML or values
            if _state["settings"] is None:
                raise
            log.error("Config reload failed, keeping previous settings: %s", exc)
            _state.update(mtime=mtime, error=str(exc))
        return _state["settings"]


def force_reload() -> Settings:
    with _lock:
        _state["mtime"] = object()  # never equal -> reload on next call
    return get_settings()


def last_load_error() -> str | None:
    get_settings()
    return _state["error"]
