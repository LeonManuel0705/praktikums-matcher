from ..config import FORCED_PROVIDER
from .anthropic_api import AnthropicApiProvider
from .claude_cli import ClaudeCliProvider
from .corpus import CorpusProvider
from .tavily import TavilyProvider

PROVIDERS = [AnthropicApiProvider(), ClaudeCliProvider(), TavilyProvider(), CorpusProvider()]
BY_NAME = {provider.name: provider for provider in PROVIDERS}


def pick_provider(preferred: str | None = None):
    wanted = preferred or FORCED_PROVIDER
    if wanted:
        provider = BY_NAME.get(wanted)
        if provider and provider.available():
            return provider
    for provider in PROVIDERS:
        if provider.available():
            return provider
    return None


def provider_status() -> list[dict]:
    return [
        {"name": p.name, "label": p.label, "available": p.available(), "live": p.name != "corpus"}
        for p in PROVIDERS
    ]
