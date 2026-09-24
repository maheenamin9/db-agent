"""Deploy tests use a fake embedder against a real Qdrant (already running via
docker-compose) — this proves the actual wipe/upsert/query mechanics for real,
without needing Ollama. tests/test_deploy_smoke_live.py is the literal "deploys a
tiny fixture and queries Qdrant back" smoke test using the real embedding model,
skipped automatically when Ollama isn't reachable.
"""

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from qdrant_client import models as qmodels

from app.config import get_settings
from app.indexing.chunks import build_chunks
from app.indexing.embed import get_embeddings
from app.indexing.qdrant_client import get_client, reset_collection, upsert_points
from app.main import app
from app.semantics.schema import Column, Model, Relationship, Semantics
from app.semantics.store import write_semantics


class FakeEmbeddings:
    """Deterministic: same text -> same vector, different text -> a different one.
    Good enough to prove the round trip mechanically; no semantic meaning."""

    def __init__(self, size: int = 8):
        self.size = size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255 for b in digest[: self.size]]


class FailingEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("Failed to connect to Ollama. Please check that Ollama is running.")


SAMPLE = Semantics(
    models=[
        Model(
            name="customers",
            description="People who buy things",
            columns=[Column(name="id", type="BIGINT", description="Primary key")],
        ),
        Model(name="orders", columns=[Column(name="id", type="BIGINT")]),
    ],
    relationships=[
        Relationship(from_model="orders", from_column="customer_id", to_model="customers", to_column="id")
    ],
)


@pytest.fixture(autouse=True)
def isolate_semantics(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "semantics_path", tmp_path / "semantics.yaml")


@pytest.fixture(autouse=True)
def isolate_qdrant_collection(monkeypatch):
    # Never let tests touch the real "semantics" collection.
    name = f"test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(get_settings(), "qdrant_collection", name)
    yield name
    qc = get_client()
    if qc.collection_exists(name):
        qc.delete_collection(name)


@pytest.fixture
def client():
    app.dependency_overrides[get_embeddings] = lambda: FakeEmbeddings()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_deploy_with_nothing_described_is_422(client):
    res = client.post("/deploy")
    assert res.status_code == 422
    assert "Nothing to deploy" in res.json()["detail"]


def test_deploy_indexes_models_columns_and_relationships(client, isolate_qdrant_collection):
    write_semantics(SAMPLE)
    res = client.post("/deploy")

    assert res.status_code == 200
    # 2 models + 2 columns (1 each) + 1 relationship
    assert res.json() == {
        "collection": isolate_qdrant_collection,
        "points": 5,
        "models": 2,
        "columns": 2,
        "relationships": 1,
    }


def test_deploy_creates_a_real_qdrant_collection(client, isolate_qdrant_collection):
    write_semantics(SAMPLE)
    client.post("/deploy")

    qc = get_client()
    assert qc.collection_exists(isolate_qdrant_collection)
    assert qc.count(isolate_qdrant_collection).count == 5


def test_deploy_payload_carries_text_and_metadata_for_retrieval(client, isolate_qdrant_collection):
    write_semantics(SAMPLE)
    client.post("/deploy")

    qc = get_client()
    points, _ = qc.scroll(isolate_qdrant_collection, limit=10, with_payload=True)
    by_kind: dict[str, list[dict]] = {}
    for p in points:
        by_kind.setdefault(p.payload["kind"], []).append(p.payload)

    column_payload = next(p for p in by_kind["column"] if p["column"] == "id" and p["table"] == "customers")
    assert column_payload == {
        "kind": "column",
        "table": "customers",
        "column": "id",
        "type": "BIGINT",
        "text": "Table customers, column id (BIGINT): Primary key.",
    }

    rel_payload = by_kind["relationship"][0]
    assert rel_payload["from_table"] == "orders" and rel_payload["to_table"] == "customers"
    assert "text" in rel_payload


def test_redeploy_wipes_previous_points(client, isolate_qdrant_collection):
    write_semantics(SAMPLE)
    client.post("/deploy")

    write_semantics(Semantics(models=[Model(name="empty_table")]))  # 1 model, no columns/relationships
    res = client.post("/deploy")

    assert res.json()["points"] == 1
    assert get_client().count(isolate_qdrant_collection).count == 1


def test_embedding_connection_error_is_502(client):
    app.dependency_overrides[get_embeddings] = lambda: FailingEmbeddings()
    write_semantics(SAMPLE)

    res = client.post("/deploy")
    assert res.status_code == 502
    assert "ollama" in res.json()["detail"].lower()


def test_search_round_trip_returns_the_matching_chunk(isolate_qdrant_collection):
    """Mechanical proof of embed -> upsert -> search, independent of the API layer."""
    fake = FakeEmbeddings()
    chunks = build_chunks(SAMPLE)
    vectors = fake.embed_documents([c.text for c in chunks])

    settings = get_settings()
    qc = get_client()
    reset_collection(qc, settings.qdrant_collection, vector_size=len(vectors[0]))
    upsert_points(
        qc,
        settings.qdrant_collection,
        [
            qmodels.PointStruct(id=str(uuid.uuid4()), vector=v, payload={**c.payload, "text": c.text})
            for c, v in zip(chunks, vectors)
        ],
    )

    target = next(c for c in chunks if c.kind == "column" and "Primary key" in c.text)
    query_vector = fake.embed_documents([target.text])[0]
    hits = qc.query_points(settings.qdrant_collection, query=query_vector, limit=1).points

    assert hits[0].payload["text"] == target.text
    assert hits[0].payload["table"] == "customers"
