from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    retrieved_context: list[str]  # schema/semantic snippets retrieved from Qdrant
    sql: str
    result: list[dict[str, Any]] | None
    error: str | None
    repair_count: int
    answer: str
