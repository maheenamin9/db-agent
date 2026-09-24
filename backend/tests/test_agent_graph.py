import pandas as pd
import pytest

from app.agent.errors import IndexNotDeployedError
from app.agent.graph import build_graph
from app.duckdb_helper import DuckDBHelper
from tests.fake_agent_deps import FakeQdrant, SequentialChatModel
from tests.test_deploy_api import FakeEmbeddings

CONTEXT_HITS = [{"text": "Table orders: customer purchases."}, {"text": "Table orders, column amount (DOUBLE)."}]


class PoisonedEmbeddings:
    """Raises if ever called — used to prove the guard truly short-circuits
    before retrieve, not just that the final answer happens to be right."""

    def embed_query(self, text):
        raise AssertionError("embed_query should never be called for a blocked question")

    def embed_documents(self, texts):
        raise AssertionError("embed_documents should never be called for a blocked question")


class PoisonedQdrant:
    def query_points(self, *args, **kwargs):
        raise AssertionError("query_points should never be called for a blocked question")


@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("orders", pd.DataFrame({"id": [1, 2], "amount": [10.0, 20.0]}))
        yield helper


def run(db, chat, qdrant=None):
    graph = build_graph(
        embeddings=FakeEmbeddings(), qdrant=qdrant or FakeQdrant(hits=CONTEXT_HITS), db=db, chat=chat
    )
    return graph.invoke({"question": "What is the total order amount?"})


def test_happy_path_first_sql_succeeds(db):
    chat = SequentialChatModel(["SELECT sum(amount) AS total FROM orders", "The total is $30."])
    result = run(db, chat)

    assert result["error"] is None
    assert result["result"] == [{"total": 30.0}]
    assert result["answer"] == "The total is $30."
    assert result.get("repair_count", 0) == 0
    assert len(chat.calls) == 2  # generate_sql, then answer — no repair needed


def test_invalid_sql_is_repaired_then_succeeds(db):
    """Fails at validate (forbidden keyword), not execute."""
    chat = SequentialChatModel(
        ["DROP TABLE orders", "SELECT sum(amount) AS total FROM orders", "The total is $30."]
    )
    result = run(db, chat)

    assert result["error"] is None
    assert result["repair_count"] == 1
    assert result["answer"] == "The total is $30."
    assert len(chat.calls) == 3


def test_bad_column_is_repaired_then_succeeds(db):
    """Fails at execute (valid SQL shape, but DuckDB rejects the column), not validate."""
    chat = SequentialChatModel(
        ["SELECT sum(nonexistent_col) FROM orders", "SELECT sum(amount) AS total FROM orders", "The total is $30."]
    )
    result = run(db, chat)

    assert result["error"] is None
    assert result["repair_count"] == 1
    assert result["result"] == [{"total": 30.0}]


def test_gives_up_after_max_repairs_without_calling_the_model_again(db):
    """Three consecutive bad columns exhaust the 2 repairs; answer explains the
    failure without a fourth LLM call."""
    chat = SequentialChatModel(
        [
            "SELECT sum(nope1) FROM orders",
            "SELECT sum(nope2) FROM orders",
            "SELECT sum(nope3) FROM orders",
        ]
    )
    result = run(db, chat)

    assert result["repair_count"] == 2
    assert result["error"] is not None
    assert result["answer"].startswith("I couldn't answer that question:")
    assert len(chat.calls) == 3  # generate_sql + 2 repairs, never a 4th call for "answer"


def test_destructive_question_short_circuits_before_any_llm_or_retrieval_call(db):
    chat = SequentialChatModel([])  # would raise (pop from empty list) if ever invoked
    graph = build_graph(embeddings=PoisonedEmbeddings(), qdrant=PoisonedQdrant(), db=db, chat=chat)

    result = graph.invoke({"question": "delete the customer named Amina Khan"})

    assert result["error"] is not None
    assert "only read data" in result["answer"].lower()
    assert result.get("repair_count", 0) == 0
    assert chat.calls == []  # never called
    assert result.get("result") is None
    assert result.get("sql") is None


def test_index_not_deployed_propagates(db):
    with pytest.raises(IndexNotDeployedError):
        run(db, SequentialChatModel([]), qdrant=FakeQdrant(missing=True))


def test_retrieved_context_reaches_the_sql_prompt(db):
    chat = SequentialChatModel(["SELECT sum(amount) AS total FROM orders", "The total is $30."])
    run(db, chat)
    assert "Table orders: customer purchases." in chat.calls[0]
