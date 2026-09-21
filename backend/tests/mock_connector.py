import duckdb
import pandas as pd

from app.connectors.base import ColumnInfo, Connector, TableNotFoundError


def _fake_tables() -> dict[str, pd.DataFrame]:
    return {
        "customers": pd.DataFrame(
            {
                "id": [1, 2, 3],
                "name": ["Ann", "Bob", "Cy"],
                "country": ["US", "UK", "US"],
            }
        ),
        "orders": pd.DataFrame(
            {
                "id": [10, 11, 12, 13],
                "customer_id": [1, 1, 2, 3],
                "amount": [25.0, 40.5, 12.0, 99.9],
                "ordered_at": pd.to_datetime(
                    ["2026-01-05", "2026-01-20", "2026-02-11", "2026-03-02"]
                ).date,
            }
        ),
    }


class MockConnector(Connector):
    """In-memory connector with a couple of fake tables, queried through DuckDB."""

    def __init__(self, tables: dict[str, pd.DataFrame] | None = None):
        self._tables = tables if tables is not None else _fake_tables()
        self._con = duckdb.connect(":memory:")
        for name, df in self._tables.items():
            self._con.register(name, df)

    def list_tables(self) -> list[str]:
        return sorted(self._tables)

    def get_schema(self, table: str) -> list[ColumnInfo]:
        if table not in self._tables:
            raise TableNotFoundError(table)
        rows = self._con.execute(f'DESCRIBE "{table}"').fetchall()
        # DESCRIBE rows: (column_name, column_type, null, key, default, extra)
        return [ColumnInfo(name=r[0], type=r[1], nullable=r[2] == "YES") for r in rows]

    def run_sql(self, query: str) -> pd.DataFrame:
        return self._con.execute(query).fetch_df()
