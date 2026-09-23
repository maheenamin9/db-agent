import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app


@pytest.fixture(autouse=True)
def isolate_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "table_selection_path", tmp_path / "table_selection.json")


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("customers", pd.DataFrame({"id": [1]}))
        helper.register_dataframe("orders", pd.DataFrame({"id": [1]}))
        yield helper


@pytest.fixture
def client(db):
    app.dependency_overrides[get_helper] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_selection_starts_as_none(client):
    assert client.get("/tables/selection").json() == {"tables": None}


def test_select_persists_and_reads_back(client):
    res = client.post("/tables/select", json={"tables": ["customers"]})
    assert res.status_code == 200
    assert res.json() == {"tables": ["customers"]}
    assert client.get("/tables/selection").json() == {"tables": ["customers"]}


def test_select_rejects_unknown_table(client):
    res = client.post("/tables/select", json={"tables": ["customers", "nope"]})
    assert res.status_code == 422
    assert "nope" in res.json()["detail"]
    assert client.get("/tables/selection").json() == {"tables": None}  # unchanged


def test_select_requires_at_least_one_table(client):
    assert client.post("/tables/select", json={"tables": []}).status_code == 422


def test_reselecting_replaces_the_previous_choice(client):
    client.post("/tables/select", json={"tables": ["customers", "orders"]})
    client.post("/tables/select", json={"tables": ["orders"]})
    assert client.get("/tables/selection").json() == {"tables": ["orders"]}
