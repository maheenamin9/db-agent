from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from app.config import get_settings
from app.llm_provider import build_chat_model


def test_defaults_to_ollama(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "ollama")
    monkeypatch.setattr(get_settings(), "ollama_host", "http://example:11434")

    model = build_chat_model("qwen3:30b", temperature=0.1)

    assert isinstance(model, ChatOllama)
    assert model.model == "qwen3:30b"
    assert model.base_url == "http://example:11434"
    assert model.temperature == 0.1


def test_switches_to_groq_when_selected(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "groq")
    monkeypatch.setattr(get_settings(), "groq_api_key", "gsk_fake")

    model = build_chat_model("llama-3.3-70b-versatile", temperature=0.3)

    assert isinstance(model, ChatGroq)
    assert model.model_name == "llama-3.3-70b-versatile"
    assert model.temperature == 0.3
    assert model.groq_api_key.get_secret_value() == "gsk_fake"


def test_groq_never_used_when_provider_is_ollama(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "ollama")
    model = build_chat_model("qwen3:8b", temperature=0.3)
    assert not isinstance(model, ChatGroq)
