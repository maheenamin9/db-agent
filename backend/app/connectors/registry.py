import uuid
from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel

from app.connectors.mysql import MySQLConfig, MySQLConnector
from app.connectors.postgres import PostgresConfig, PostgresConnector
from app.connectors.sql import SqlConnector

# source type -> (config model, connector factory)
CONNECTOR_TYPES: dict[str, tuple[type[BaseModel], type[SqlConnector]]] = {
    "postgres": (PostgresConfig, PostgresConnector),
    "mysql": (MySQLConfig, MySQLConnector),
}


@dataclass
class Source:
    id: str
    type: str
    name: str
    connector: SqlConnector  # holds the credentials; never serialized


class SourceRegistry:
    """Connected sources, kept in memory. Credentials are never written to disk,
    so sources must be reconnected after a restart (imported tables stay in DuckDB)."""

    def __init__(self):
        self._sources: dict[str, Source] = {}

    def add(self, type: str, name: str, connector: SqlConnector) -> Source:
        source = Source(id=uuid.uuid4().hex[:8], type=type, name=name, connector=connector)
        self._sources[source.id] = source
        return source

    def get(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def list(self) -> list[Source]:
        return list(self._sources.values())


@lru_cache
def get_registry() -> SourceRegistry:
    return SourceRegistry()
