"""Postgres-backed local ticket desk connector used behind the Tool Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from chorus.connectors.local import ConnectorError, ConnectorResult
from chorus.contracts.generated.tools.ticket_case_lookup_args import TicketCaseLookupArgs
from chorus.contracts.generated.tools.ticket_case_update_proposal_args import (
    TicketCaseUpdateProposalArgs,
)
from chorus.contracts.generated.tools.ticket_duplicate_case_lookup_args import (
    DuplicateScopeCategory,
    TicketDuplicateCaseLookupArgs,
)


@dataclass(frozen=True)
class _TicketCase:
    case_ref: str
    request_ref: str | None
    account_ref: str
    product_ref: str
    severity_category: str
    status_category: str
    duplicate_group_ref: str | None
    recent_status_refs: list[str]


class LocalTicketDeskConnector:
    """Local-only ticket desk sandbox backed by Postgres safe refs."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def lookup_case(
        self,
        *,
        tenant_id: str,
        arguments: TicketCaseLookupArgs,
    ) -> ConnectorResult:
        case = self._fetch_case(
            tenant_id=tenant_id,
            case_ref=arguments.case_ref,
            account_ref=arguments.account_ref,
            product_ref=arguments.product_ref,
        )
        output_case = None
        if case is not None:
            output_case = _case_output(
                case,
                include_recent_status_refs=(
                    arguments.include_history_category == "bounded_recent_status_refs"
                ),
            )

        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "local_ticket_desk.postgres",
                "lookup_status": "case_found" if case is not None else "case_not_found",
                "case_ref": arguments.case_ref,
                "request_ref": arguments.request_ref,
                "account_ref": arguments.account_ref,
                "product_ref": arguments.product_ref,
                "lookup_policy_ref": arguments.lookup_policy_ref,
                "case": output_case,
            },
        )

    def lookup_duplicates(
        self,
        *,
        tenant_id: str,
        arguments: TicketDuplicateCaseLookupArgs,
    ) -> ConnectorResult:
        duplicate_refs = self._duplicate_case_refs(tenant_id=tenant_id, arguments=arguments)
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "local_ticket_desk.postgres",
                "duplicate_status": (
                    "duplicates_found" if duplicate_refs else "no_duplicates_found"
                ),
                "request_ref": arguments.request_ref,
                "account_ref": arguments.account_ref,
                "product_ref": arguments.product_ref,
                "case_ref": arguments.case_ref,
                "severity_category": arguments.severity_category.value,
                "duplicate_scope_category": arguments.duplicate_scope_category.value,
                "lookup_policy_ref": arguments.lookup_policy_ref,
                "duplicate_case_refs": duplicate_refs,
                "duplicate_count": len(duplicate_refs),
            },
        )

    def propose_case_update(
        self,
        *,
        tenant_id: str,
        arguments: TicketCaseUpdateProposalArgs,
    ) -> ConnectorResult:
        case = self._fetch_case(
            tenant_id=tenant_id,
            case_ref=arguments.case_ref,
            account_ref=arguments.account_ref,
            product_ref=arguments.product_ref,
        )
        if case is None:
            raise ConnectorError("ticket_case_not_found")

        connector_invocation_id = uuid4()
        case_update_ref = arguments.case_update_ref or _case_update_ref(arguments)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO local_ticket_case_update_proposals (
                    tenant_id,
                    case_update_ref,
                    connector_invocation_id,
                    request_ref,
                    case_ref,
                    account_ref,
                    product_ref,
                    severity_category,
                    target_status_category,
                    resolution_plan_ref,
                    response_draft_ref,
                    update_reason_category,
                    policy_ref,
                    proposal_status,
                    metadata
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'proposed', %s
                )
                ON CONFLICT (tenant_id, case_update_ref) DO UPDATE
                SET
                    connector_invocation_id = EXCLUDED.connector_invocation_id,
                    target_status_category = EXCLUDED.target_status_category,
                    resolution_plan_ref = EXCLUDED.resolution_plan_ref,
                    response_draft_ref = EXCLUDED.response_draft_ref,
                    update_reason_category = EXCLUDED.update_reason_category,
                    policy_ref = EXCLUDED.policy_ref,
                    proposal_status = 'proposed',
                    updated_at = now()
                RETURNING case_update_ref, proposal_status
                """,
                (
                    tenant_id,
                    case_update_ref,
                    connector_invocation_id,
                    arguments.request_ref,
                    arguments.case_ref,
                    arguments.account_ref,
                    arguments.product_ref,
                    arguments.severity_category.value,
                    arguments.target_status_category.value,
                    arguments.resolution_plan_ref,
                    arguments.response_draft_ref,
                    arguments.update_reason_category.value,
                    arguments.policy_ref,
                    Jsonb(
                        {
                            "source": "tool_gateway.ticket.propose_case_update",
                            "case_status_mutated": False,
                        }
                    ),
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise ConnectorError("ticket_case_update_proposal_not_recorded")

        return ConnectorResult(
            connector_invocation_id=connector_invocation_id,
            output={
                "connector": "local_ticket_desk.postgres",
                "proposal_status": row["proposal_status"],
                "case_status_mutated": False,
                "request_ref": arguments.request_ref,
                "case_ref": arguments.case_ref,
                "account_ref": arguments.account_ref,
                "product_ref": arguments.product_ref,
                "case_update_ref": row["case_update_ref"],
                "severity_category": arguments.severity_category.value,
                "target_status_category": arguments.target_status_category.value,
                "update_reason_category": arguments.update_reason_category.value,
                "policy_ref": arguments.policy_ref,
            },
        )

    def _fetch_case(
        self,
        *,
        tenant_id: str,
        case_ref: str,
        account_ref: str,
        product_ref: str | None,
    ) -> _TicketCase | None:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    case_ref,
                    request_ref,
                    account_ref,
                    product_ref,
                    severity_category,
                    status_category,
                    duplicate_group_ref,
                    recent_status_refs
                FROM local_ticket_cases
                WHERE tenant_id = %s
                  AND case_ref = %s
                  AND account_ref = %s
                  AND (%s::text IS NULL OR product_ref = %s)
                """,
                (tenant_id, case_ref, account_ref, product_ref, product_ref),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _TicketCase(
            case_ref=row["case_ref"],
            request_ref=row["request_ref"],
            account_ref=row["account_ref"],
            product_ref=row["product_ref"],
            severity_category=row["severity_category"],
            status_category=row["status_category"],
            duplicate_group_ref=row["duplicate_group_ref"],
            recent_status_refs=list(row["recent_status_refs"] or []),
        )

    def _duplicate_case_refs(
        self,
        *,
        tenant_id: str,
        arguments: TicketDuplicateCaseLookupArgs,
    ) -> list[str]:
        account_filter = "account_ref = %(account_ref)s"
        product_filter = "product_ref = %(product_ref)s"
        if (
            arguments.duplicate_scope_category
            == DuplicateScopeCategory.SAME_ACCOUNT_ANY_PRODUCT_OPEN
        ):
            product_filter = "TRUE"
        elif (
            arguments.duplicate_scope_category
            == DuplicateScopeCategory.SAME_PRODUCT_RECENTLY_RESOLVED
        ):
            account_filter = "TRUE"

        query = f"""
            SELECT case_ref
            FROM local_ticket_cases
            WHERE tenant_id = %(tenant_id)s
              AND {account_filter}
              AND {product_filter}
              AND status_category = ANY(%(status_categories)s::text[])
              AND (%(case_ref)s::text IS NULL OR case_ref <> %(case_ref)s)
            ORDER BY updated_at DESC, case_ref
            LIMIT 5
        """
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                query,
                {
                    "tenant_id": tenant_id,
                    "account_ref": arguments.account_ref,
                    "product_ref": arguments.product_ref,
                    "status_categories": [status.value for status in arguments.status_categories],
                    "case_ref": arguments.case_ref,
                },
            )
            return [row["case_ref"] for row in cur.fetchall()]


def _case_output(case: _TicketCase, *, include_recent_status_refs: bool) -> dict[str, Any]:
    return {
        "case_ref": case.case_ref,
        "request_ref": case.request_ref,
        "account_ref": case.account_ref,
        "product_ref": case.product_ref,
        "severity_category": case.severity_category,
        "status_category": case.status_category,
        "duplicate_group_ref": case.duplicate_group_ref,
        "recent_status_refs": case.recent_status_refs if include_recent_status_refs else [],
    }


def _case_update_ref(arguments: TicketCaseUpdateProposalArgs) -> str:
    seed = ":".join(
        [
            arguments.request_ref,
            arguments.case_ref,
            arguments.resolution_plan_ref,
            arguments.response_draft_ref,
            arguments.update_reason_category.value,
        ]
    )
    return f"caseupd_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"
