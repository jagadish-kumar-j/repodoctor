"""Optional AI explanation support for repodoctor."""

from .provider import OllamaProvider, OpenAICompatProvider, Provider, ProviderError

__all__ = [
    "Provider",
    "ProviderError",
    "OllamaProvider",
    "OpenAICompatProvider",
]
