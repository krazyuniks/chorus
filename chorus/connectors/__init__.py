"""Sandbox connector adapters and the connector registry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg import Connection

from chorus.connectors.calendar import CalendarAdapter
from chorus.connectors.types import (
    ConnectorAdapter,
    ConnectorContext,
    ConnectorError,
    ConnectorRegistry,
    ConnectorRegistryError,
    ConnectorResult,
    ConnectorTransientError,
    ToolSpec,
)
from chorus.connectors.uc1 import (
    SandboxCustomerProfileAdapter,
    SandboxDeclineLedgerAdapter,
    SandboxOutboundCommsAdapter,
    SandboxProductCatalogueAdapter,
    SandboxQuotingQueueAdapter,
    SandboxReferralInboxAdapter,
)


def default_registry(conn: Connection[Any]) -> ConnectorRegistry:
    """Build the default connector registry for the local sandbox.

    Registers the six UC1 sandbox adapters and the calendar adapter.
    """

    del conn  # broker-firm-side persistence wiring is R4 work
    registry = ConnectorRegistry()
    for adapter in _default_adapters():
        registry.register(adapter)
    return registry


def _default_adapters() -> Sequence[ConnectorAdapter]:
    return (
        CalendarAdapter(),
        SandboxQuotingQueueAdapter(),
        SandboxReferralInboxAdapter(),
        SandboxDeclineLedgerAdapter(),
        SandboxOutboundCommsAdapter(),
        SandboxCustomerProfileAdapter(),
        SandboxProductCatalogueAdapter(),
    )


__all__ = [
    "CalendarAdapter",
    "ConnectorAdapter",
    "ConnectorContext",
    "ConnectorError",
    "ConnectorRegistry",
    "ConnectorRegistryError",
    "ConnectorResult",
    "ConnectorTransientError",
    "SandboxCustomerProfileAdapter",
    "SandboxDeclineLedgerAdapter",
    "SandboxOutboundCommsAdapter",
    "SandboxProductCatalogueAdapter",
    "SandboxQuotingQueueAdapter",
    "SandboxReferralInboxAdapter",
    "ToolSpec",
    "default_registry",
]
