"""LLM provider port: structured invocation surface and route catalogue.

Per ADR 0018 this is the call boundary for every model invocation. Domain
code calls the port with structured arguments and receives a structured
result; no provider SDK is reachable outside this package's adapters.
"""

from __future__ import annotations

from chorus.llm_provider.adapter_openai import OpenAICompatibleAdapter
from chorus.llm_provider.adapter_replay import RecordedReplayAdapter
from chorus.llm_provider.port import (
    InvocationArgs,
    InvocationMessage,
    InvocationResult,
    LLMProviderAdapter,
    LLMProviderInvocationError,
)
from chorus.llm_provider.route_catalogue import (
    RouteCatalogue,
    RouteCatalogueEntry,
    default_route_catalogue,
)

__all__ = [
    "InvocationArgs",
    "InvocationMessage",
    "InvocationResult",
    "LLMProviderAdapter",
    "LLMProviderInvocationError",
    "OpenAICompatibleAdapter",
    "RecordedReplayAdapter",
    "RouteCatalogue",
    "RouteCatalogueEntry",
    "default_route_catalogue",
]
