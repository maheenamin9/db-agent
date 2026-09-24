import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.duckdb_helper import DuckDBHelper, get_helper
from app.main import app
from app.semantics.schema import Model, Relationship, Semantics
from app.semantics.store import write_semantics

REL = {
    "from_model": "orders",
    "from_column": "customer_id",
    "to_model": "customers",
    "to_column": "id",
}


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")
    monkeypatch.setattr(get_settings(), "table_selection_path", tmp_path / "table_selection.json")


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("customers", pd.DataFrame({"id": [1]}))
        helper.register_dataframe("orders", pd.DataFrame({"id": [1], "customer_id": [1]}))
        helper.register_dataframe("scratch", pd.DataFrame({"x": [1]}))
        yield helper


@pytest.fixture
def client(db):
    app.dependency_overrides[get_helper] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_delete_removes_the_table_from_duckdb(client, db):
    res = client.delete("/tables/scratch")

    assert res.status_code == 200
    assert res.json() == {"table": "scratch", "model_removed": False, "relationships_removed": 0}
    assert "scratch" not in db.list_tables()
    assert [t["name"] for t in client.get("/tables").json()] == ["customers", "orders"]


def test_delete_unknown_table_is_404(client, db):
    res = client.delete("/tables/nope")
    assert res.status_code == 404
    assert set(db.list_tables()) == {"customers", "orders", "scratch"}


def test_delete_removes_the_matching_model(client):
    write_semantics(Semantics(models=[Model(name="scratch", description="temp")]))
    res = client.delete("/tables/scratch")

    assert res.json()["model_removed"] is True
    assert client.get("/semantics").json()["models"] == []


def test_delete_leaves_other_models_untouched(client):
    write_semantics(Semantics(models=[Model(name="scratch"), Model(name="customers")]))
    client.delete("/tables/scratch")

    remaining = [m["name"] for m in client.get("/semantics").json()["models"]]
    assert remaining == ["customers"]


def test_delete_removes_relationships_that_reference_it(client):
    write_semantics(Semantics(relationships=[Relationship(**REL)]))
    res = client.delete("/tables/orders")  # the "from" side of the relationship

    assert res.json()["relationships_removed"] == 1
    assert client.get("/relationships").json() == []


def test_delete_removes_relationships_where_it_is_the_target_side(client):
    write_semantics(Semantics(relationships=[Relationship(**REL)]))
    res = client.delete("/tables/customers")  # the "to" side

    assert res.json()["relationships_removed"] == 1
    assert client.get("/relationships").json() == []


def test_delete_table_not_involved_leaves_relationships_alone(client):
    write_semantics(Semantics(relationships=[Relationship(**REL)]))
    res = client.delete("/tables/scratch")

    assert res.json()["relationships_removed"] == 0
    assert len(client.get("/relationships").json()) == 1


def test_delete_narrows_an_explicit_selection(client):
    client.post("/tables/select", json={"tables": ["customers", "scratch"]})
    client.delete("/tables/scratch")
    assert client.get("/tables/selection").json() == {"tables": ["customers"]}


def test_delete_the_last_selected_table_reverts_to_no_selection(client):
    """Emptying the explicit list would otherwise leave the Tables UI showing
    everything unchecked; reverting to null (= everything) is the safer default."""
    client.post("/tables/select", json={"tables": ["scratch"]})
    client.delete("/tables/scratch")
    assert client.get("/tables/selection").json() == {"tables": None}


def test_delete_when_table_is_not_in_the_selection_leaves_it_alone(client):
    client.post("/tables/select", json={"tables": ["customers"]})
    client.delete("/tables/scratch")
    assert client.get("/tables/selection").json() == {"tables": ["customers"]}


# The bug report this whole feature grew out of: deselecting a table (not deleting
# it) must also stop it from being described in Semantics.
def test_deselecting_a_table_prunes_its_already_synced_model(client):
    client.post("/semantics/sync")  # describes customers, orders, and scratch
    assert {m["name"] for m in client.get("/semantics").json()["models"]} == {
        "customers",
        "orders",
        "scratch",
    }

    client.post("/tables/select", json={"tables": ["customers", "orders"]})  # drop scratch from scope

    names = {m["name"] for m in client.get("/semantics").json()["models"]}
    assert names == {"customers", "orders"}


def test_deselecting_a_table_prunes_relationships_referencing_it(client):
    write_semantics(Semantics(relationships=[Relationship(**REL)]))  # references orders + customers
    client.post("/tables/select", json={"tables": ["orders", "scratch"]})  # excludes customers

    assert client.get("/relationships").json() == []


def test_reselecting_a_table_lets_sync_describe_it_again(client):
    client.post("/tables/select", json={"tables": ["customers"]})  # excludes orders, scratch
    client.post("/semantics/sync")
    assert {m["name"] for m in client.get("/semantics").json()["models"]} == {"customers"}

    client.post("/tables/select", json={"tables": ["customers", "orders", "scratch"]})
    client.post("/semantics/sync")
    assert {m["name"] for m in client.get("/semantics").json()["models"]} == {
        "customers",
        "orders",
        "scratch",
    }
