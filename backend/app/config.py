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

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "semantics"

    # Local state
    duckdb_path: Path = DATA_DIR / "warehouse.duckdb"
    semantics_path: Path = DATA_DIR / "semantics.yaml"
    relationships_path: Path = DATA_DIR / "relationships.json"

    # Agent
    max_repair_retries: int = 2
    row_limit: int = 1000

    # Seed databases (used by the Postgres / MySQL connectors)
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/demo"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "mysql"
    mysql_database: str = "demo"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
