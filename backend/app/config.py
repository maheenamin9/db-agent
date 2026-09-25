from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
ROOT_ENV_FILE = BACKEND_DIR.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    # Which backend runs SQL_MODEL/DESCRIBE_MODEL. Embeddings always stay on
    # Ollama regardless (Groq has no embeddings API) — this only affects chat.
    llm_provider: Literal["ollama", "groq"] = "ollama"
    groq_api_key: str | None = None

    # Ollama
    ollama_host: str = "http://localhost:11434"
    sql_model: str = "qwen3:30b"
    embed_model: str = "nomic-embed-text"
    describe_model: str = "qwen3:8b"
    retrieval_top_k: int = 8

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "semantics"

    # Local state
    duckdb_path: Path = DATA_DIR / "warehouse.duckdb"
    semantics_path: Path = DATA_DIR / "semantics.yaml"
    table_selection_path: Path = DATA_DIR / "table_selection.json"

    # Agent
    max_repair_retries: int = 2
    row_limit: int = 1000

    # Uploads
    max_upload_mb: int = 50

    # Google Sheets: path to a service account JSON key. The spreadsheet must be
    # shared with that service account's email (Editor access is not needed, Viewer is enough).
    google_service_account_file: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def _require_groq_key_when_selected(self) -> "Settings":
        # Fail at startup, not three minutes into a request: SQL_MODEL/DESCRIBE_MODEL
        # also need to actually be Groq model ids (e.g. llama-3.3-70b-versatile) when
        # this is on — that part can't be validated here, only the key's presence.
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("LLM_PROVIDER=groq requires GROQ_API_KEY to be set")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
