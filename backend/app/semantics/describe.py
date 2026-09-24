"""Generate short, plain-English descriptions for a model and its columns with an
LLM. Only ever proposes text for fields that are currently empty — never
overwrites something a person already wrote — and never writes to semantics.yaml
itself; the caller decides what to keep.
"""

import json
import re
from typing import Protocol

from langchain_ollama import ChatOllama

from app.config import get_settings
from app.semantics.schema import Model


class DescribeError(ValueError):
    """The model's response couldn't be used (bad JSON, missing fields, etc.)."""


class ChatMessage(Protocol):
    content: str


class ChatModel(Protocol):
    """What this module needs — matches ChatOllama and any test double."""

    def invoke(self, prompt: str) -> ChatMessage: ...


def get_chat_model() -> ChatModel:
    settings = get_settings()
    return ChatOllama(model=settings.describe_model, base_url=settings.ollama_host, temperature=0.3)


def _build_prompt(model: Model, column_names: list[str]) -> str:
    all_columns = "\n".join(f"- {c.name} ({c.type})" for c in model.columns)
    needs = "\n".join(f"- {name}" for name in column_names)
    parts = [
        "You are documenting a database schema for someone unfamiliar with it. "
        "Write ONE short, plain-English sentence for each item asked for below. "
        "Be concise and factual — describe what the name and type most plausibly "
        "mean; don't invent specifics you can't know from the name alone.",
        f"\nTable: {model.name}",
        f"All columns (for context):\n{all_columns}" if all_columns else "This table has no columns.",
    ]
    needs_table = not model.description
    if needs_table:
        parts.append("\nWrite a one-sentence description of the table itself.")
    if column_names:
        parts.append(f"\nWrite a one-sentence description for each of these columns:\n{needs}")

    shape = {}
    if needs_table:
        shape["table"] = "<one sentence>"
    if column_names:
        shape["columns"] = {name: "<one sentence>" for name in column_names}
    parts.append(
        "\nRespond with ONLY a JSON object of this exact shape, no markdown fences, "
        f"no other text:\n{json.dumps(shape)}"
    )
    return "\n".join(parts)


def _extract_json(text: str) -> dict:
    # Strip a <think>...</think> block some models emit, and any ```json fences.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise DescribeError(f"The model didn't return JSON: {text[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise DescribeError(f"The model's JSON was malformed: {e}") from e


def generate_descriptions(model: Model, chat: ChatModel) -> dict:
    """Returns {"table": str | None, "columns": {name: str}} — only for fields that
    were empty. `table` is None when the model already had a description."""
    missing_columns = [c.name for c in model.columns if not c.description]
    if model.description and not missing_columns:
        return {"table": None, "columns": {}}

    prompt = _build_prompt(model, missing_columns)
    reply = chat.invoke(prompt).content
    data = _extract_json(reply)

    result: dict = {"table": None, "columns": {}}
    if not model.description:
        table_text = data.get("table")
        if not isinstance(table_text, str) or not table_text.strip():
            raise DescribeError(f"Missing or empty 'table' in the model's response: {data!r}")
        result["table"] = table_text.strip()

    columns = data.get("columns", {})
    if missing_columns and not isinstance(columns, dict):
        raise DescribeError(f"Expected an object for 'columns', got: {columns!r}")
    for name in missing_columns:
        text = columns.get(name)
        if isinstance(text, str) and text.strip():
            result["columns"][name] = text.strip()

    return result
