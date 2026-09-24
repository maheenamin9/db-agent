import json

import pytest

from app.semantics.describe import DescribeError, _extract_json, generate_descriptions
from app.semantics.schema import Column, Model


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class FakeChatModel:
    """Returns a fixed reply (JSON dict, or raw text) and records the prompt it saw."""

    def __init__(self, response: dict | None = None, raw: str | None = None):
        self.response = response
        self.raw = raw
        self.last_prompt: str | None = None

    def invoke(self, prompt: str) -> FakeMessage:
        self.last_prompt = prompt
        return FakeMessage(self.raw if self.raw is not None else json.dumps(self.response))


class FailingChatModel:
    def invoke(self, prompt: str):
        raise ConnectionError("Failed to connect to Ollama.")


# _extract_json
def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_markdown_fences():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_strips_think_block():
    assert _extract_json('<think>reasoning here</think>{"a": 1}') == {"a": 1}


def test_extract_json_with_surrounding_prose():
    assert _extract_json('Sure, here you go:\n{"a": 1}\nHope that helps!') == {"a": 1}


def test_extract_json_no_json_raises():
    with pytest.raises(DescribeError, match="didn't return JSON"):
        _extract_json("I cannot help with that.")


def test_extract_json_malformed_raises():
    with pytest.raises(DescribeError, match="malformed"):
        _extract_json('{"a": 1,}')


# generate_descriptions
def test_generates_table_and_all_missing_columns():
    model = Model(
        name="orders",
        columns=[Column(name="id", type="BIGINT"), Column(name="status", type="VARCHAR")],
    )
    chat = FakeChatModel(
        {"table": "Customer orders.", "columns": {"id": "The order's id.", "status": "Order status."}}
    )

    result = generate_descriptions(model, chat)

    assert result == {
        "table": "Customer orders.",
        "columns": {"id": "The order's id.", "status": "Order status."},
    }
    assert "orders" in chat.last_prompt
    assert "id (BIGINT)" in chat.last_prompt


def test_skips_columns_that_already_have_a_description():
    model = Model(
        name="orders",
        columns=[
            Column(name="id", type="BIGINT", description="already written"),
            Column(name="status", type="VARCHAR"),
        ],
    )
    chat = FakeChatModel({"table": "Customer orders.", "columns": {"status": "Order status."}})

    result = generate_descriptions(model, chat)

    assert result["columns"] == {"status": "Order status."}
    assert "id" not in result["columns"]
    # the prompt should tell the model id already has a description and not ask again
    assert "status" in chat.last_prompt


def test_skips_table_description_if_already_written():
    model = Model(name="orders", description="already written", columns=[Column(name="id", type="BIGINT")])
    chat = FakeChatModel({"columns": {"id": "The order's id."}})

    result = generate_descriptions(model, chat)

    assert result["table"] is None
    assert result["columns"] == {"id": "The order's id."}


def test_nothing_to_generate_does_not_call_the_model():
    model = Model(
        name="orders",
        description="already written",
        columns=[Column(name="id", type="BIGINT", description="already written")],
    )
    chat = FakeChatModel({})

    result = generate_descriptions(model, chat)

    assert result == {"table": None, "columns": {}}
    assert chat.last_prompt is None  # never called


def test_model_with_no_columns():
    model = Model(name="empty_table")
    chat = FakeChatModel({"table": "An empty table."})

    result = generate_descriptions(model, chat)
    assert result == {"table": "An empty table.", "columns": {}}


def test_missing_table_key_raises():
    model = Model(name="orders")
    chat = FakeChatModel({})  # no "table" key, but one was needed
    with pytest.raises(DescribeError, match="Missing or empty 'table'"):
        generate_descriptions(model, chat)


def test_non_dict_columns_raises():
    model = Model(name="orders", description="already written", columns=[Column(name="id", type="BIGINT")])
    chat = FakeChatModel({"columns": "not an object"})
    with pytest.raises(DescribeError, match="Expected an object"):
        generate_descriptions(model, chat)


def test_a_missing_column_in_the_response_is_just_skipped_not_an_error():
    model = Model(
        name="orders",
        description="already written",
        columns=[Column(name="id", type="BIGINT"), Column(name="status", type="VARCHAR")],
    )
    chat = FakeChatModel({"columns": {"id": "The order's id."}})  # "status" missing from response

    result = generate_descriptions(model, chat)
    assert result["columns"] == {"id": "The order's id."}


def test_connection_error_propagates():
    model = Model(name="orders")
    with pytest.raises(ConnectionError):
        generate_descriptions(model, FailingChatModel())
