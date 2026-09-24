"""Real end-to-end proof: index a tiny fixture through the real pipeline (real
embeddings, real Qdrant), then run the actual agent graph (real retrieval, real
SQL-generation/answer model) and check it produces a correct, sensible answer.

Skips cleanly if Ollama isn't reachable. Slow — each local LLM call observed to
take over a minute during development, and a full run makes at least two.
"""

import uuid

import pandas as pd
import pytest
from qdrant_client import models as qmodels

from app.agent.graph import build_graph
from app.config import get_settings
from app.duckdb_helper import DuckDBHelper
from app.indexing.chunks import build_chunks
from app.indexing.embed import get_embeddings
from app.indexing.qdrant_client import get_client, reset_collection, upsert_points
from app.semantics.schema import Column, Model, Semantics

pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_collection(monkeypatch):
    name = f"test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(get_settings(), "qdrant_collection", name)
    yield name
    qc = get_client()
    if qc.collection_exists(name):
        qc.delete_collection(name)


def test_agent_answers_a_real_question(isolated_collection):
    embeddings = get_embeddings()
    try:
        embeddings.embed_documents(["ping"])
    except ConnectionError as e:
        pytest.skip(f"Ollama not reachable: {e}")

    # A tiny real fixture, indexed through the real Task 10 pipeline.
    semantics = Semantics(
        models=[
            Model(
                name="orders",
                description="Customer orders.",
                columns=[
                    Column(name="id", type="BIGINT", description="Unique order id."),
                    Column(name="amount", type="DOUBLE", description="The order's total amount."),
                ],
            )
        ]
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

    with DuckDBHelper(":memory:") as db:
        db.register_dataframe("orders", pd.DataFrame({"id": [1, 2, 3], "amount": [10.0, 20.0, 30.0]}))

        # embeddings/qdrant/chat all default to real ones; only db is a fixture.
        graph = build_graph(db=db)
        result = graph.invoke({"question": "What is the total amount across all orders?"})

    assert result["error"] is None, f"agent failed: {result.get('answer')}"
    assert len(result["result"]) == 1
    value = next(iter(result["result"][0].values()))
    assert float(value) == 60.0
    assert "60" in result["answer"]
