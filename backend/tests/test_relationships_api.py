import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app


@pytest.fixture(autouse=True)
def isolate_semantics(tmp_path, monkeypatch):
    # Never let a test write into the real, tracked data/semantics.yaml.
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("customers", pd.DataFrame({"id": [1, 2], "name": ["Ann", "Bob"]}))
        helper.register_dataframe("orders", pd.DataFrame({"id": [1], "customer_id": [1]}))
        yield helper


@pytest.fixture
def client(db):
    app.dependency_overrides[get_helper] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


REL = {
    "from_model": "orders",
    "from_column": "customer_id",
    "to_model": "customers",
    "to_column": "id",
}


def test_list_starts_empty(client):
    assert client.get("/relationships").json() == []


def test_suggest_finds_the_fk_and_does_not_persist(client):
    res = client.post("/relationships/suggest", json={})
    assert res.status_code == 200
    suggestions = res.json()
    assert len(suggestions) == 1
    assert suggestions[0]["from_model"] == "orders"
    assert suggestions[0]["confidence"] == 0.9
    assert "reason" in suggestions[0]
    assert client.get("/relationships").json() == []  # suggest never writes


def test_suggest_can_be_scoped_to_tables(client):
    res = client.post("/relationships/suggest", json={"tables": ["customers"]})
    assert res.status_code == 200
    assert res.json() == []


def test_suggest_unknown_table_is_422(client):
    res = client.post("/relationships/suggest", json={"tables": ["nope"]})
    assert res.status_code == 422


def test_suggest_omits_already_saved_relationships(client):
    client.post("/relationships", json=REL)
    res = client.post("/relationships/suggest", json={})
    assert res.json() == []


def test_create_persists_and_returns_it_with_an_id(client):
    res = client.post("/relationships", json=REL)
    assert res.status_code == 201
    body = res.json()
    assert body["id"]
    assert {k: body[k] for k in REL} == REL
    assert body["cardinality"] == "many_to_one"

    listed = client.get("/relationships").json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_create_unknown_table_is_422(client):
    res = client.post("/relationships", json={**REL, "from_model": "nope"})
    assert res.status_code == 422
    assert client.get("/relationships").json() == []


def test_create_unknown_column_is_422(client):
    res = client.post("/relationships", json={**REL, "from_column": "nope"})
    assert res.status_code == 422
    assert client.get("/relationships").json() == []


def test_create_accepts_explicit_cardinality(client):
    res = client.post("/relationships", json={**REL, "cardinality": "one_to_many"})
    assert res.json()["cardinality"] == "one_to_many"


def test_create_rejects_unknown_cardinality(client):
    res = client.post("/relationships", json={**REL, "cardinality": "sideways"})
    assert res.status_code == 422


def test_update_replaces_fields(client):
    rel_id = client.post("/relationships", json=REL).json()["id"]
    res = client.put(f"/relationships/{rel_id}", json={**REL, "cardinality": "one_to_one"})

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == rel_id
    assert body["cardinality"] == "one_to_one"
    assert len(client.get("/relationships").json()) == 1


def test_update_unknown_id_is_404(client):
    res = client.put("/relationships/nope", json=REL)
    assert res.status_code == 404


def test_update_validates_new_endpoints(client):
    rel_id = client.post("/relationships", json=REL).json()["id"]
    res = client.put(f"/relationships/{rel_id}", json={**REL, "to_column": "nope"})
    assert res.status_code == 422
    assert client.get("/relationships").json()[0]["to_column"] == "id"  # unchanged


def test_delete_removes_it(client):
    rel_id = client.post("/relationships", json=REL).json()["id"]
    res = client.delete(f"/relationships/{rel_id}")

    assert res.status_code == 204
    assert client.get("/relationships").json() == []


def test_delete_unknown_id_is_404(client):
    res = client.delete("/relationships/nope")
    assert res.status_code == 404


def test_full_suggest_then_create_flow(client):
    suggestion = client.post("/relationships/suggest", json={}).json()[0]
    created = client.post(
        "/relationships",
        json={k: suggestion[k] for k in ("from_model", "from_column", "to_model", "to_column")},
    ).json()

    assert created["from_model"] == suggestion["from_model"]
    assert client.post("/relationships/suggest", json={}).json() == []  # now already saved
