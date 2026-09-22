"""Contract + behaviour tests against the seeded docker-compose databases.

Run `docker compose up -d postgres mysql` first. Without them these tests skip.
Connection details default to the compose read-only user (Postgres on host port 5433) and can be overridden with
TEST_POSTGRES_* / TEST_MYSQL_* environment variables.
"""

import os

import pytest

from app.connectors.base import TableNotFoundError
from app.connectors.mysql import MySQLConfig, MySQLConnector
from app.connectors.postgres import PostgresConfig, PostgresConnector
from app.duckdb_helper import DuckDBHelper
from tests.connector_contract import ConnectorContract

pytestmark = pytest.mark.integration

TABLES = ["customers", "order_items", "orders", "products"]


def _env(prefix: str, key: str, default: str) -> str:
    return os.environ.get(f"TEST_{prefix}_{key}", default)


def postgres_config(**overrides) -> PostgresConfig:
    values = dict(
        host=_env("POSTGRES", "HOST", "localhost"),
        port=int(_env("POSTGRES", "PORT", "5433")),
        database=_env("POSTGRES", "DB", "demo"),
        user=_env("POSTGRES", "USER", "readonly"),
        password=_env("POSTGRES", "PASSWORD", "readonly"),
    )
    return PostgresConfig(**{**values, **overrides})


def mysql_config(**overrides) -> MySQLConfig:
    values = dict(
        host=_env("MYSQL", "HOST", "127.0.0.1"),
        port=int(_env("MYSQL", "PORT", "3306")),
        database=_env("MYSQL", "DB", "demo"),
        user=_env("MYSQL", "USER", "readonly"),
        password=_env("MYSQL", "PASSWORD", "readonly"),
    )
    return MySQLConfig(**{**values, **overrides})


def reachable_or_skip(connector):
    try:
        connector.list_tables()
    except connector.errors as e:
        pytest.skip(f"database not reachable: {e}")
    return connector


class LiveSqlChecks:
    """Behaviour shared by both databases, on top of the generic contract."""

    make_connector = None  # set by subclasses: (overrides) -> connector

    @pytest.fixture
    def connector(self):
        return reachable_or_skip(self.make_connector())

    def test_seeded_tables(self, connector):
        assert connector.list_tables() == TABLES

    def test_schema_reflects_constraints(self, connector):
        by_name = {c.name: c for c in connector.get_schema("orders")}
        assert list(by_name) == ["id", "customer_id", "order_date", "status", "total_amount"]
        assert by_name["total_amount"].nullable is False

    def test_preview_returns_limited_rows(self, connector):
        assert len(connector.preview("customers", limit=3)) == 3

    def test_agent_account_cannot_write(self, connector):
        for statement in (
            "INSERT INTO customers (id, name, email, country, created_at) "
            "VALUES (999, 'x', 'x@example.com', 'x', '2026-01-01 00:00:00')",
            "UPDATE customers SET name = 'hacked'",
            "DELETE FROM customers",
            "DROP TABLE customers",
        ):
            with pytest.raises(connector.errors):
                connector.run_sql(statement)
        assert len(connector.run_sql("SELECT * FROM customers")) == 15

    def test_wrong_password_is_rejected(self):
        bad = self.make_connector(password="definitely-wrong")
        reachable_or_skip(self.make_connector())  # skip if the server is down at all
        with pytest.raises(bad.errors):
            bad.list_tables()

    def test_import_into_duckdb_matches_source(self, connector):
        with DuckDBHelper(":memory:") as db:
            counts = connector.import_tables(["customers", "orders", "order_items"], db)

            assert counts == {"customers": 15, "orders": 40, "order_items": 102}
            assert db.list_tables() == ["customers", "order_items", "orders"]

            sql = "SELECT sum(total_amount) AS s FROM orders"
            assert float(db.query(sql)["s"][0]) == pytest.approx(float(connector.run_sql(sql)["s"][0]))

            # Joins across imported tables work and dates/decimals arrive usable.
            top = db.query(
                "SELECT c.country, sum(o.total_amount) AS revenue FROM orders o "
                "JOIN customers c ON c.id = o.customer_id "
                "WHERE o.status = 'completed' AND o.order_date >= DATE '2026-01-01' "
                "GROUP BY c.country ORDER BY revenue DESC LIMIT 3"
            )
            assert len(top) == 3

    def test_import_unknown_table_imports_nothing(self, connector):
        with DuckDBHelper(":memory:") as db:
            with pytest.raises(TableNotFoundError):
                connector.import_tables(["customers", "nope"], db)
            assert db.list_tables() == []


class TestPostgresConnector(LiveSqlChecks, ConnectorContract):
    @staticmethod
    def make_connector(**overrides):
        return PostgresConnector(postgres_config(**overrides))


class TestMySQLConnector(LiveSqlChecks, ConnectorContract):
    @staticmethod
    def make_connector(**overrides):
        return MySQLConnector(mysql_config(**overrides))
