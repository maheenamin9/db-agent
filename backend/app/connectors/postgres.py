import pandas as pd

from app.connectors.base import ColumnInfo, Connector


class PostgresConnector(Connector):
    def __init__(self, dsn: str):
        self.dsn = dsn

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> list[ColumnInfo]:
        raise NotImplementedError

    def run_sql(self, query: str) -> pd.DataFrame:
        raise NotImplementedError
