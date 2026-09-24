import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.semantics.describe import get_chat_model
from app.semantics.schema import Column, Model, Semantics
from app.semantics.store import write_semantics
from tests.test_describe import FailingChatModel, FakeChatModel


@pytest.fixture(autouse=True)
def isolate_semantics(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")
    monkeypatch.setattr(get_settings(), "table_selection_path", tmp_path / "table_selection.json")


@pytest.fixture
def client():
    app.dependency_overrides[get_chat_model] = lambda: FakeChatModel(
        {"table": "Customer orders.", "columns": {"id": "The order's id."}}
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_generate_fills_in_blank_descriptions(client):
    write_semantics(Semantics(models=[Model(name="orders", columns=[Column(name="id", type="BIGINT")])]))

    res = client.post("/semantics/generate/orders")

    assert res.status_code == 200
    body = res.json()
    assert body["description"] == "Customer orders."
    assert body["columns"][0]["description"] == "The order's id."


def test_generate_does_not_persist_to_semantics_yaml(client):
    write_semantics(Semantics(models=[Model(name="orders", columns=[Column(name="id", type="BIGINT")])]))
    client.post("/semantics/generate/orders")

    stored = client.get("/semantics").json()
    assert stored["models"][0]["description"] == ""  # unaffected until Save (PUT)


def test_generate_never_overwrites_an_existing_description(client):
    write_semantics(
        Semantics(
            models=[
                Model(
                    name="orders",
                    description="hand-written",
                    columns=[Column(name="id", type="BIGINT", description="hand-written too")],
                )
            ]
        )
    )

    res = client.post("/semantics/generate/orders")

    body = res.json()
    assert body["description"] == "hand-written"
    assert body["columns"][0]["description"] == "hand-written too"


def test_generate_unknown_model_is_404(client):
    write_semantics(Semantics())
    res = client.post("/semantics/generate/nope")
    assert res.status_code == 404


def test_generate_connection_error_is_502(client):
    app.dependency_overrides[get_chat_model] = lambda: FailingChatModel()
    write_semantics(Semantics(models=[Model(name="orders")]))

    res = client.post("/semantics/generate/orders")
    assert res.status_code == 502


def test_generate_bad_json_from_model_is_502(client):
    app.dependency_overrides[get_chat_model] = lambda: FakeChatModel(raw="not json at all")
    write_semantics(Semantics(models=[Model(name="orders")]))

    res = client.post("/semantics/generate/orders")
    assert res.status_code == 502
    assert "JSON" in res.json()["detail"]
