import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app


@pytest.fixture(autouse=True)
def isolate_semantics(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("customers", pd.DataFrame({"id": [1], "name": ["Ann"]}))
        helper.register_dataframe("orders", pd.DataFrame({"id": [1], "customer_id": [1]}))
        yield helper


@pytest.fixture
def client(db):
    app.dependency_overrides[get_helper] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


VALID_BODY = {
    "models": [
        {
            "name": "customers",
            "description": "People who buy things",
            "columns": [{"name": "id", "type": "BIGINT", "description": "Primary key"}],
        }
    ],
    "relationships": [
        {
            "from_model": "orders",
            "from_column": "customer_id",
            "to_model": "customers",
            "to_column": "id",
        }
    ],
}


def test_get_starts_empty(client):
    assert client.get("/semantics").json() == {"models": [], "relationships": []}


def test_put_then_get_round_trips(client):
    put_res = client.put("/semantics", json=VALID_BODY)
    assert put_res.status_code == 200

    get_res = client.get("/semantics")
    assert get_res.json()["models"][0]["description"] == "People who buy things"
    assert get_res.json()["relationships"][0]["id"]  # server-assigned


def test_put_rejects_shape_mismatch(client):
    res = client.put("/semantics", json={"models": "not-a-list"})
    assert res.status_code == 422


def test_put_rejects_unknown_model_table(client):
    body = {"models": [{"name": "no_such_table", "columns": []}], "relationships": []}
    res = client.put("/semantics", json=body)
    assert res.status_code == 422
    assert "no_such_table" in res.json()["detail"]
    assert client.get("/semantics").json() == {"models": [], "relationships": []}


def test_put_rejects_unknown_model_column(client):
    body = {"models": [{"name": "customers", "columns": [{"name": "nope"}]}], "relationships": []}
    res = client.put("/semantics", json=body)
    assert res.status_code == 422
    assert "customers.nope" in res.json()["detail"]


def test_put_rejects_relationship_to_unknown_table(client):
    body = {
        "models": [],
        "relationships": [
            {"from_model": "orders", "from_column": "customer_id", "to_model": "ghost", "to_column": "id"}
        ],
    }
    res = client.put("/semantics", json=body)
    assert res.status_code == 422
    assert "ghost" in res.json()["detail"]


def test_put_bypass_would_have_been_caught_by_relationships_router_too(client):
    """The same rule /relationships enforces on POST must hold for PUT /semantics,
    since it's a second way to write a relationship."""
    body = {"models": [], "relationships": [{**VALID_BODY["relationships"][0], "to_column": "typo"}]}
    assert client.put("/semantics", json=body).status_code == 422


def test_corrupt_file_is_500_not_a_raw_crash(client):
    get_settings().semantics_path.parent.mkdir(parents=True, exist_ok=True)
    get_settings().semantics_path.write_text("models: [not valid")
    res = client.get("/semantics")
    assert res.status_code == 500
    assert "not valid YAML" in res.json()["detail"]


def test_sync_creates_a_model_per_table_with_real_columns(client):
    res = client.post("/semantics/sync")
    assert res.status_code == 200

    by_name = {m["name"]: m for m in res.json()["models"]}
    assert set(by_name) == {"customers", "orders"}
    assert [c["name"] for c in by_name["customers"]["columns"]] == ["id", "name"]
    assert by_name["customers"]["columns"][0]["type"] == "BIGINT"
    assert by_name["customers"]["columns"][0]["description"] == ""


def test_sync_never_overwrites_an_existing_description(client):
    client.post("/semantics/sync")
    semantics = client.get("/semantics").json()
    semantics["models"][0]["description"] = "hand-written description"
    semantics["models"][0]["columns"][0]["description"] = "hand-written column note"
    client.put("/semantics", json=semantics)

    client.post("/semantics/sync")  # re-sync shouldn't touch what a human wrote

    after = client.get("/semantics").json()
    model = next(m for m in after["models"] if m["name"] == semantics["models"][0]["name"])
    assert model["description"] == "hand-written description"
    assert model["columns"][0]["description"] == "hand-written column note"


def test_sync_adds_new_columns_without_touching_existing_ones(client, db):
    client.post("/semantics/sync")
    client.put(
        "/semantics",
        json={
            "models": [
                {
                    "name": "customers",
                    "columns": [{"name": "id", "description": "kept"}, {"name": "name"}],
                }
            ],
            "relationships": [],
        },
    )

    db.register_dataframe("customers", pd.DataFrame({"id": [1], "name": ["Ann"], "country": ["US"]}))
    res = client.post("/semantics/sync")

    model = next(m for m in res.json()["models"] if m["name"] == "customers")
    columns = {c["name"]: c for c in model["columns"]}
    assert set(columns) == {"id", "name", "country"}
    assert columns["id"]["description"] == "kept"
    assert columns["country"]["description"] == ""


def test_sync_is_idempotent(client):
    first = client.post("/semantics/sync").json()
    second = client.post("/semantics/sync").json()
    assert first == second


def test_sync_ignores_tables_dropped_from_duckdb(client):
    """Sync is purely additive: a table that's momentarily missing (e.g. a
    disconnected source) doesn't get its description silently deleted."""
    client.post("/semantics/sync")
    app.dependency_overrides[get_helper] = lambda: DuckDBHelper(":memory:")

    res = client.post("/semantics/sync")
    names = {m["name"] for m in res.json()["models"]}
    assert {"customers", "orders"} <= names
