from typing import Any

import pytest

from app.connectors.base import ColumnInfo, Connector, TableSchema


class FakeConnector(Connector):
    def list_tables(self) -> list[str]:
        return ["orders"]

    def get_schema(self, table: str) -> TableSchema:
        return TableSchema(name=table, columns=[ColumnInfo(name="id", type="INTEGER")])

    def run_sql(self, sql: str) -> list[dict[str, Any]]:
        return [{"id": 1}]


def test_connector_is_abstract():
    with pytest.raises(TypeError):
        Connector()  # type: ignore[abstract]


def test_fake_connector_satisfies_interface():
    c = FakeConnector()
    assert c.list_tables() == ["orders"]
    assert c.get_schema("orders").columns[0].name == "id"
    assert c.run_sql("SELECT 1") == [{"id": 1}]
