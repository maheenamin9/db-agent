import pytest
from fastapi.testclient import TestClient

from app.connectors.postgres import PostgresConfig
from app.connectors.registry import CONNECTOR_TYPES, SourceRegistry, get_registry
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app
from tests.fake_sql_connector import DownConnector, FakeSqlConnector

PG_BODY = {
    "type": "postgres",
    "name": "shop",
    "config": {"host": "db", "database": "demo", "user": "readonly", "password": "s3cret-pw"},
}


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        yield helper


@pytest.fixture
def client(db, monkeypatch):
    # Swap the real Postgres connector for a fake one: no database needed.
    monkeypatch.setitem(CONNECTOR_TYPES, "postgres", (PostgresConfig, lambda config: FakeSqlConnector()))
    registry = SourceRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_helper] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def connect(client, body=PG_BODY):
    res = client.post("/sources", json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_create_source_returns_id_without_credentials(client):
    res = client.post("/sources", json=PG_BODY)

    assert res.status_code == 201
    body = res.json()
    assert set(body) == {"id", "type", "name"}
    assert body["type"] == "postgres" and body["name"] == "shop"
    assert "s3cret-pw" not in res.text


def test_name_defaults_to_type(client):
    body = {**PG_BODY}
    del body["name"]
    assert client.post("/sources", json=body).json()["name"] == "postgres"


def test_list_sources(client):
    assert client.get("/sources").json() == []
    source_id = connect(client)
    assert [s["id"] for s in client.get("/sources").json()] == [source_id]


def test_source_tables_lists_live_schema(client):
    source_id = connect(client)
    res = client.get(f"/sources/{source_id}/tables")

    assert res.status_code == 200
    tables = {t["name"]: [c["name"] for c in t["columns"]] for t in res.json()}
    assert tables == {
        "customers": ["id", "name", "country"],
        "orders": ["id", "customer_id", "amount", "ordered_at"],
    }


def test_unknown_source_is_404(client):
    assert client.get("/sources/nope/tables").status_code == 404
    assert client.post("/sources/nope/import", json={"tables": ["x"]}).status_code == 404


def test_missing_config_fields_are_422_and_do_not_echo_password(client):
    body = {"type": "postgres", "config": {"host": "db", "password": "s3cret-pw"}}
    res = client.post("/sources", json=body)

    assert res.status_code == 422
    missing = {e["loc"][-1] for e in res.json()["detail"]}
    assert missing == {"database", "user"}
    assert "s3cret-pw" not in res.text


def test_unknown_type_is_422(client):
    assert client.post("/sources", json={**PG_BODY, "type": "oracle"}).status_code == 422


def test_unreachable_database_is_400_and_not_registered(client, monkeypatch):
    monkeypatch.setitem(CONNECTOR_TYPES, "postgres", (PostgresConfig, lambda config: DownConnector()))
    res = client.post("/sources", json=PG_BODY)

    assert res.status_code == 400
    assert "connection refused" in res.json()["detail"]
    assert client.get("/sources").json() == []


def test_import_copies_selected_tables_into_duckdb(client, db):
    source_id = connect(client)
    res = client.post(f"/sources/{source_id}/import", json={"tables": ["orders"]})

    assert res.status_code == 200
    assert res.json() == {"imported": [{"name": "orders", "rows": 4}]}
    assert db.list_tables() == ["orders"]
    assert db.query("SELECT count(*) AS n FROM orders")["n"][0] == 4


def test_import_unknown_table_is_404_and_imports_nothing(client, db):
    source_id = connect(client)
    res = client.post(f"/sources/{source_id}/import", json={"tables": ["orders", "nope"]})

    assert res.status_code == 404
    assert "nope" in res.json()["detail"]
    assert db.list_tables() == []


def test_import_requires_at_least_one_table(client):
    source_id = connect(client)
    assert client.post(f"/sources/{source_id}/import", json={"tables": []}).status_code == 422
