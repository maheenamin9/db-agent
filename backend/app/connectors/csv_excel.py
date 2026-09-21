from pathlib import Path

import pandas as pd

from app.connectors.base import ColumnInfo, Connector


class CsvExcelConnector(Connector):
    """CSV files and Excel workbooks (one table per CSV, one per sheet)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> list[ColumnInfo]:
        raise NotImplementedError

    def run_sql(self, query: str) -> pd.DataFrame:
        raise NotImplementedError
