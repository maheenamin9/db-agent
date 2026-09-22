import pandas as pd
import psycopg
from pydantic import BaseModel

from app.connectors.base import ColumnInfo, TableNotFoundError
from app.connectors.sql import STATEMENT_TIMEOUT_MS, SqlConnector
from app.duckdb_helper import quote_ident


class PostgresConfig(BaseModel):
    host: str
    port: int = 5432
    database: str
    user: str
    password: str
    schema_name: str = "public"


class PostgresConnector(SqlConnector):
    errors = (psycopg.Error,)

    def __init__(self, config: PostgresConfig):
        self.config = config

    def _fetch(self, query: str, params: tuple | None = None) -> pd.DataFrame:
        c = self.config
        # A fresh short-lived connection per call keeps the connector stateless.
        # Sessions are read-only even if someone passes privileged credentials.
        with psycopg.connect(
            host=c.host,
            port=c.port,
            dbname=c.database,
            user=c.user,
            password=c.password,
            connect_timeout=5,
            autocommit=True,
            options=f"-c default_transaction_read_only=on -c statement_timeout={STATEMENT_TIMEOUT_MS}",
        ) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description is None:
                return pd.DataFrame()
            return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])

    def quote(self, identifier: str) -> str:
        return quote_ident(identifier)

    def list_tables(self) -> list[str]:
        df = self._fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
            (self.config.schema_name,),
        )
        return df["table_name"].tolist()

    def get_schema(self, table: str) -> list[ColumnInfo]:
        df = self._fetch(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (self.config.schema_name, table),
        )
        if df.empty:
            raise TableNotFoundError(table)
        return [ColumnInfo(name=n, type=t, nullable=nullable == "YES") for n, t, nullable in df.itertuples(index=False)]

    def run_sql(self, query: str) -> pd.DataFrame:
        return self._fetch(query)
