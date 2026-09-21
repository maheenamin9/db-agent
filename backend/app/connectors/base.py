from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool = True


class TableNotFoundError(LookupError):
    """Raised by get_schema/run_sql when a table does not exist in the source."""


class Connector(ABC):
    """Common interface over every data source (files, sheets, SQL databases).

    Contract (enforced by tests/test_connectors_mock.py::ConnectorContract):
    - list_tables() returns unique table names.
    - get_schema(table) returns the columns in table order, and raises
      TableNotFoundError for an unknown table.
    - run_sql(query) returns a DataFrame, and raises an exception whose message
      describes the problem when the query is invalid (the agent feeds this
      message back to the LLM for repair).
    """

    @abstractmethod
    def list_tables(self) -> list[str]:
        """Names of the tables/sheets/files this source exposes."""

    @abstractmethod
    def get_schema(self, table: str) -> list[ColumnInfo]:
        """Column names and types for one table."""

    @abstractmethod
    def run_sql(self, query: str) -> pd.DataFrame:
        """Run a read-only query against the source."""
