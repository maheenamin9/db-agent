import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_to_ollama_with_no_key_required():
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "ollama"
    assert settings.groq_api_key is None


def test_groq_provider_without_a_key_fails_fast():
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(_env_file=None, llm_provider="groq")


def test_groq_provider_with_a_key_is_fine():
    settings = Settings(_env_file=None, llm_provider="groq", groq_api_key="gsk_fake")
    assert settings.groq_api_key == "gsk_fake"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="not-a-real-provider")
