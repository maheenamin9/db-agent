from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    # Ollama
    ollama_host: str = "http://localhost:11434"
    sql_model: str = "qwen2.5-coder:14b"
    embed_model: str = "nomic-embed-text"
    describe_model: str = "qwen3:8b"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
