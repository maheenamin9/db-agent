import pandas as pd

from app.connectors.base import ColumnInfo
from app.connectors.sql import SqlConnector
from app.duckdb_helper import quote_ident
from tests.mock_connector import MockConnector


class FakeSqlConnector(SqlConnector):
    """A SqlConnector backed by the in-memory mock data, so no database is needed."""

    def __init__(self, tables: dict[str, pd.DataFrame] | None = None):
        self._mock = MockConnector(tables)

    def quote(self, identifier: str) -> str:
        return quote_ident(identifier)

    def list_tables(self) -> list[str]:
        return self._mock.list_tables()

    def get_schema(self, table: str) -> list[ColumnInfo]:
        return self._mock.get_schema(table)

    def run_sql(self, query: str) -> pd.DataFrame:
        return self._mock.run_sql(query)


class DownConnector(FakeSqlConnector):
    """Simulates an unreachable database."""

    errors = (ConnectionError,)

    def list_tables(self) -> list[str]:
        raise ConnectionError("connection refused")
