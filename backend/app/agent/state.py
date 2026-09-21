from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    context: list[str]  # schema/semantic snippets retrieved from Qdrant
    sql: str
    error: str | None
    rows: list[dict[str, Any]]
    retries: int
    answer: str
