from __future__ import annotations

import httpx
import pytest

from chorus.workflows.mailpit import (
    MailpitPoller,
    parse_mailpit_message,
    workflow_id_for_message_id,
)
from chorus.workflows.types import LighthouseWorkflowInput, MailpitPollConfig


class FakeWorkflowStarter:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.started: list[tuple[LighthouseWorkflowInput, str]] = []

    async def start_lighthouse(self, lead: LighthouseWorkflowInput, workflow_id: str) -> bool:
        if workflow_id in self.existing:
            return False
        self.started.append((lead, workflow_id))
        self.existing.add(workflow_id)
        return True


def _message_detail(
    *,
    message_id: str,
    to: list[dict[str, str]] | None = None,
    subject: str = "Need help choosing a CRM automation partner",
) -> dict[str, object]:
    return {
        "ID": message_id.strip("<>").replace("@", "-"),
        "MessageID": message_id,
        "From": {"Name": "Alex Morgan", "Address": "alex.morgan@example.test"},
        "To": to or [{"Address": "leads@chorus.local"}],
        "Subject": subject,
        "Text": "Hello, we are looking for help qualifying new inbound enquiries.",
        "Headers": {
            "Message-ID": [message_id],
            "Date": ["Wed, 29 Apr 2026 10:00:00 +0000"],
        },
        "Attachments": [
            {"FileName": "brief.txt", "ContentType": "text/plain", "Size": 42},
        ],
    }


def test_parse_mailpit_message_builds_lead_intake_contract_shape() -> None:
    lead = parse_mailpit_message(
        _message_detail(message_id="<lead-acme-001@example.test>"),
        tenant_id="tenant_demo",
    )

    assert lead is not None
    assert lead.schema_version == "1.0.0"
    assert lead.tenant_id == "tenant_demo"
    assert lead.correlation_id.startswith("cor_")
    assert lead.sender.email == "alex.morgan@example.test"
    assert lead.recipients == ["leads@chorus.local"]
    assert lead.attachments_summary[0].filename == "brief.txt"


@pytest.mark.asyncio
async def test_mailpit_poll_dedupes_by_message_id_and_starts_one_workflow() -> None:
    details = {
        "/api/v1/message/msg-1": _message_detail(message_id="<lead-acme-001@example.test>"),
        "/api/v1/message/msg-2": _message_detail(message_id="<lead-acme-001@example.test>"),
        "/api/v1/message/msg-3": _message_detail(
            message_id="<lead-other-001@example.test>",
            to=[{"Address": "other@chorus.local"}],
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/messages":
            return httpx.Response(
                200,
                json={"messages": [{"ID": "msg-1"}, {"ID": "msg-2"}, {"ID": "msg-3"}]},
            )
        return httpx.Response(200, json=details[request.url.path])

    starter = FakeWorkflowStarter()
    async with httpx.AsyncClient(
        base_url="http://mailpit.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await MailpitPoller(
            MailpitPollConfig(mailpit_base_url="http://mailpit.test"),
            starter,
            client=client,
        ).poll_once()

    expected_workflow_id = workflow_id_for_message_id("<lead-acme-001@example.test>")
    assert result.started_workflow_ids == [expected_workflow_id]
    assert result.duplicate_message_ids == ["<lead-acme-001@example.test>"]
    assert result.ignored_message_ids == ["<lead-other-001@example.test>"]
    assert result.parsed_message_ids == [
        "<lead-acme-001@example.test>",
        "<lead-acme-001@example.test>",
    ]
    assert len(starter.started) == 1
    assert starter.started[0][0].subject == "Need help choosing a CRM automation partner"
