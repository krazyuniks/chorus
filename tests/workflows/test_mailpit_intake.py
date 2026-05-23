from __future__ import annotations

import httpx
import pytest

from chorus.workflows.mailpit import (
    MailpitPoller,
    parse_mailpit_message,
    workflow_id_for_message_id,
)
from chorus.workflows.types import MailpitPollConfig, Uc1EnquiryIntake


class FakeWorkflowStarter:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.started: list[tuple[Uc1EnquiryIntake, str]] = []

    async def start_uc1(self, intake: Uc1EnquiryIntake, workflow_id: str) -> bool:
        if workflow_id in self.existing:
            return False
        self.started.append((intake, workflow_id))
        self.existing.add(workflow_id)
        return True


def _message_detail(
    *,
    message_id: str,
    to: list[dict[str, str]] | None = None,
    subject: str = "Motor cover enquiry: 2018 hatchback, new driver",
) -> dict[str, object]:
    return {
        "ID": message_id.strip("<>").replace("@", "-"),
        "MessageID": message_id,
        "From": {"Name": "Alex Morgan", "Address": "alex.morgan@example.test"},
        "To": to or [{"Address": "enquiries@broker-firm.local"}],
        "Subject": subject,
        "Text": (
            "Hello, I am looking for motor cover for my 2018 hatchback. "
            "I passed my test six months ago and would like a quote on third-party "
            "fire and theft. Postcode SE15."
        ),
        "Headers": {
            "Message-ID": [message_id],
            "Date": ["Wed, 29 Apr 2026 10:00:00 +0000"],
        },
        "Attachments": [
            {"FileName": "brief.txt", "ContentType": "text/plain", "Size": 42},
        ],
    }


def test_parse_mailpit_message_builds_uc1_email_channel_intake() -> None:
    intake = parse_mailpit_message(
        _message_detail(message_id="<enquiry-motor-001@example.test>"),
        tenant_id="tenant_demo",
    )

    assert intake is not None
    assert intake.schema_version == "1.0.0"
    assert intake.tenant_id == "tenant_demo"
    assert intake.correlation_id.startswith("cor_")
    assert intake.from_address.email == "alex.morgan@example.test"
    assert intake.to_recipients == ["enquiries@broker-firm.local"]
    assert intake.attachments_summary[0].filename == "brief.txt"
    assert intake.channel == "email"
    assert intake.adapter_id == "email-channel"
    assert intake.enquiry_ref.startswith("enq_")


@pytest.mark.asyncio
async def test_mailpit_poll_dedupes_by_message_id_and_starts_one_workflow() -> None:
    details = {
        "/api/v1/message/msg-1": _message_detail(message_id="<enquiry-motor-001@example.test>"),
        "/api/v1/message/msg-2": _message_detail(message_id="<enquiry-motor-001@example.test>"),
        "/api/v1/message/msg-3": _message_detail(
            message_id="<enquiry-other-001@example.test>",
            to=[{"Address": "other@broker-firm.local"}],
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

    expected_workflow_id = workflow_id_for_message_id("<enquiry-motor-001@example.test>")
    assert result.started_workflow_ids == [expected_workflow_id]
    assert result.duplicate_message_ids == ["<enquiry-motor-001@example.test>"]
    assert result.ignored_message_ids == ["<enquiry-other-001@example.test>"]
    assert result.parsed_message_ids == [
        "<enquiry-motor-001@example.test>",
        "<enquiry-motor-001@example.test>",
    ]
    assert len(starter.started) == 1
    assert starter.started[0][0].subject == "Motor cover enquiry: 2018 hatchback, new driver"
