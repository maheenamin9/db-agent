from abc import ABC, abstractmethod
from typing import ClassVar

import pandas as pd

from app.connectors.base import Connector, TableNotFoundError
from app.duckdb_helper import DuckDBHelper

# Upper bound for any single query against a live database.
STATEMENT_TIMEOUT_MS = 60_000


class SqlConnector(Connector, ABC):
    """A live SQL database (Postgres, MySQL) reached with read-only credentials.

    The live connection is only for discovery (list_tables, get_schema) and
    previews. To answer questions, selected tables are copied into DuckDB with
    `import_tables`, so the agent only ever queries DuckDB.
    """

    # Exceptions raised by the driver, so callers can tell "the database said no" from bugs.
    errors: ClassVar[tuple[type[Exception], ...]] = (Exception,)

    @abstractmethod
    def quote(self, identifier: str) -> str:
        """Quote a table/column name for this database's SQL dialect."""

    def preview(self, table: str, limit: int = 20) -> pd.DataFrame:
        self._require_tables([table])
        return self.run_sql(f"SELECT * FROM {self.quote(table)} LIMIT {int(limit)}")

    def import_tables(self, tables: list[str], db: DuckDBHelper) -> dict[str, int]:
        """Copy whole tables into DuckDB under the same names. Returns rows copied per table."""
        self._require_tables(tables)
        imported = {}
        for table in tables:
            df = self.run_sql(f"SELECT * FROM {self.quote(table)}")
            db.register_dataframe(table, df)
            imported[table] = len(df)
        return imported

    def _require_tables(self, tables: list[str]) -> None:
        known = set(self.list_tables())
        missing = [t for t in tables if t not in known]
        if missing:
            raise TableNotFoundError(", ".join(missing))
