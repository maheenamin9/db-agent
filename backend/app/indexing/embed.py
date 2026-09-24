from typing import Protocol

from langchain_ollama import OllamaEmbeddings

from app.config import get_settings


class Embeddings(Protocol):
    """What deploy.py actually needs — matches OllamaEmbeddings and any test double."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


def get_embeddings() -> Embeddings:
    settings = get_settings()
    return OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_host)
