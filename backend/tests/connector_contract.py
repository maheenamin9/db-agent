"""Connector contract suite.

`ConnectorContract` holds the tests every connector must pass. To test a new
connector, subclass it in a test module and provide a `connector` fixture:

    class TestPostgresConnector(ConnectorContract):
        @pytest.fixture
        def connector(self): ...
"""

import pandas as pd
import pytest

from app.connectors.base import ColumnInfo, Connector, TableNotFoundError


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
