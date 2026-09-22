import pandas as pd
import pytest

from app.connectors.base import TableNotFoundError
from app.duckdb_helper import DuckDBHelper
from tests.connector_contract import ConnectorContract
from tests.fake_sql_connector import FakeSqlConnector


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        yield helper


class TestFakeSqlConnector(ConnectorContract):
    @pytest.fixture
    def connector(self):
        return FakeSqlConnector()


def test_preview_limits_rows():
    assert len(FakeSqlConnector().preview("orders", limit=2)) == 2


def test_preview_unknown_table():
    with pytest.raises(TableNotFoundError):
        FakeSqlConnector().preview("nope")


def test_import_tables_copies_into_duckdb(db):
    counts = FakeSqlConnector().import_tables(["customers", "orders"], db)

    assert counts == {"customers": 3, "orders": 4}
    assert db.list_tables() == ["customers", "orders"]
    joined = db.query(
        "SELECT c.name, sum(o.amount) AS total FROM customers c "
        "JOIN orders o ON o.customer_id = c.id GROUP BY c.name ORDER BY c.name"
    )
    assert joined["name"].tolist() == ["Ann", "Bob", "Cy"]


def test_import_only_selected_tables(db):
    FakeSqlConnector().import_tables(["orders"], db)
    assert db.list_tables() == ["orders"]


def test_import_unknown_table_imports_nothing(db):
    with pytest.raises(TableNotFoundError, match="nope"):
        FakeSqlConnector().import_tables(["customers", "nope"], db)
    assert db.list_tables() == []


def test_import_empty_table_keeps_columns(db):
    empty = pd.DataFrame({"a": pd.Series([], dtype="object"), "b": pd.Series([], dtype="object")})
    connector = FakeSqlConnector({"t": empty})
    assert connector.import_tables(["t"], db) == {"t": 0}
    assert list(db.query("SELECT * FROM t").columns) == ["a", "b"]


def test_reimport_replaces_table(db):
    FakeSqlConnector().import_tables(["customers"], db)
    FakeSqlConnector({"customers": pd.DataFrame({"only": [1]})}).import_tables(["customers"], db)
    assert list(db.query("SELECT * FROM customers").columns) == ["only"]
