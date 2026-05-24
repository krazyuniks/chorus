"""Route catalogue for the LLM provider port.

The catalogue is the port's route-metadata layer: it pairs a route id (a
human-named selection like ``dev``, ``demo-eval-canonical``, or
``recorded-replay``) with the provider, model, parameters, and adapter
version that should service it.

Provider catalogue and route-version tables remain governance evidence. The
in-process route catalogue is the call-boundary metadata used by the provider
port.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, cast

from chorus.llm_provider.adapter_openai import OpenAICompatibleAdapter
from chorus.llm_provider.adapter_replay import RecordedReplayAdapter
from chorus.llm_provider.port import (
    InvocationArgs,
    InvocationResult,
    LLMProviderAdapter,
    LLMProviderInvocationError,
)


@dataclass(frozen=True)
class RouteCatalogueEntry:
    """One registered route in the LLM provider port catalogue."""

    route_id: str
    provider_id: str
    model_id: str
    adapter: LLMProviderAdapter
    parameters: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))

    @property
    def adapter_version(self) -> str:
        return self.adapter.adapter_version


class RouteCatalogue:
    """Resolves route ids to their configured adapters."""

    def __init__(self, entries: list[RouteCatalogueEntry]) -> None:
        self._entries: dict[str, RouteCatalogueEntry] = {}
        for entry in entries:
            if entry.route_id in self._entries:
                raise ValueError(f"Duplicate route id in catalogue: {entry.route_id!r}")
            self._entries[entry.route_id] = entry

    @property
    def route_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def get(self, route_id: str) -> RouteCatalogueEntry:
        entry = self._entries.get(route_id)
        if entry is None:
            raise LLMProviderInvocationError(
                route_id=route_id, reason="route_not_registered", retryable=False
            )
        return entry

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        entry = self.get(args.route_id)
        return entry.adapter.invoke(args)


def default_route_catalogue() -> RouteCatalogue:
    """Register the routes required by the LLM provider port.

    The ``dev`` and ``demo-eval-canonical`` routes register
    OpenAI-compatible endpoints (DeepSeek and OpenAI respectively) and read
    credentials from provider-standard environment variables. The
    ``recorded-replay`` route is the deterministic substrate for offline
    eval; it produces stable structured outputs without reaching any
    external provider.
    """

    return RouteCatalogue(
        [
            RouteCatalogueEntry(
                route_id="recorded-replay",
                provider_id="local-replay",
                model_id="recorded-replay-v1",
                adapter=RecordedReplayAdapter(),
                parameters={},
            ),
            RouteCatalogueEntry(
                route_id="dev",
                provider_id="deepseek",
                model_id="deepseek-v4-flash",
                adapter=OpenAICompatibleAdapter(
                    base_url=os.environ.get("CHORUS_LLM_DEV_BASE_URL", "https://api.deepseek.com"),
                    api_key_env="DEEPSEEK_API_KEY",
                ),
                parameters={
                    "reasoning_effort": "high",
                    "extra_body": {"thinking": {"type": "enabled"}},
                },
            ),
            RouteCatalogueEntry(
                route_id="demo-eval-canonical",
                provider_id="openai",
                model_id="gpt-5.4-mini-2026-03-17",
                adapter=OpenAICompatibleAdapter(
                    base_url=os.environ.get(
                        "CHORUS_LLM_CANONICAL_BASE_URL", "https://api.openai.com/v1"
                    ),
                    api_key_env="OPENAI_API_KEY",
                ),
                parameters={"temperature": 0.1},
            ),
        ]
    )
