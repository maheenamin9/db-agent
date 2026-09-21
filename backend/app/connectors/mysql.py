import pandas as pd

from app.connectors.base import ColumnInfo, Connector


class MySQLConnector(Connector):
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> list[ColumnInfo]:
        raise NotImplementedError

    def run_sql(self, query: str) -> pd.DataFrame:
        raise NotImplementedError
