"""Connector contract suite.

`ConnectorContract` holds the tests every connector must pass. To test a new
connector, subclass it and provide a `connector` fixture:

    class TestPostgresConnector(ConnectorContract):
        @pytest.fixture
        def connector(self): ...
"""

import pandas as pd
import pytest

from app.connectors.base import ColumnInfo, Connector, TableNotFoundError
from tests.mock_connector import MockConnector


class ConnectorContract:
    @pytest.fixture
    def connector(self) -> Connector:
        raise NotImplementedError

    # list_tables
    def test_list_tables_returns_unique_names(self, connector):
        tables = connector.list_tables()
        assert isinstance(tables, list)
        assert tables, "connector should expose at least one table"
        assert all(isinstance(t, str) and t for t in tables)
        assert len(tables) == len(set(tables))

    # get_schema
    def test_get_schema_returns_column_info(self, connector):
        for table in connector.list_tables():
            columns = connector.get_schema(table)
            assert isinstance(columns, list) and columns
            assert all(isinstance(c, ColumnInfo) for c in columns)
            assert all(c.name and c.type for c in columns)
            names = [c.name for c in columns]
            assert len(names) == len(set(names))

    def test_get_schema_unknown_table_raises(self, connector):
        with pytest.raises(TableNotFoundError):
            connector.get_schema("definitely_not_a_table")

    # run_sql
    def test_run_sql_returns_dataframe(self, connector):
        df = connector.run_sql(f"SELECT * FROM {connector.list_tables()[0]}")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_run_sql_columns_match_schema(self, connector):
        for table in connector.list_tables():
            expected = [c.name for c in connector.get_schema(table)]
            df = connector.run_sql(f"SELECT * FROM {table}")
            assert list(df.columns) == expected

    def test_run_sql_respects_limit(self, connector):
        table = connector.list_tables()[0]
        assert len(connector.run_sql(f"SELECT * FROM {table} LIMIT 1")) == 1

    def test_run_sql_invalid_query_raises_with_message(self, connector):
        with pytest.raises(Exception) as exc:
            connector.run_sql("SELEKT nonsense FROM nowhere")
        assert str(exc.value).strip()


class TestMockConnector(ConnectorContract):
    @pytest.fixture
    def connector(self):
        return MockConnector()

    # Mock-specific checks against its known fake data
    def test_tables(self, connector):
        assert connector.list_tables() == ["customers", "orders"]

    def test_schema_details(self, connector):
        by_name = {c.name: c for c in connector.get_schema("orders")}
        assert list(by_name) == ["id", "customer_id", "amount", "ordered_at"]
        assert by_name["amount"].type == "DOUBLE"
        assert by_name["ordered_at"].type == "DATE"

    def test_join_query(self, connector):
        df = connector.run_sql(
            "SELECT c.name, sum(o.amount) AS total "
            "FROM customers c JOIN orders o ON o.customer_id = c.id "
            "GROUP BY c.name ORDER BY c.name"
        )
        assert df["name"].tolist() == ["Ann", "Bob", "Cy"]
        assert df["total"].round(1).tolist() == [65.5, 12.0, 99.9]


def test_connector_is_abstract():
    with pytest.raises(TypeError):
        Connector()  # type: ignore[abstract]


def test_partial_subclass_cannot_instantiate():
    class Partial(Connector):
        def list_tables(self):
            return []

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]
