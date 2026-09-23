import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.connectors.base import ColumnInfo, Connector, TableNotFoundError
from app.duckdb_helper import DuckDBHelper, get_helper

SUPPORTED_SUFFIXES = {".csv", ".xlsx"}


class FileLoadError(ValueError):
    """The file could not be read as a CSV or Excel workbook."""


def sanitize_table_name(name: str) -> str:
    """Turn a filename or sheet name into a plain SQL identifier the LLM won't need to quote."""
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower() or "table"
    return f"t_{cleaned}" if cleaned[0].isdigit() else cleaned


class CsvExcelConnector(Connector):
    """CSV and Excel files, loaded into DuckDB.

    Files are copied into tables in the warehouse, so this connector exposes
    every table in the DuckDB it is backed by.
    """

    def __init__(self, db: DuckDBHelper | None = None):
        self.db = db or get_helper()

    def load_file(self, path: str | Path, name: str | None = None) -> list[str]:
        """Load a .csv or .xlsx file and return the names of the tables it created.

        A CSV becomes one table. A workbook becomes one table per non-empty
        sheet: `<name>` if it has a single sheet, otherwise `<name>_<sheet>`.
        Loading a file again replaces the tables of the same name.
        """
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise FileLoadError(f"Unsupported file type '{path.suffix}', expected .csv or .xlsx")

        base = sanitize_table_name(name or path.stem)
        try:
            if suffix == ".csv":
                # DuckDB turns an empty file into a bogus one-column table instead of failing.
                with path.open("rb") as f:
                    if not f.read(64 * 1024).strip():
                        raise FileLoadError("The file is empty")
                self.db.load_csv(base, path)
                return [base]
            return self._load_workbook(path, base)
        except FileLoadError:
            raise
        except Exception as e:
            raise FileLoadError(str(e)) from e

    def _load_workbook(self, path: Path, base: str) -> list[str]:
        with pd.ExcelFile(path) as workbook:
            sheets = [s for s in workbook.sheet_names if not workbook.parse(s, nrows=0).columns.empty]
        if not sheets:
            raise FileLoadError("The workbook has no sheets with data")

        tables = []
        for sheet in sheets:
            table = base if len(sheets) == 1 else f"{base}_{sanitize_table_name(str(sheet))}"
            self.db.load_excel(table, path, sheet_name=sheet)
            tables.append(table)
        return tables

    def list_tables(self) -> list[str]:
        return self.db.list_tables()

    def get_schema(self, table: str) -> list[ColumnInfo]:
        if table not in self.list_tables():
            raise TableNotFoundError(table)
        return self.db.describe(table)

    def run_sql(self, query: str) -> pd.DataFrame:
        return self.db.query(query)


@lru_cache
def get_csv_excel_connector() -> CsvExcelConnector:
    """Shared connector on the warehouse, used as a FastAPI dependency."""
    return CsvExcelConnector()
