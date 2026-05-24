"""UC1 connector-side sandbox persistence.

The store in this module backs the local broker-firm-side UC1 write
connectors. It is intentionally scoped to the three routing destinations that
receive qualification verdicts: quoting queue, referral inbox, and decline
ledger. Read-only customer profile and product catalogue state are separate R4
work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from chorus.persistence._query import set_tenant_context


@dataclass(frozen=True)
class QuotingQueueRouteWrite:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    connector_invocation_id: UUID
    mode: str
    enquiry_ref: str
    customer_ref: str
    verdict_ref: str
    product_family_category: str
    qualification_summary_ref: str
    routing_policy_ref: str


@dataclass(frozen=True)
class QuotingQueueRouteRecord:
    queued_route_ref: str
    route_status: str


@dataclass(frozen=True)
class ReferralInboxRouteWrite:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    connector_invocation_id: UUID
    mode: str
    enquiry_ref: str
    customer_ref: str
    verdict_ref: str
    referral_destination_category: str
    referral_reason_category: str
    routing_policy_ref: str


@dataclass(frozen=True)
class ReferralInboxRouteRecord:
    referral_route_ref: str
    route_status: str


@dataclass(frozen=True)
class DeclineLedgerRouteWrite:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    connector_invocation_id: UUID
    mode: str
    enquiry_ref: str
    customer_ref: str
    verdict_ref: str
    decline_reason_category: str
    routing_policy_ref: str


@dataclass(frozen=True)
class DeclineLedgerRouteRecord:
    decline_route_ref: str
    route_status: str


class Uc1BrokerFirmRoutingWriter(Protocol):
    def record_quoting_queue_route(
        self,
        command: QuotingQueueRouteWrite,
    ) -> QuotingQueueRouteRecord: ...

    def record_referral_inbox_route(
        self,
        command: ReferralInboxRouteWrite,
    ) -> ReferralInboxRouteRecord: ...

    def record_decline_ledger_route(
        self,
        command: DeclineLedgerRouteWrite,
    ) -> DeclineLedgerRouteRecord: ...


class Uc1BrokerFirmRoutingStore:
    """Postgres-backed local sandbox records for UC1 verdict routing."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def record_quoting_queue_route(
        self,
        command: QuotingQueueRouteWrite,
    ) -> QuotingQueueRouteRecord:
        set_tenant_context(self._conn, command.tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO local_quoting_queue_routes (
                    tenant_id,
                    queued_route_ref,
                    correlation_id,
                    workflow_id,
                    connector_invocation_id,
                    mode,
                    enquiry_ref,
                    customer_ref,
                    verdict_ref,
                    product_family_category,
                    qualification_summary_ref,
                    routing_policy_ref,
                    route_status,
                    metadata
                )
                VALUES (
                    %(tenant_id)s,
                    %(queued_route_ref)s,
                    %(correlation_id)s,
                    %(workflow_id)s,
                    %(connector_invocation_id)s,
                    %(mode)s,
                    %(enquiry_ref)s,
                    %(customer_ref)s,
                    %(verdict_ref)s,
                    %(product_family_category)s,
                    %(qualification_summary_ref)s,
                    %(routing_policy_ref)s,
                    'queued',
                    %(metadata)s
                )
                ON CONFLICT (tenant_id, verdict_ref) DO UPDATE
                SET updated_at = local_quoting_queue_routes.updated_at
                RETURNING queued_route_ref, route_status
                """,
                {
                    "tenant_id": command.tenant_id,
                    "queued_route_ref": _new_ref("qroute"),
                    "correlation_id": command.correlation_id,
                    "workflow_id": command.workflow_id,
                    "connector_invocation_id": command.connector_invocation_id,
                    "mode": command.mode,
                    "enquiry_ref": command.enquiry_ref,
                    "customer_ref": command.customer_ref,
                    "verdict_ref": command.verdict_ref,
                    "product_family_category": command.product_family_category,
                    "qualification_summary_ref": command.qualification_summary_ref,
                    "routing_policy_ref": command.routing_policy_ref,
                    "metadata": Jsonb({}),
                },
            )
            row = cur.fetchone()
        if row is None:
            raise RuntimeError("local quoting queue route insert did not return a row")
        return QuotingQueueRouteRecord(
            queued_route_ref=row["queued_route_ref"],
            route_status=row["route_status"],
        )

    def record_referral_inbox_route(
        self,
        command: ReferralInboxRouteWrite,
    ) -> ReferralInboxRouteRecord:
        set_tenant_context(self._conn, command.tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO local_referral_inbox_routes (
                    tenant_id,
                    referral_route_ref,
                    correlation_id,
                    workflow_id,
                    connector_invocation_id,
                    mode,
                    enquiry_ref,
                    customer_ref,
                    verdict_ref,
                    referral_destination_category,
                    referral_reason_category,
                    routing_policy_ref,
                    route_status,
                    metadata
                )
                VALUES (
                    %(tenant_id)s,
                    %(referral_route_ref)s,
                    %(correlation_id)s,
                    %(workflow_id)s,
                    %(connector_invocation_id)s,
                    %(mode)s,
                    %(enquiry_ref)s,
                    %(customer_ref)s,
                    %(verdict_ref)s,
                    %(referral_destination_category)s,
                    %(referral_reason_category)s,
                    %(routing_policy_ref)s,
                    'routed',
                    %(metadata)s
                )
                ON CONFLICT (tenant_id, verdict_ref) DO UPDATE
                SET updated_at = local_referral_inbox_routes.updated_at
                RETURNING referral_route_ref, route_status
                """,
                {
                    "tenant_id": command.tenant_id,
                    "referral_route_ref": _new_ref("rroute"),
                    "correlation_id": command.correlation_id,
                    "workflow_id": command.workflow_id,
                    "connector_invocation_id": command.connector_invocation_id,
                    "mode": command.mode,
                    "enquiry_ref": command.enquiry_ref,
                    "customer_ref": command.customer_ref,
                    "verdict_ref": command.verdict_ref,
                    "referral_destination_category": command.referral_destination_category,
                    "referral_reason_category": command.referral_reason_category,
                    "routing_policy_ref": command.routing_policy_ref,
                    "metadata": Jsonb({}),
                },
            )
            row = cur.fetchone()
        if row is None:
            raise RuntimeError("local referral inbox route insert did not return a row")
        return ReferralInboxRouteRecord(
            referral_route_ref=row["referral_route_ref"],
            route_status=row["route_status"],
        )

    def record_decline_ledger_route(
        self,
        command: DeclineLedgerRouteWrite,
    ) -> DeclineLedgerRouteRecord:
        set_tenant_context(self._conn, command.tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO local_decline_ledger_routes (
                    tenant_id,
                    decline_route_ref,
                    correlation_id,
                    workflow_id,
                    connector_invocation_id,
                    mode,
                    enquiry_ref,
                    customer_ref,
                    verdict_ref,
                    decline_reason_category,
                    routing_policy_ref,
                    route_status,
                    metadata
                )
                VALUES (
                    %(tenant_id)s,
                    %(decline_route_ref)s,
                    %(correlation_id)s,
                    %(workflow_id)s,
                    %(connector_invocation_id)s,
                    %(mode)s,
                    %(enquiry_ref)s,
                    %(customer_ref)s,
                    %(verdict_ref)s,
                    %(decline_reason_category)s,
                    %(routing_policy_ref)s,
                    'recorded',
                    %(metadata)s
                )
                ON CONFLICT (tenant_id, verdict_ref) DO UPDATE
                SET updated_at = local_decline_ledger_routes.updated_at
                RETURNING decline_route_ref, route_status
                """,
                {
                    "tenant_id": command.tenant_id,
                    "decline_route_ref": _new_ref("droute"),
                    "correlation_id": command.correlation_id,
                    "workflow_id": command.workflow_id,
                    "connector_invocation_id": command.connector_invocation_id,
                    "mode": command.mode,
                    "enquiry_ref": command.enquiry_ref,
                    "customer_ref": command.customer_ref,
                    "verdict_ref": command.verdict_ref,
                    "decline_reason_category": command.decline_reason_category,
                    "routing_policy_ref": command.routing_policy_ref,
                    "metadata": Jsonb({}),
                },
            )
            row = cur.fetchone()
        if row is None:
            raise RuntimeError("local decline ledger route insert did not return a row")
        return DeclineLedgerRouteRecord(
            decline_route_ref=row["decline_route_ref"],
            route_status=row["route_status"],
        )


def _new_ref(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


__all__ = [
    "DeclineLedgerRouteRecord",
    "DeclineLedgerRouteWrite",
    "QuotingQueueRouteRecord",
    "QuotingQueueRouteWrite",
    "ReferralInboxRouteRecord",
    "ReferralInboxRouteWrite",
    "Uc1BrokerFirmRoutingStore",
    "Uc1BrokerFirmRoutingWriter",
]
