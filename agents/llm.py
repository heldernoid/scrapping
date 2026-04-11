"""
LLM client - supports two backends, selected by LLM_BACKEND env var:

  LLM_BACKEND=openrouter  (default)
    Uses OpenRouter at https://openrouter.ai/api/v1
    Requires OPENROUTER_API_KEY
    Model: OPENROUTER_LLM_MODEL (default: mistralai/ministral-14b-2512)

  LLM_BACKEND=ollama
    Uses a local/remote Ollama instance via its OpenAI-compatible endpoint
    Requires OLLAMA_BASE_URL (e.g. http://192.168.0.177:11434/v1)
    Model: OLLAMA_MODEL (default: ministral-3:14b)

Both backends are accessed through the same OpenAI Python SDK; only the
base_url and api_key differ.
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None
_backend: str | None = None


def get_backend() -> str:
    return os.environ.get("LLM_BACKEND", "openrouter").lower()


def get_client() -> OpenAI:
    global _client, _backend
    backend = get_backend()

    # Rebuild client if backend changed
    if _client is None or _backend != backend:
        if backend == "ollama":
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://192.168.0.177:11434/v1")
            # Ollama doesn't validate the key but the SDK requires a non-empty string
            _client = OpenAI(base_url=base_url, api_key="ollama")
        else:
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY not set in environment")
            _client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
        _backend = backend

    return _client


def get_model() -> str:
    backend = get_backend()
    if backend == "ollama":
        return os.environ.get("OLLAMA_MODEL", "ministral-3:14b")
    return os.environ.get("OPENROUTER_LLM_MODEL", "mistralai/ministral-14b-2512")


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 4096) -> str:
    """Send a chat completion request, return the assistant message content."""
    client = get_client()
    model = get_model()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
