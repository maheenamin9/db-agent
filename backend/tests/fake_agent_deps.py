"""Shared fakes for testing the agent graph without real Ollama/Qdrant."""

import httpx
from qdrant_client.http.exceptions import UnexpectedResponse


class FakePoint:
    def __init__(self, payload: dict):
        self.payload = payload


class FakeQueryResponse:
    def __init__(self, points: list[FakePoint]):
        self.points = points


class FakeQdrant:
    """A stand-in for QdrantClient, covering only query_points (what retrieve uses)."""

    def __init__(self, hits: list[dict] | None = None, missing: bool = False):
        self.hits = hits or []
        self.missing = missing  # simulates "nothing has been deployed yet"

    def query_points(self, collection_name, query=None, limit=10, with_payload=True):
        if self.missing:
            raise UnexpectedResponse(404, "Not Found", b"{}", httpx.Headers())
        return FakeQueryResponse([FakePoint(h) for h in self.hits[:limit]])


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class SequentialChatModel:
    """Returns each of `replies` in order, one per .invoke() call. Records every
    prompt it was given, so a test can assert on what the model was actually asked
    (or how many times it was called at all)."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls: list[str] = []

    def invoke(self, prompt: str) -> FakeMessage:
        self.calls.append(prompt)
        return FakeMessage(self._replies.pop(0))
