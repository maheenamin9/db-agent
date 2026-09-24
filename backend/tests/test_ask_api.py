import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.agent.graph import build_graph, get_agent_graph
from app.duckdb_helper import DuckDBHelper
from app.main import app
from tests.fake_agent_deps import FakeQdrant, SequentialChatModel
from tests.test_deploy_api import FakeEmbeddings

CONTEXT_HITS = [{"text": "Table orders, column amount (DOUBLE)."}]


class FailingEmbeddings:
    def embed_documents(self, texts):
        raise ConnectionError("Failed to connect to Ollama.")

    def embed_query(self, text):
        raise ConnectionError("Failed to connect to Ollama.")


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("orders", pd.DataFrame({"id": [1, 2], "amount": [10.0, 20.0]}))
        yield helper


def client_with(db, chat, embeddings=None, qdrant=None):
    graph = build_graph(
        embeddings=embeddings or FakeEmbeddings(), qdrant=qdrant or FakeQdrant(hits=CONTEXT_HITS), db=db, chat=chat
    )
    app.dependency_overrides[get_agent_graph] = lambda: graph
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_ask_happy_path(db):
    chat = SequentialChatModel(["SELECT sum(amount) AS total FROM orders", "The total is $30."])
    client = client_with(db, chat)

    res = client.post("/ask", json={"question": "What is the total order amount?"})

    assert res.status_code == 200
    assert res.json() == {
        "answer": "The total is $30.",
        # sqlglot regenerates SQL from the parsed AST, uppercasing function names;
        # settings.row_limit (1000) is used, not validate_sql's own default of 500
        "sql": "SELECT SUM(amount) AS total FROM orders LIMIT 1000",
        "rows": [{"total": 30.0}],
        "row_count": 1,
        "error": None,
    }


def test_ask_repairs_then_succeeds(db):
    chat = SequentialChatModel(
        ["SELECT sum(nope) FROM orders", "SELECT sum(amount) AS total FROM orders", "The total is $30."]
    )
    client = client_with(db, chat)

    res = client.post("/ask", json={"question": "total?"})

    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert body["answer"] == "The total is $30."


def test_ask_gives_up_is_still_a_200(db):
    """A repair-exhausted question is not a server error — the agent tried and
    honestly reports it, with a normal 200."""
    chat = SequentialChatModel(["SELECT sum(nope1) FROM orders", "SELECT sum(nope2) FROM orders", "SELECT sum(nope3) FROM orders"])
    client = client_with(db, chat)

    res = client.post("/ask", json={"question": "total?"})

    assert res.status_code == 200
    body = res.json()
    assert body["rows"] == []
    assert body["row_count"] == 0
    assert body["error"] is not None
    assert body["answer"].startswith("I couldn't answer that question:")


def test_ask_index_not_deployed_is_422(db):
    client = client_with(db, SequentialChatModel([]), qdrant=FakeQdrant(missing=True))

    res = client.post("/ask", json={"question": "total?"})

    assert res.status_code == 422
    assert "deploy" in res.json()["detail"].lower()


def test_ask_unreachable_embeddings_is_502(db):
    client = client_with(db, SequentialChatModel([]), embeddings=FailingEmbeddings())

    res = client.post("/ask", json={"question": "total?"})

    assert res.status_code == 502


def test_ask_empty_question_is_422(db):
    client = client_with(db, SequentialChatModel([]))
    res = client.post("/ask", json={"question": ""})
    assert res.status_code == 422
