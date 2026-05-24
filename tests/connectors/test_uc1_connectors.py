from __future__ import annotations

from uuid import UUID

from chorus.connectors import ConnectorContext
from chorus.connectors.uc1 import (
    SandboxDeclineLedgerAdapter,
    SandboxQuotingQueueAdapter,
    SandboxReferralInboxAdapter,
)
from chorus.contracts.generated.connector.uc1.decline_ledger_route_args import (
    DeclineLedgerRouteArgs,
    DeclineReasonCategory,
)
from chorus.contracts.generated.connector.uc1.quoting_queue_route_args import (
    ProductFamilyCategory,
    QuotingQueueRouteArgs,
)
from chorus.contracts.generated.connector.uc1.referral_inbox_route_args import (
    ReferralDestinationCategory,
    ReferralInboxRouteArgs,
    ReferralReasonCategory,
)
from chorus.persistence.uc1_connectors import (
    DeclineLedgerRouteRecord,
    DeclineLedgerRouteWrite,
    QuotingQueueRouteRecord,
    QuotingQueueRouteWrite,
    ReferralInboxRouteRecord,
    ReferralInboxRouteWrite,
)


class _FakeRoutingStore:
    def __init__(self) -> None:
        self.quoting_writes: list[QuotingQueueRouteWrite] = []
        self.referral_writes: list[ReferralInboxRouteWrite] = []
        self.decline_writes: list[DeclineLedgerRouteWrite] = []

    def record_quoting_queue_route(
        self,
        command: QuotingQueueRouteWrite,
    ) -> QuotingQueueRouteRecord:
        self.quoting_writes.append(command)
        return QuotingQueueRouteRecord(
            queued_route_ref="qroute_persisted_accept_001",
            route_status="queued",
        )

    def record_referral_inbox_route(
        self,
        command: ReferralInboxRouteWrite,
    ) -> ReferralInboxRouteRecord:
        self.referral_writes.append(command)
        return ReferralInboxRouteRecord(
            referral_route_ref="rroute_persisted_refer_001",
            route_status="routed",
        )

    def record_decline_ledger_route(
        self,
        command: DeclineLedgerRouteWrite,
    ) -> DeclineLedgerRouteRecord:
        self.decline_writes.append(command)
        return DeclineLedgerRouteRecord(
            decline_route_ref="droute_persisted_decline_001",
            route_status="recorded",
        )


def _context() -> ConnectorContext:
    return ConnectorContext(
        tenant_id="tenant_demo",
        correlation_id="cor_uc1_connector_persistence",
        workflow_id="uc1-enq-connector-persistence",
    )


def test_quoting_queue_adapter_returns_persisted_route_ref() -> None:
    store = _FakeRoutingStore()
    adapter = SandboxQuotingQueueAdapter(store)
    result = adapter.invoke(
        tool_name="crm.route_to_quoting_queue",
        mode="write",
        context=_context(),
        arguments=QuotingQueueRouteArgs(
            enquiry_ref="enq_connector_001",
            customer_ref="cust_connector_001",
            product_family_category=ProductFamilyCategory.MOTOR_PRIVATE_CAR,
            qualification_summary_ref="qsum_connector_001",
            verdict_ref="verdict_connector_accept_001",
            routing_policy_ref="policy_uc1_routing_v1",
        ),
    )

    assert result.output["queued_route_ref"] == "qroute_persisted_accept_001"
    assert result.output["route_status"] == "queued"
    assert len(store.quoting_writes) == 1
    write = store.quoting_writes[0]
    assert write.tenant_id == "tenant_demo"
    assert write.verdict_ref == "verdict_connector_accept_001"
    assert write.product_family_category == "motor_private_car"
    assert write.connector_invocation_id == UUID(str(result.connector_invocation_id))


def test_referral_inbox_adapter_returns_persisted_route_ref() -> None:
    store = _FakeRoutingStore()
    adapter = SandboxReferralInboxAdapter(store)
    result = adapter.invoke(
        tool_name="referral_inbox.route",
        mode="write",
        context=_context(),
        arguments=ReferralInboxRouteArgs(
            enquiry_ref="enq_connector_002",
            customer_ref="cust_connector_002",
            referral_destination_category=ReferralDestinationCategory.SPECIALIST_BROKER_PANEL,
            referral_reason_category=ReferralReasonCategory.COMPLEX_RISK_OUTSIDE_APPETITE,
            verdict_ref="verdict_connector_refer_001",
            routing_policy_ref="policy_uc1_routing_v1",
        ),
    )

    assert result.output["referral_route_ref"] == "rroute_persisted_refer_001"
    assert result.output["route_status"] == "routed"
    assert len(store.referral_writes) == 1
    write = store.referral_writes[0]
    assert write.correlation_id == "cor_uc1_connector_persistence"
    assert write.verdict_ref == "verdict_connector_refer_001"
    assert write.referral_destination_category == "specialist_broker_panel"
    assert write.connector_invocation_id == UUID(str(result.connector_invocation_id))


def test_decline_ledger_adapter_returns_persisted_route_ref() -> None:
    store = _FakeRoutingStore()
    adapter = SandboxDeclineLedgerAdapter(store)
    result = adapter.invoke(
        tool_name="decline_ledger.route",
        mode="write",
        context=_context(),
        arguments=DeclineLedgerRouteArgs(
            enquiry_ref="enq_connector_003",
            customer_ref="cust_connector_003",
            decline_reason_category=DeclineReasonCategory.OUTSIDE_PRODUCT_TARGET_MARKET,
            verdict_ref="verdict_connector_decline_001",
            routing_policy_ref="policy_uc1_routing_v1",
        ),
    )

    assert result.output["decline_route_ref"] == "droute_persisted_decline_001"
    assert result.output["route_status"] == "recorded"
    assert len(store.decline_writes) == 1
    write = store.decline_writes[0]
    assert write.workflow_id == "uc1-enq-connector-persistence"
    assert write.verdict_ref == "verdict_connector_decline_001"
    assert write.decline_reason_category == "outside_product_target_market"
    assert write.connector_invocation_id == UUID(str(result.connector_invocation_id))
