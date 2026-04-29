from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest

from chorus.connectors.local import MailpitEmailConnector
from chorus.contracts.generated.tools.email_message_args import EmailMessageArgs

MAILPIT_HTTP_URL = os.environ.get("CHORUS_TEST_MAILPIT_HTTP_URL", "http://localhost:8025")
MAILPIT_SMTP_HOST = os.environ.get("CHORUS_TEST_MAILPIT_SMTP_HOST", "localhost")
MAILPIT_SMTP_PORT = int(os.environ.get("CHORUS_TEST_MAILPIT_SMTP_PORT", "1025"))


def test_mailpit_email_connector_captures_outbound_proposal() -> None:
    if not _mailpit_available():
        pytest.skip("Mailpit is not available for outbound connector evidence")

    recipient = f"lead-{uuid4().hex}@example.com"
    subject = f"Chorus outbound connector evidence {uuid4().hex}"

    result = MailpitEmailConnector(
        smtp_host=MAILPIT_SMTP_HOST,
        smtp_port=MAILPIT_SMTP_PORT,
    ).propose_response(
        tenant_id="tenant_demo",
        correlation_id=f"cor_mailpit_connector_{uuid4().hex}",
        workflow_id=f"lighthouse-mailpit-{uuid4().hex}",
        arguments=EmailMessageArgs.model_validate(
            {
                "to": recipient,
                "subject": subject,
                "body_text": "Captured proposal body from the local Tool Gateway connector.",
            }
        ),
        mode="propose",
    )

    assert result.output["captured_by"] == "mailpit"
    assert _mailpit_contains(recipient=recipient, subject=subject)


def _mailpit_available() -> bool:
    try:
        response = httpx.get(f"{MAILPIT_HTTP_URL}/api/v1/messages", timeout=2)
        response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True


def _mailpit_contains(*, recipient: str, subject: str) -> bool:
    response = httpx.get(f"{MAILPIT_HTTP_URL}/api/v1/messages", timeout=5)
    response.raise_for_status()
    listing = cast(Mapping[str, Any], response.json())
    raw_messages = listing.get("messages", [])
    if not isinstance(raw_messages, Sequence) or isinstance(raw_messages, str):
        return False
    messages = cast(Sequence[object], raw_messages)

    for raw_message in messages:
        if not isinstance(raw_message, Mapping):
            continue
        message = cast(Mapping[str, Any], raw_message)
        if message.get("Subject") != subject:
            continue
        if _message_has_recipient(message, recipient):
            return True
    return False


def _message_has_recipient(message: Mapping[str, Any], recipient: str) -> bool:
    for key in ("To", "to"):
        raw_to = message.get(key)
        if isinstance(raw_to, Sequence) and not isinstance(raw_to, str):
            recipients = cast(Sequence[object], raw_to)
            for item in recipients:
                if isinstance(item, Mapping):
                    recipient_obj = cast(Mapping[str, Any], item)
                    if recipient_obj.get("Address") == recipient:
                        return True
                if isinstance(item, str) and recipient in item:
                    return True
    return False
