from typing import Any

from app.connectors.base import Connector, TableSchema


class MySQLConnector(Connector):
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> TableSchema:
        raise NotImplementedError

    def run_sql(self, sql: str) -> list[dict[str, Any]]:
        raise NotImplementedError
