from pathlib import Path

import duckdb
import pandas as pd

from app.config import get_settings


def get_connection(path: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the file-backed warehouse, or pass ":memory:" for a throwaway one."""
    return duckdb.connect(str(path or get_settings().duckdb_path))


def load_dataframe(con: duckdb.DuckDBPyConnection, name: str, df: pd.DataFrame) -> None:
    con.register("_incoming", df)
    con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM _incoming')
    con.unregister("_incoming")


def load_csv(con: duckdb.DuckDBPyConnection, name: str, path: str | Path) -> None:
    con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM read_csv_auto(?)', [str(path)])


def load_excel(
    con: duckdb.DuckDBPyConnection, name: str, path: str | Path, sheet: str | int = 0
) -> None:
    load_dataframe(con, name, pd.read_excel(path, sheet_name=sheet))


def run_sql(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).fetch_df()
