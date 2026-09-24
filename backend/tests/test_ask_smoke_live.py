"""The literal end-to-end proof the task asks for: a real question, against the
real seeded Postgres data (Task 4), through every real step —
retrieve -> generate_sql -> validate -> execute -> answer — via the actual
POST /ask endpoint.

Skips cleanly if Postgres or Ollama isn't reachable. Slow — a single real
generate/answer round trip has been observed to take well over a minute.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from qdrant_client import models as qmodels

from app.agent.graph import build_graph, get_agent_graph
from app.config import get_settings
from app.connectors.postgres import PostgresConnector
from app.duckdb_helper import DuckDBHelper
from app.indexing.chunks import build_chunks
from app.indexing.embed import get_embeddings
from app.indexing.qdrant_client import get_client, reset_collection, upsert_points
from app.main import app
from app.semantics.schema import Column, Model, Relationship, Semantics
from tests.test_sql_connectors_live import postgres_config

pytestmark = pytest.mark.integration

REAL_TABLES = ["customers", "orders", "products", "order_items"]


@pytest.fixture
def isolated_collection(monkeypatch):
    name = f"test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(get_settings(), "qdrant_collection", name)
    yield name
    qc = get_client()
    if qc.collection_exists(name):
        qc.delete_collection(name)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_ask_against_real_seeded_postgres_data(isolated_collection):
    embeddings = get_embeddings()
    try:
        embeddings.embed_documents(["ping"])
    except ConnectionError as e:
        pytest.skip(f"Ollama not reachable: {e}")

    pg = PostgresConnector(postgres_config())
    try:
        pg.list_tables()
    except pg.errors as e:
        pytest.skip(f"Postgres not reachable: {e}")

    with DuckDBHelper(":memory:") as db:
        pg.import_tables(REAL_TABLES, db)

        # Describe the real schema — enough for a simple counting/aggregation
        # question, mirroring what a deployed project would actually have.
        semantics = Semantics(
            models=[
                Model(
                    name="customers",
                    description="People who buy things.",
                    columns=[Column(name=c.name, type=c.type) for c in db.describe("customers")],
                ),
                Model(
                    name="orders",
                    description="Customer orders.",
                    columns=[Column(name=c.name, type=c.type) for c in db.describe("orders")],
                ),
            ],
            relationships=[
                Relationship(
                    from_model="orders", from_column="customer_id", to_model="customers", to_column="id"
                )
            ],
        )
        chunks = build_chunks(semantics)
        vectors = embeddings.embed_documents([c.text for c in chunks])
        client = get_client()
        reset_collection(client, isolated_collection, vector_size=len(vectors[0]))
        upsert_points(
            client,
            isolated_collection,
            [
                qmodels.PointStruct(id=str(uuid.uuid4()), vector=v, payload={**c.payload, "text": c.text})
                for c, v in zip(chunks, vectors)
            ],
        )

        graph = build_graph(db=db)  # real embeddings, real qdrant, real chat model
        app.dependency_overrides[get_agent_graph] = lambda: graph
        test_client = TestClient(app)

        res = test_client.post("/ask", json={"question": "How many customers are there?"})

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["error"] is None, body["answer"]
    assert len(body["rows"]) == 1
    value = next(iter(body["rows"][0].values()))
    assert int(value) == 15  # the real seeded customer count (Task 4)
    assert "15" in body["answer"]
