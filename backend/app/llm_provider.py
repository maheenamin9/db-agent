"""Picks which chat-model backend actually runs a request, based on
`LLM_PROVIDER`. Shared by agent/llm.py (SQL generation/repair/answer) and
semantics/describe.py (description generation) — both need the exact same
switch, so it lives in neither of those modules specifically.

Embeddings always stay on Ollama regardless of `LLM_PROVIDER`: Groq doesn't
offer an embeddings API, and nomic-embed-text isn't something this setting
was ever meant to affect.
"""

from typing import Protocol

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from app.config import get_settings


class ChatMessage(Protocol):
    content: str


class ChatModel(Protocol):
    """What a caller needs — matches ChatOllama, ChatGroq, and any test double."""

    def invoke(self, prompt: str) -> ChatMessage: ...


def build_chat_model(model: str, temperature: float) -> ChatModel:
    settings = get_settings()
    if settings.llm_provider == "groq":
        # Settings' own validator guarantees groq_api_key is set whenever
        # llm_provider is "groq" — enforced at startup, not rediscovered here.
        return ChatGroq(model=model, api_key=settings.groq_api_key, temperature=temperature)
    return ChatOllama(model=model, base_url=settings.ollama_host, temperature=temperature)
