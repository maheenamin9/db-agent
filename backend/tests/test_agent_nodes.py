import pandas as pd
import pytest

from app.agent import nodes
from app.agent.errors import IndexNotDeployedError
from app.duckdb_helper import DuckDBHelper
from tests.fake_agent_deps import FakeQdrant, SequentialChatModel
from tests.test_deploy_api import FakeEmbeddings
from tests.test_describe import FailingChatModel


# retrieve
def test_retrieve_returns_hit_texts():
    qdrant = FakeQdrant(hits=[{"text": "Table orders: ..."}, {"text": "Table customers: ..."}])
    result = nodes.retrieve({"question": "How many orders?"}, embeddings=FakeEmbeddings(), qdrant=qdrant)
    assert result == {"retrieved_context": ["Table orders: ...", "Table customers: ..."]}


def test_retrieve_raises_when_nothing_deployed():
    qdrant = FakeQdrant(missing=True)
    with pytest.raises(IndexNotDeployedError):
        nodes.retrieve({"question": "How many orders?"}, embeddings=FakeEmbeddings(), qdrant=qdrant)


# generate_sql
def test_generate_sql_extracts_sql_from_reply():
    chat = SequentialChatModel(["```sql\nSELECT 1\n```"])
    result = nodes.generate_sql({"question": "?", "retrieved_context": []}, chat=chat)
    assert result == {"sql": "SELECT 1", "error": None}
    assert "?" in chat.calls[0]


# validate
def test_validate_accepts_select():
    result = nodes.validate({"sql": "SELECT 1"})
    assert result["error"] is None
    assert "LIMIT" in result["sql"]


def test_validate_rejects_forbidden_keyword():
    result = nodes.validate({"sql": "DROP TABLE orders"})
    assert result["error"] is not None
    assert "sql" not in result  # unchanged/untouched on rejection


# execute
@pytest.fixture
def db():
    with DuckDBHelper(":memory:") as helper:
        helper.register_dataframe("orders", pd.DataFrame({"id": [1, 2], "amount": [10.0, 20.0]}))
        yield helper


def test_execute_returns_rows(db):
    result = nodes.execute({"sql": "SELECT sum(amount) AS total FROM orders"}, db=db)
    assert result == {"result": [{"total": 30.0}], "error": None}


def test_execute_captures_db_error(db):
    result = nodes.execute({"sql": "SELECT nonexistent_col FROM orders"}, db=db)
    assert result["error"] is not None
    assert "result" not in result


# repair
def test_repair_bumps_repair_count_and_builds_new_sql():
    chat = SequentialChatModel(["SELECT sum(amount) AS total FROM orders"])
    state = {
        "question": "total?",
        "retrieved_context": [],
        "sql": "SELECT sum(amonut) FROM orders",
        "error": "column amonut not found",
        "repair_count": 0,
    }
    result = nodes.repair(state, chat=chat)

    assert result["sql"] == "SELECT sum(amount) AS total FROM orders"
    assert result["repair_count"] == 1
    assert "column amonut not found" in chat.calls[0]
    assert "SELECT sum(amonut) FROM orders" in chat.calls[0]


def test_repair_defaults_repair_count_to_zero_then_increments():
    chat = SequentialChatModel(["SELECT 1"])
    result = nodes.repair({"question": "?", "sql": "bad", "error": "bad"}, chat=chat)
    assert result["repair_count"] == 1


# answer
def test_answer_summarizes_successful_result():
    chat = SequentialChatModel(["The total is 30."])
    result = nodes.answer(
        {"question": "total?", "result": [{"total": 30.0}], "error": None}, chat=chat
    )
    assert result == {"answer": "The total is 30."}
    assert "30" in chat.calls[0] or "total" in chat.calls[0].lower()


def test_answer_on_failure_does_not_call_the_model():
    chat = FailingChatModel()  # would raise if invoked at all
    result = nodes.answer({"question": "?", "error": "something broke"}, chat=chat)
    assert result == {"answer": "I couldn't answer that question: something broke"}


def test_answer_handles_empty_result():
    chat = SequentialChatModel(["There were no matching results."])
    result = nodes.answer({"question": "?", "result": [], "error": None}, chat=chat)
    assert result["answer"] == "There were no matching results."
    assert "no rows" in chat.calls[0].lower() or "no matching" in chat.calls[0].lower()
