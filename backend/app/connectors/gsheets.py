import pandas as pd

from app.connectors.base import ColumnInfo, Connector


class GoogleSheetsConnector(Connector):
    """One table per worksheet in a Google spreadsheet."""

    def __init__(self, spreadsheet_id: str, credentials_path: str | None = None):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> list[ColumnInfo]:
        raise NotImplementedError

    def run_sql(self, query: str) -> pd.DataFrame:
        raise NotImplementedError
