import pytest

from app.connectors.base import Connector
from tests.connector_contract import ConnectorContract
from tests.mock_connector import MockConnector


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
