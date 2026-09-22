from contextlib import closing

import pandas as pd
import pymysql
from pydantic import BaseModel

from app.connectors.base import ColumnInfo, TableNotFoundError
from app.connectors.sql import STATEMENT_TIMEOUT_MS, SqlConnector


class MySQLConfig(BaseModel):
    host: str
    port: int = 3306
    database: str
    user: str
    password: str


class MySQLConnector(SqlConnector):
    errors = (pymysql.MySQLError,)

    def __init__(self, config: MySQLConfig):
        self.config = config

    def _fetch(self, query: str, params: tuple | None = None) -> pd.DataFrame:
        c = self.config
        # A fresh short-lived connection per call keeps the connector stateless.
        # Sessions are read-only even if someone passes privileged credentials.
        with closing(
            pymysql.connect(
                host=c.host,
                port=c.port,
                user=c.user,
                password=c.password,
                database=c.database,
                connect_timeout=5,
                autocommit=True,
                init_command=(
                    "SET @@session.transaction_read_only = 1, "
                    f"@@session.max_execution_time = {STATEMENT_TIMEOUT_MS}"
                ),
            )
        ) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description is None:
                return pd.DataFrame()
            return pd.DataFrame(list(cur.fetchall()), columns=[d[0] for d in cur.description])

    def quote(self, identifier: str) -> str:
        return "`" + identifier.replace("`", "``") + "`"

    def list_tables(self) -> list[str]:
        df = self._fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
            (self.config.database,),
        )
        return df.iloc[:, 0].tolist()

    def get_schema(self, table: str) -> list[ColumnInfo]:
        df = self._fetch(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (self.config.database, table),
        )
        if df.empty:
            raise TableNotFoundError(table)
        return [ColumnInfo(name=n, type=t, nullable=nullable == "YES") for n, t, nullable in df.itertuples(index=False)]

    def run_sql(self, query: str) -> pd.DataFrame:
        return self._fetch(query)
