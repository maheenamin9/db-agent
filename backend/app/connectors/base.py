from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool = True


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)


class Connector(ABC):
    """Common interface over every data source (files, sheets, SQL databases)."""

    @abstractmethod
    def list_tables(self) -> list[str]:
        """Names of the tables/sheets/files this source exposes."""

    @abstractmethod
    def get_schema(self, table: str) -> TableSchema:
        """Column names and types for one table."""

    @abstractmethod
    def run_sql(self, sql: str) -> list[dict[str, Any]]:
        """Run a read-only query against the source and return rows as dicts."""
