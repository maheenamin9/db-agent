from typing import Any

from app.connectors.base import Connector, TableSchema


class PostgresConnector(Connector):
    def __init__(self, dsn: str):
        self.dsn = dsn

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> TableSchema:
        raise NotImplementedError

    def run_sql(self, sql: str) -> list[dict[str, Any]]:
        raise NotImplementedError
