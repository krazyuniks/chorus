"""Local/sandbox connector adapters and the connector registry."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg import Connection

from chorus.connectors.calendar import CalendarAdapter
from chorus.connectors.local import (
    LegacyCrmAdapter,
    LegacyResearchAdapter,
    MailpitEmailAdapter,
)
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

    Registers the Lighthouse-era adapters (`MailpitEmailAdapter`,
    `LegacyCrmAdapter`, `LegacyResearchAdapter`) alongside the UC1
    sandbox adapters and the calendar adapter. The Lighthouse-era
    adapters retire in R3 checkpoint E together with the Lighthouse
    workflow; the UC1 adapters become the authoritative set as UC1 wires
    through the new workflow spine.
    """

    registry = ConnectorRegistry()
    for adapter in _default_adapters(conn):
        registry.register(adapter)
    return registry


def _default_adapters(conn: Connection[Any]) -> Sequence[ConnectorAdapter]:
    return (
        MailpitEmailAdapter(),
        LegacyCrmAdapter(conn),
        LegacyResearchAdapter(),
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
    "LegacyCrmAdapter",
    "LegacyResearchAdapter",
    "MailpitEmailAdapter",
    "SandboxCustomerProfileAdapter",
    "SandboxDeclineLedgerAdapter",
    "SandboxOutboundCommsAdapter",
    "SandboxProductCatalogueAdapter",
    "SandboxQuotingQueueAdapter",
    "SandboxReferralInboxAdapter",
    "ToolSpec",
    "default_registry",
]
