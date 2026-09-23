import threading
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from app.config import get_settings
from app.connectors.base import ColumnInfo


def quote_ident(name: str) -> str:
    """Quote a table name so spaces and odd characters are safe in SQL."""
    return '"' + name.replace('"', '""') + '"'


class DuckDBHelper:
    """A persistent DuckDB connection: load data into tables, then query them.

    Pass ":memory:" as `path` for a throwaway database. Tables are real tables
    (not views), so they survive a restart when `path` is a file.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = str(path or get_settings().duckdb_path)
        self._con = duckdb.connect(self.path)
        # A DuckDB connection is not safe for concurrent use, and FastAPI
        # serves sync endpoints from a thread pool.
        self._lock = threading.Lock()

    def register_dataframe(self, name: str, df: pd.DataFrame) -> None:
        """Materialize a DataFrame as a table, replacing any table of that name."""
        with self._lock:
            self._con.register("_incoming", df)
            try:
                self._con.execute(
                    f"CREATE OR REPLACE TABLE {quote_ident(name)} AS SELECT * FROM _incoming"
                )
            finally:
                self._con.unregister("_incoming")

    def load_csv(self, name: str, path: str | Path) -> None:
        """Load a CSV file with DuckDB's read_csv_auto (types are inferred)."""
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        with self._lock:
            self._con.execute(
                f"CREATE OR REPLACE TABLE {quote_ident(name)} AS SELECT * FROM read_csv_auto(?)",
                [str(path)],
            )

    def load_excel(self, name: str, path: str | Path, sheet_name: str | int | None = None) -> None:
        """Load one Excel sheet via pandas. `sheet_name=None` means the first sheet."""
        df = pd.read_excel(path, sheet_name=0 if sheet_name is None else sheet_name)
        df.columns = [str(c) for c in df.columns]
        self.register_dataframe(name, df)

    def query(self, sql: str) -> pd.DataFrame:
        """Run SQL and return the result as a DataFrame."""
        with self._lock:
            return self._con.execute(sql).fetch_df()

    def list_tables(self) -> list[str]:
        return self.query("SELECT table_name FROM information_schema.tables ORDER BY table_name")[
            "table_name"
        ].tolist()

    def describe(self, table: str) -> list[ColumnInfo]:
        """Column names/types/nullability for a table already in the warehouse."""
        rows = self.query(f"DESCRIBE {quote_ident(table)}").to_dict("records")
        return [
            ColumnInfo(name=r["column_name"], type=r["column_type"], nullable=r["null"] == "YES")
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def __enter__(self) -> "DuckDBHelper":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


@lru_cache
def get_helper() -> DuckDBHelper:
    """Shared helper on data/warehouse.duckdb for the app to use."""
    return DuckDBHelper()
