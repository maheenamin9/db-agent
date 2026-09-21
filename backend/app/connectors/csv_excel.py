from pathlib import Path
from typing import Any

from app.connectors.base import Connector, TableSchema


class CsvExcelConnector(Connector):
    """CSV files and Excel workbooks (one table per CSV, one per sheet)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def list_tables(self) -> list[str]:
        raise NotImplementedError

    def get_schema(self, table: str) -> TableSchema:
        raise NotImplementedError

    def run_sql(self, sql: str) -> list[dict[str, Any]]:
        raise NotImplementedError
