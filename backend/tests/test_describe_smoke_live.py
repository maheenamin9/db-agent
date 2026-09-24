"""Real end-to-end proof: ask the actual configured chat model (qwen3:8b, on
whatever OLLAMA_HOST points at) to describe a tiny fixture table, and check the
response is usable. Skips cleanly if that model isn't reachable.
"""

import pytest

from app.semantics.describe import ChatModel, generate_descriptions, get_chat_model
from app.semantics.schema import Column, Model

pytestmark = pytest.mark.integration


def _reachable_chat_model() -> ChatModel:
    chat = get_chat_model()
    try:
        chat.invoke("Reply with exactly: OK")
    except ConnectionError as e:
        pytest.skip(f"Chat model not reachable: {e}")
    return chat


def test_generate_descriptions_with_the_real_model():
    chat = _reachable_chat_model()
    model = Model(
        name="orders",
        columns=[
            Column(name="id", type="BIGINT"),
            Column(name="customer_id", type="BIGINT"),
            Column(name="total_amount", type="DECIMAL(10,2)"),
        ],
    )

    result = generate_descriptions(model, chat)

    assert result["table"] and len(result["table"]) > 0
    assert set(result["columns"]) == {"id", "customer_id", "total_amount"}
    for text in result["columns"].values():
        assert isinstance(text, str) and text.strip()
