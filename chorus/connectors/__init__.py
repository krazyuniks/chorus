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
from chorus.connectors.uc2 import (
    SandboxAmlRecordStoreAdapter,
    SandboxConflictCheckAdapter,
    SandboxEngagementLetterStoreAdapter,
    SandboxKycBeneficialOwnershipAdapter,
)
from chorus.connectors.uc3 import (
    SandboxAttitudeToRiskProfilerAdapter,
    SandboxCapacityForLossToolAdapter,
    SandboxPlatformResearchAdapter,
    SandboxSuitabilityReportStoreAdapter,
)
from chorus.persistence.uc1_connectors import (
    Uc1BrokerFirmRoutingStore,
    Uc1ConnectorReferenceDataStore,
)


def default_registry(conn: Connection[Any]) -> ConnectorRegistry:
    """Build the default connector registry for the local sandbox.

    Registers the UC1, UC2, and UC3 sandbox adapters and the calendar adapter.
    """

    registry = ConnectorRegistry()
    for adapter in _default_adapters(conn):
        registry.register(adapter)
    return registry


def _default_adapters(conn: Connection[Any]) -> Sequence[ConnectorAdapter]:
    uc1_routing_store = Uc1BrokerFirmRoutingStore(conn)
    uc1_reference_data = Uc1ConnectorReferenceDataStore(conn)
    return (
        CalendarAdapter(),
        SandboxQuotingQueueAdapter(uc1_routing_store),
        SandboxReferralInboxAdapter(uc1_routing_store),
        SandboxDeclineLedgerAdapter(uc1_routing_store),
        SandboxOutboundCommsAdapter(),
        SandboxCustomerProfileAdapter(uc1_reference_data),
        SandboxProductCatalogueAdapter(uc1_reference_data),
        SandboxConflictCheckAdapter(),
        SandboxKycBeneficialOwnershipAdapter(),
        SandboxAmlRecordStoreAdapter(),
        SandboxEngagementLetterStoreAdapter(),
        SandboxAttitudeToRiskProfilerAdapter(),
        SandboxCapacityForLossToolAdapter(),
        SandboxPlatformResearchAdapter(),
        SandboxSuitabilityReportStoreAdapter(),
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
    "SandboxAmlRecordStoreAdapter",
    "SandboxAttitudeToRiskProfilerAdapter",
    "SandboxCapacityForLossToolAdapter",
    "SandboxConflictCheckAdapter",
    "SandboxCustomerProfileAdapter",
    "SandboxDeclineLedgerAdapter",
    "SandboxEngagementLetterStoreAdapter",
    "SandboxKycBeneficialOwnershipAdapter",
    "SandboxOutboundCommsAdapter",
    "SandboxPlatformResearchAdapter",
    "SandboxProductCatalogueAdapter",
    "SandboxQuotingQueueAdapter",
    "SandboxReferralInboxAdapter",
    "SandboxSuitabilityReportStoreAdapter",
    "ToolSpec",
    "default_registry",
]
