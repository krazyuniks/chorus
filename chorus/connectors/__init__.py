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
from chorus.persistence.uc1_connectors import Uc1BrokerFirmRoutingStore


def default_registry(conn: Connection[Any]) -> ConnectorRegistry:
    """Build the default connector registry for the local sandbox.

    Registers the six UC1 sandbox adapters and the calendar adapter.
    """

    registry = ConnectorRegistry()
    for adapter in _default_adapters(conn):
        registry.register(adapter)
    return registry


def _default_adapters(conn: Connection[Any]) -> Sequence[ConnectorAdapter]:
    uc1_routing_store = Uc1BrokerFirmRoutingStore(conn)
    return (
        CalendarAdapter(),
        SandboxQuotingQueueAdapter(uc1_routing_store),
        SandboxReferralInboxAdapter(uc1_routing_store),
        SandboxDeclineLedgerAdapter(uc1_routing_store),
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
