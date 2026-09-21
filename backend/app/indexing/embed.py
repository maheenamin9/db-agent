from langchain_ollama import OllamaEmbeddings

from app.config import get_settings


def get_embeddings() -> OllamaEmbeddings:
    settings = get_settings()
    return OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_host)
