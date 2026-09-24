"""The literal smoke test the task asks for: deploy a tiny fixture semantics file
through the real embedding model, then query Qdrant back and get it.

Skips cleanly if Ollama isn't reachable or doesn't have the embedding model pulled —
see backend/README or ask for setup steps. Qdrant itself must be running
(docker compose up -d qdrant), which test_deploy_api.py's tests already depend on.
"""

import uuid

import pytest

from app.config import get_settings
from app.indexing.embed import get_embeddings
from app.indexing.qdrant_client import get_client
from app.semantics.schema import Column, Model, Semantics
from app.semantics.store import write_semantics

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def isolate_semantics(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")


@pytest.fixture(autouse=True)
def isolate_qdrant_collection(monkeypatch):
    name = f"test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(get_settings(), "qdrant_collection", name)
    yield name
    qc = get_client()
    if qc.collection_exists(name):
        qc.delete_collection(name)


def test_deploy_and_query_with_real_ollama(isolate_qdrant_collection):
    from fastapi.testclient import TestClient

    from app.main import app

    embeddings = get_embeddings()
    try:
        embeddings.embed_documents(["ping"])
    except ConnectionError as e:
        pytest.skip(f"Ollama not reachable: {e}")

    write_semantics(
        Semantics(
            models=[
                Model(
                    name="orders",
                    description="Customer purchases",
                    columns=[Column(name="order_id", type="INTEGER", description="Unique order identifier")],
                )
            ]
        )
    )

    client = TestClient(app)
    res = client.post("/deploy")
    assert res.status_code == 200
    assert res.json()["points"] == 2  # 1 model + 1 column

    query_vector = embeddings.embed_documents(["What column uniquely identifies an order?"])[0]
    hits = get_client().query_points(
        isolate_qdrant_collection, query=query_vector, limit=1, with_payload=True
    ).points

    assert len(hits) == 1
    assert hits[0].payload["table"] == "orders"
    assert "order_id" in hits[0].payload["text"]
