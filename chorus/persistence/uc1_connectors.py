"""UC1 connector-side sandbox persistence.

The stores in this module back the local broker-firm-side UC1 connector
adapters. Routing writes persist local sandbox refs for accept, refer, and
decline verdicts. Read-only customer profile and product catalogue adapters
resolve tenant-scoped synthetic records from deterministic local seed data.
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


@dataclass(frozen=True)
class CustomerProfileRecord:
    display_name_category: str
    vulnerability_markers: tuple[str, ...]
    consent_state_category: str


@dataclass(frozen=True)
class ProductCatalogueRecord:
    target_market_summary_category: str
    fair_value_assessment_ref: str
    min_age_category: str | None
    construction_categories: tuple[str, ...]
    excluded_postcode_categories: tuple[str, ...]

    def target_market(self) -> dict[str, Any]:
        target_market: dict[str, Any] = {
            "target_market_summary_category": self.target_market_summary_category,
            "excluded_postcode_categories": list(self.excluded_postcode_categories),
            "fair_value_assessment_ref": self.fair_value_assessment_ref,
        }
        if self.min_age_category is not None:
            target_market["min_age_category"] = self.min_age_category
        if self.construction_categories:
            target_market["construction_categories"] = list(self.construction_categories)
        return target_market


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


class Uc1ConnectorReferenceDataReader(Protocol):
    def lookup_customer_profile(
        self,
        *,
        tenant_id: str,
        customer_ref: str,
    ) -> CustomerProfileRecord | None: ...

    def lookup_product_catalogue(
        self,
        *,
        tenant_id: str,
        product_family_category: str,
    ) -> ProductCatalogueRecord | None: ...


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


class Uc1ConnectorReferenceDataStore:
    """Postgres-backed local synthetic read data for UC1 read connectors."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def lookup_customer_profile(
        self,
        *,
        tenant_id: str,
        customer_ref: str,
    ) -> CustomerProfileRecord | None:
        set_tenant_context(self._conn, tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    display_name_category,
                    vulnerability_markers,
                    consent_state_category
                FROM local_customer_profiles
                WHERE tenant_id = %(tenant_id)s
                  AND customer_ref = %(customer_ref)s
                  AND profile_status = 'active'
                """,
                {
                    "tenant_id": tenant_id,
                    "customer_ref": customer_ref,
                },
            )
            row = cur.fetchone()
        if row is None:
            return None
        return CustomerProfileRecord(
            display_name_category=row["display_name_category"],
            vulnerability_markers=tuple(row["vulnerability_markers"]),
            consent_state_category=row["consent_state_category"],
        )

    def lookup_product_catalogue(
        self,
        *,
        tenant_id: str,
        product_family_category: str,
    ) -> ProductCatalogueRecord | None:
        set_tenant_context(self._conn, tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    target_market_summary_category,
                    fair_value_assessment_ref,
                    min_age_category,
                    construction_categories,
                    excluded_postcode_categories
                FROM local_product_catalogue_entries
                WHERE tenant_id = %(tenant_id)s
                  AND product_family_category = %(product_family_category)s
                  AND catalogue_status = 'active'
                """,
                {
                    "tenant_id": tenant_id,
                    "product_family_category": product_family_category,
                },
            )
            row = cur.fetchone()
        if row is None:
            return None
        return ProductCatalogueRecord(
            target_market_summary_category=row["target_market_summary_category"],
            fair_value_assessment_ref=row["fair_value_assessment_ref"],
            min_age_category=row["min_age_category"],
            construction_categories=tuple(row["construction_categories"]),
            excluded_postcode_categories=tuple(row["excluded_postcode_categories"]),
        )


def _new_ref(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


__all__ = [
    "CustomerProfileRecord",
    "DeclineLedgerRouteRecord",
    "DeclineLedgerRouteWrite",
    "ProductCatalogueRecord",
    "QuotingQueueRouteRecord",
    "QuotingQueueRouteWrite",
    "ReferralInboxRouteRecord",
    "ReferralInboxRouteWrite",
    "Uc1BrokerFirmRoutingStore",
    "Uc1BrokerFirmRoutingWriter",
    "Uc1ConnectorReferenceDataReader",
    "Uc1ConnectorReferenceDataStore",
]
