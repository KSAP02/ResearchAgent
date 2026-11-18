"""Application settings loaded from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default local data dir: <repo>/data_warehouse (backend/ is one level below the repo root).
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data_warehouse"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str = ""

    max_research_retries: int = 2
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Storage
    data_dir: Path = _DEFAULT_DATA_DIR
    sqlite_filename: str = "app.db"
    milvus_filename: str = "milvus.db"
    milvus_collection: str = "paper_passages"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / self.sqlite_filename

    @property
    def milvus_uri(self) -> str:
        return str(self.data_dir / self.milvus_filename)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
