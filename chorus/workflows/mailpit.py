"""Mailpit HTTP intake parsing and workflow-start dedupe."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid5

import httpx
from httpx._types import QueryParamTypes
from pydantic import TypeAdapter
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from chorus.contracts.generated.events.lead_intake import LeadIntake
from chorus.observability import set_current_span_attributes
from chorus.workflows.lighthouse import LighthouseWorkflow
from chorus.workflows.types import (
    LeadAttachmentSummary,
    LeadSender,
    LighthouseWorkflowInput,
    MailpitPollConfig,
    MailpitPollResult,
)

_RECIPIENT_ADAPTER: TypeAdapter[list[str]] = TypeAdapter(list[str])
_MESSAGE_ID_HEADER = "message-id"
_DATE_HEADER = "date"


class WorkflowStarter(Protocol):
    async def start_lighthouse(self, lead: LighthouseWorkflowInput, workflow_id: str) -> bool:
        """Start a Lighthouse workflow.

        Returns True when a new workflow was started and False when the
        Message-ID-derived workflow already exists.
        """
        ...


class TemporalWorkflowStarter:
    def __init__(self, client: Client, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    @classmethod
    async def connect(
        cls,
        *,
        target_host: str,
        namespace: str,
        task_queue: str,
    ) -> TemporalWorkflowStarter:
        client = await Client.connect(target_host, namespace=namespace)
        return cls(client, task_queue)

    async def start_lighthouse(self, lead: LighthouseWorkflowInput, workflow_id: str) -> bool:
        set_current_span_attributes(
            tenant_id=lead.tenant_id,
            correlation_id=lead.correlation_id,
            workflow_id=workflow_id,
        )
        try:
            await self._client.start_workflow(
                LighthouseWorkflow.run,
                lead,
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
        except WorkflowAlreadyStartedError:
            return False
        return True


class MailpitPoller:
    def __init__(
        self,
        config: MailpitPollConfig,
        starter: WorkflowStarter,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._starter = starter
        self._client = client

    async def poll_once(self) -> MailpitPollResult:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self._config.mailpit_base_url,
            timeout=10.0,
        )
        try:
            return await self._poll_with_client(client)
        finally:
            if owns_client:
                await client.aclose()

    async def _poll_with_client(self, client: httpx.AsyncClient) -> MailpitPollResult:
        listing = await _get_json(
            client,
            "/api/v1/messages",
            params={"limit": self._config.page_size},
        )
        message_refs = _message_refs(listing)
        seen_message_ids: set[str] = set()
        started_workflow_ids: list[str] = []
        duplicate_message_ids: list[str] = []
        ignored_message_ids: list[str] = []
        parsed_message_ids: list[str] = []

        for ref in message_refs:
            detail = await _get_json(client, f"/api/v1/message/{ref}")
            lead = parse_mailpit_message(detail, tenant_id=self._config.tenant_id)
            if lead is None:
                ignored_message_ids.append(ref)
                continue
            lead_recipients = {recipient.lower() for recipient in lead.recipients}
            if self._config.recipient.lower() not in lead_recipients:
                ignored_message_ids.append(lead.message_id)
                continue
            parsed_message_ids.append(lead.message_id)
            if lead.message_id in seen_message_ids:
                duplicate_message_ids.append(lead.message_id)
                continue
            seen_message_ids.add(lead.message_id)

            workflow_id = workflow_id_for_message_id(lead.message_id)
            started = await self._starter.start_lighthouse(lead, workflow_id)
            if started:
                started_workflow_ids.append(workflow_id)
            else:
                duplicate_message_ids.append(lead.message_id)

        return MailpitPollResult(
            started_workflow_ids=started_workflow_ids,
            duplicate_message_ids=duplicate_message_ids,
            ignored_message_ids=ignored_message_ids,
            parsed_message_ids=parsed_message_ids,
        )


async def _get_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: QueryParamTypes | None = None,
) -> Mapping[str, Any]:
    response = await client.get(path, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping):
        raise TypeError(f"Mailpit API returned {type(data).__name__}, expected object")
    return cast(Mapping[str, Any], data)


def _message_refs(listing: Mapping[str, Any]) -> list[str]:
    raw_messages_obj: object = listing.get("messages")
    if not isinstance(raw_messages_obj, Sequence) or isinstance(raw_messages_obj, str):
        return []

    raw_messages = cast(Sequence[object], raw_messages_obj)
    refs: list[str] = []
    for message in raw_messages:
        if not isinstance(message, Mapping):
            continue
        message = cast(Mapping[str, Any], message)
        ref = _first_string(message, "ID", "Id", "id")
        if ref is not None:
            refs.append(ref)
    return refs


def parse_mailpit_message(
    detail: Mapping[str, Any],
    *,
    tenant_id: str,
) -> LighthouseWorkflowInput | None:
    headers = _headers(detail)
    message_id = _first_string(detail, "MessageID", "MessageId", "Message-ID", "message_id")
    if message_id is None:
        message_id = _first_header(headers, _MESSAGE_ID_HEADER)
    if message_id is None:
        return None

    subject = _first_string(detail, "Subject", "subject") or _first_header(headers, "subject")
    body_text = _first_string(detail, "Text", "TextBody", "Body", "body", "text")
    sender_name, sender_email = _sender(detail, headers)
    recipients = _recipients(detail, headers)
    received_at = _received_at(detail, headers)

    if subject is None or body_text is None or sender_email is None or not recipients:
        return None

    lead_id = str(uuid5(NAMESPACE_URL, f"chorus:lighthouse:lead:{tenant_id}:{message_id}"))
    correlation_id = correlation_id_for_message_id(message_id)
    contract = LeadIntake.model_validate(
        {
            "schema_version": "1.0.0",
            "lead_id": lead_id,
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "source": "mailpit_smtp",
            "message_id": message_id,
            "received_at": received_at,
            "sender": {"display_name": sender_name or "", "email": sender_email},
            "recipients": recipients,
            "subject": subject,
            "body_text": body_text,
            "message_headers": headers,
            "attachments_summary": _attachments(detail),
        }
    )
    return lead_input_from_contract(contract)


def lead_input_from_contract(contract: LeadIntake) -> LighthouseWorkflowInput:
    return LighthouseWorkflowInput(
        schema_version=contract.schema_version,
        lead_id=str(contract.lead_id),
        tenant_id=contract.tenant_id,
        correlation_id=contract.correlation_id,
        source=contract.source,
        message_id=contract.message_id,
        received_at=contract.received_at.isoformat(),
        sender=LeadSender(
            display_name=contract.sender.display_name,
            email=contract.sender.email,
        ),
        recipients=_RECIPIENT_ADAPTER.validate_python(
            [recipient.root for recipient in contract.recipients]
        ),
        subject=contract.subject,
        body_text=contract.body_text,
        message_headers={key: list(values) for key, values in contract.message_headers.items()},
        attachments_summary=[
            LeadAttachmentSummary(
                filename=attachment.filename,
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes,
            )
            for attachment in contract.attachments_summary
        ],
    )


def lead_input_to_contract_dict(lead: LighthouseWorkflowInput) -> dict[str, object]:
    payload = asdict(lead)
    payload["sender"] = asdict(lead.sender)
    payload["attachments_summary"] = [asdict(attachment) for attachment in lead.attachments_summary]
    return payload


def workflow_id_for_message_id(message_id: str) -> str:
    digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:24]
    return f"lighthouse-{digest}"


def correlation_id_for_message_id(message_id: str) -> str:
    digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:24]
    return f"cor_{digest}"


def _headers(detail: Mapping[str, Any]) -> dict[str, list[str]]:
    raw_obj: object = detail.get("Headers") or detail.get("headers") or {}
    headers: dict[str, list[str]] = {}
    if isinstance(raw_obj, Mapping):
        raw = cast(Mapping[object, object], raw_obj)
        for key, value in raw.items():
            normalised_key = str(key)
            if isinstance(value, Sequence) and not isinstance(value, str):
                value_sequence = cast(Sequence[object], value)
                headers[normalised_key] = [str(item) for item in value_sequence]
            else:
                headers[normalised_key] = [str(value)]
    return headers


def _first_header(headers: Mapping[str, list[str]], name: str) -> str | None:
    for key, values in headers.items():
        if key.lower() == name.lower() and values:
            return values[0]
    return None


def _first_string(data: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _sender(
    detail: Mapping[str, Any],
    headers: Mapping[str, list[str]],
) -> tuple[str | None, str | None]:
    raw_obj: object = detail.get("From") or detail.get("from")
    if isinstance(raw_obj, Mapping):
        raw_mapping = cast(Mapping[str, Any], raw_obj)
        name = _first_string(raw_mapping, "Name", "name", "DisplayName", "display_name")
        email = _first_string(raw_mapping, "Address", "Email", "address", "email")
        if email is not None:
            return name, email
    if isinstance(raw_obj, str):
        addresses = getaddresses([raw_obj])
        if addresses:
            return addresses[0]

    from_header = _first_header(headers, "from")
    if from_header is not None:
        addresses = getaddresses([from_header])
        if addresses:
            return addresses[0]
    return None, None


def _recipients(detail: Mapping[str, Any], headers: Mapping[str, list[str]]) -> list[str]:
    raw_obj: object = detail.get("To") or detail.get("to") or []
    addresses: list[tuple[str, str]] = []
    if isinstance(raw_obj, str):
        addresses.extend(getaddresses([raw_obj]))
    elif isinstance(raw_obj, Sequence):
        raw_sequence = cast(Sequence[object], raw_obj)
        for item in raw_sequence:
            if isinstance(item, Mapping):
                item = cast(Mapping[str, Any], item)
                email = _first_string(item, "Address", "Email", "address", "email")
                if email is not None:
                    addresses.append(("", email))
            elif isinstance(item, str):
                addresses.extend(getaddresses([item]))

    if not addresses:
        to_header = _first_header(headers, "to")
        if to_header is not None:
            addresses.extend(getaddresses([to_header]))

    return [email for _, email in addresses if email]


def _received_at(detail: Mapping[str, Any], headers: Mapping[str, list[str]]) -> str:
    candidate = _first_string(detail, "Created", "CreatedAt", "Date", "date")
    if candidate is None:
        candidate = _first_header(headers, _DATE_HEADER)
    if candidate is not None:
        try:
            parsed = parsedate_to_datetime(candidate)
        except TypeError, ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat()
    return datetime.now(UTC).isoformat()


def _attachments(detail: Mapping[str, Any]) -> list[dict[str, object]]:
    raw_obj: object = detail.get("Attachments") or detail.get("attachments") or []
    if not isinstance(raw_obj, Sequence) or isinstance(raw_obj, str):
        return []

    raw = cast(Sequence[object], raw_obj)
    attachments: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        item = cast(Mapping[str, Any], item)
        filename = _first_string(item, "FileName", "Filename", "filename", "Name", "name") or ""
        content_type = _first_string(item, "ContentType", "content_type", "MIMEType") or ""
        size = (
            item.get("Size")
            or item.get("SizeBytes")
            or item.get("size")
            or item.get("size_bytes")
            or 0
        )
        if not isinstance(size, int):
            size = 0
        attachments.append(
            {
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size,
            }
        )
    return attachments
