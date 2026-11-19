"""AI provider implementations with lazy httpx loading."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from .prompts import SYSTEM_PROMPT


class ProviderError(RuntimeError):
    """Friendly error raised for AI provider failures."""


class Provider(ABC):
    @abstractmethod
    def explain(self, payload: dict) -> str:
        """Return a plain-language explanation of a sanitized payload."""


def _load_httpx():
    try:
        import httpx
    except ImportError:
        raise ProviderError('AI support is not installed. Run: pip install "repodoctor[ai]"')
    return httpx


def get_timeout() -> float:
    """Read REPODOCTOR_TIMEOUT, falling back to 30 for invalid values."""
    raw = os.environ.get("REPODOCTOR_TIMEOUT")
    if raw is not None:
        try:
            value = float(raw)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return 30.0


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict:
    httpx = _load_httpx()
    timeout = get_timeout()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise ProviderError("The AI service returned an error. Check the provider and try again.") from exc
    except httpx.TimeoutException:
        raise ProviderError(f"The AI service timed out after {get_timeout():g} seconds. Try again later.")
    except (httpx.RequestError, httpx.HTTPError, OSError):
        raise ProviderError("The AI service is unreachable. Check its URL and network connection.")


class OllamaProvider(Provider):
    def explain(self, payload: dict) -> str:
        model = os.environ.get("REPODOCTOR_MODEL", "llama3.2")
        data = _post_json(
            "http://localhost:11434/api/chat",
            {"Content-Type": "application/json"},
            {
                "model": model,
                "stream": False,
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _payload_text(payload)},
                ],
            },
        )
        try:
            return data["message"]["content"]
        except (KeyError, TypeError):
            raise ProviderError("The AI service returned a response without an explanation.")


class OpenAICompatProvider(Provider):
    def explain(self, payload: dict) -> str:
        url = os.environ.get("REPODOCTOR_AI_URL")
        if not url:
            raise ProviderError("REPODOCTOR_AI_URL is missing. Set the chat completions URL in your environment.")
        key = os.environ.get("REPODOCTOR_AI_KEY")
        if not key:
            raise ProviderError("REPODOCTOR_AI_KEY is missing. Set your API key in an environment variable.")
        model = os.environ.get("REPODOCTOR_MODEL", "llama3.2")

        data = _post_json(
            url,
            {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _payload_text(payload)},
                ],
            },
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("The AI service returned a response without an explanation.")


def _payload_text(payload: dict) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False)
