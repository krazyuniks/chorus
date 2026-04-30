"""Local connector substrate for Phase 1A Tool Gateway evidence."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from chorus.contracts.generated.tools.email_message_args import EmailMessageArgs


class ConnectorError(RuntimeError):
    """Raised when a local connector cannot complete an authorised action."""


class ConnectorTransientError(ConnectorError):
    """Raised when a local connector has a retryable fixture-scoped failure."""


class CompanyResearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1, max_length=200)


class CrmLookupCompanyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1, max_length=200)


class CrmCreateLeadArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1, max_length=200)
    contact_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    lead_summary: str = Field(min_length=1, max_length=1000)


@dataclass(frozen=True)
class ConnectorResult:
    connector_invocation_id: UUID
    output: dict[str, Any]


class MailpitEmailConnector:
    """Outbound email connector captured by the local Mailpit SMTP server."""

    def __init__(
        self,
        *,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        sender: str = "lighthouse@chorus.local",
    ) -> None:
        self._smtp_host = smtp_host or os.environ.get("CHORUS_MAILPIT_SMTP_HOST", "localhost")
        self._smtp_port = smtp_port or int(os.environ.get("CHORUS_MAILPIT_SMTP_PORT", "1025"))
        self._sender = sender

    def propose_response(
        self,
        *,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: EmailMessageArgs,
        mode: str,
    ) -> ConnectorResult:
        connector_invocation_id = uuid4()
        if _is_connector_failure_fixture(arguments):
            raise ConnectorTransientError(
                "fixture-scoped transient Mailpit SMTP failure for connector-failure lead"
            )

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = arguments.to
        message["Subject"] = arguments.subject
        message["X-Chorus-Tenant-Id"] = tenant_id
        message["X-Chorus-Correlation-Id"] = correlation_id
        message["X-Chorus-Workflow-Id"] = workflow_id
        message["X-Chorus-Connector-Invocation-Id"] = str(connector_invocation_id)
        message["X-Chorus-Tool-Mode"] = mode
        message.set_content(arguments.body_text)

        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as smtp:
                smtp.send_message(message)
        except OSError as exc:
            raise ConnectorError(
                f"Mailpit SMTP send failed at {self._smtp_host}:{self._smtp_port}: {exc}"
            ) from exc

        return ConnectorResult(
            connector_invocation_id=connector_invocation_id,
            output={
                "connector": "mailpit.smtp",
                "mode": mode,
                "to": arguments.to,
                "subject": arguments.subject,
                "captured_by": "mailpit",
            },
        )


class LocalCrmConnector:
    """Postgres-backed local CRM connector."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def lookup_company(
        self,
        *,
        tenant_id: str,
        arguments: CrmLookupCompanyArguments,
    ) -> ConnectorResult:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT crm_lead_id, company_name, contact_email, lead_summary, status
                FROM local_crm_leads
                WHERE tenant_id = %s AND lower(company_name) = lower(%s)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (tenant_id, arguments.company_name),
            )
            row = cur.fetchone()
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "local_crm.postgres",
                "found": row is not None,
                "lead": _crm_row_to_output(row) if row is not None else None,
            },
        )

    def create_lead(
        self,
        *,
        tenant_id: str,
        correlation_id: str,
        arguments: CrmCreateLeadArguments,
    ) -> ConnectorResult:
        connector_invocation_id = uuid4()
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO local_crm_leads (
                    tenant_id,
                    crm_lead_id,
                    correlation_id,
                    company_name,
                    contact_email,
                    lead_summary,
                    status,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'proposed', %s)
                ON CONFLICT (tenant_id, correlation_id, contact_email) DO UPDATE
                SET
                    company_name = EXCLUDED.company_name,
                    lead_summary = EXCLUDED.lead_summary,
                    updated_at = now()
                RETURNING crm_lead_id, company_name, contact_email, lead_summary, status
                """,
                (
                    tenant_id,
                    connector_invocation_id,
                    correlation_id,
                    arguments.company_name,
                    arguments.contact_email,
                    arguments.lead_summary,
                    Jsonb({"connector_invocation_id": str(connector_invocation_id)}),
                ),
            )
            row = cur.fetchone()
        return ConnectorResult(
            connector_invocation_id=connector_invocation_id,
            output={"connector": "local_crm.postgres", "lead": _crm_row_to_output(row)},
        )


class CompanyResearchConnector:
    """Companies House-backed lookup connector when a local API key is configured."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("CHORUS_COMPANIES_HOUSE_API_KEY")

    def lookup(self, arguments: CompanyResearchArguments) -> ConnectorResult:
        if not self._api_key:
            raise ConnectorError(
                "CHORUS_COMPANIES_HOUSE_API_KEY is not configured for company research"
            )

        try:
            response = httpx.get(
                "https://api.company-information.service.gov.uk/search/companies",
                params={"q": arguments.company_name, "items_per_page": 3},
                auth=(self._api_key, ""),
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Companies House lookup failed: {exc}") from exc
        data = cast(dict[str, Any], response.json())
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []
        typed_items = cast(list[Any], items)
        matches: list[dict[str, Any]] = []
        for raw_item in typed_items:
            if not isinstance(raw_item, dict):
                continue
            item = cast(dict[str, Any], raw_item)
            matches.append(
                {
                    "company_name": item.get("title"),
                    "company_number": item.get("company_number"),
                    "status": item.get("company_status"),
                }
            )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "companies_house.public_api",
                "query": arguments.company_name,
                "matches": matches,
            },
        )


def _is_connector_failure_fixture(arguments: EmailMessageArgs) -> bool:
    marker = "connector-failure fixture"
    return marker in arguments.subject.lower() or marker in arguments.body_text.lower()


def _crm_row_to_output(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "crm_lead_id": str(row["crm_lead_id"]),
        "company_name": row["company_name"],
        "contact_email": row["contact_email"],
        "lead_summary": row["lead_summary"],
        "status": row["status"],
    }
