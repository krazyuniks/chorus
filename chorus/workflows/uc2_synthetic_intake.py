"""One-shot UC2 synthetic intake adapter.

The adapter reads the documented UC2 email legal-intake contract sample,
validates it with the generated contract model, normalises it to the workflow
input DTO, derives stable Temporal IDs, and starts the UC2 workflow. It is a
local evidence path, not a generic workflow-start DSL.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from chorus.contracts.generated.intake.uc2.email_legal_intake import EmailLegalIntake
from chorus.observability import set_current_span_attributes
from chorus.workflows.types import Uc2AttachmentSummary, Uc2LegalIntake, Uc2PartyRoleHint
from chorus.workflows.uc2 import (
    UC2_WORKFLOW_TYPE,
    Uc2LegalServicesIntakeConflictCheckWorkflow,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UC2_EMAIL_INTAKE_FIXTURE = (
    _REPO_ROOT / "contracts/intake/uc2/samples/email_legal_intake.sample.json"
)


@dataclass(frozen=True)
class Uc2SyntheticIntakeConfig:
    fixture_path: Path = DEFAULT_UC2_EMAIL_INTAKE_FIXTURE
    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "chorus-uc1"


@dataclass(frozen=True)
class Uc2WorkflowStartRequest:
    workflow_type: str
    workflow_id: str
    intake: Uc2LegalIntake


@dataclass(frozen=True)
class Uc2SyntheticIntakeResult:
    workflow_type: str
    workflow_id: str
    legal_intake_id: str
    legal_intake_ref: str
    correlation_id: str
    started: bool


class Uc2WorkflowStarter(Protocol):
    async def start_uc2(self, intake: Uc2LegalIntake, workflow_id: str) -> bool:
        """Start a UC2 legal-services workflow.

        Returns True when a new workflow was started and False when the
        deterministic workflow ID already exists.
        """
        ...


class TemporalUc2WorkflowStarter:
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
    ) -> TemporalUc2WorkflowStarter:
        client = await Client.connect(target_host, namespace=namespace)
        return cls(client, task_queue)

    async def start_uc2(self, intake: Uc2LegalIntake, workflow_id: str) -> bool:
        set_current_span_attributes(
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            workflow_id=workflow_id,
        )
        try:
            await self._client.start_workflow(
                Uc2LegalServicesIntakeConflictCheckWorkflow.run,
                intake,
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
        except WorkflowAlreadyStartedError:
            return False
        return True


def load_email_legal_intake_fixture(path: Path) -> EmailLegalIntake:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TypeError(f"UC2 intake fixture {path} must contain a JSON object")
    return EmailLegalIntake.model_validate(cast(Mapping[str, Any], raw))


def workflow_start_request_from_email_fixture(path: Path) -> Uc2WorkflowStartRequest:
    return workflow_start_request_from_email_contract(load_email_legal_intake_fixture(path))


def workflow_start_request_from_email_contract(
    contract: EmailLegalIntake,
) -> Uc2WorkflowStartRequest:
    return Uc2WorkflowStartRequest(
        workflow_type=UC2_WORKFLOW_TYPE,
        workflow_id=workflow_id_for_email_message_id(
            tenant_id=contract.tenant_id,
            message_id=contract.message_id,
        ),
        intake=uc2_legal_intake_from_email_contract(contract),
    )


def uc2_legal_intake_from_email_contract(contract: EmailLegalIntake) -> Uc2LegalIntake:
    return Uc2LegalIntake(
        schema_version=contract.schema_version,
        legal_intake_id=str(contract.legal_intake_id),
        tenant_id=contract.tenant_id,
        correlation_id=contract.correlation_id,
        channel=contract.channel,
        adapter_id=contract.adapter_id,
        received_at=contract.received_at.isoformat(),
        source_payload_ref=contract.source_payload_ref,
        legal_intake_ref=legal_intake_ref_for_source_payload(contract.source_payload_ref),
        subject_summary=contract.subject_summary,
        matter_scope_summary=contract.matter_scope_summary,
        party_role_hints=[
            Uc2PartyRoleHint(
                party_ref=hint.party_ref,
                role=hint.role.value,
                party_category=hint.party_category.value,
            )
            for hint in contract.party_role_hints
        ],
        attachments_summary=[
            Uc2AttachmentSummary(
                attachment_ref=attachment.attachment_ref,
                document_category=attachment.document_category.value,
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes,
                sha256=attachment.sha256,
            )
            for attachment in contract.attachments_summary
        ],
        instructing_contact_ref=contract.sender_contact_ref,
        known_party_refs=[hint.party_ref for hint in contract.party_role_hints],
        idempotency_key_ref=idempotency_key_ref_for_email_message_id(contract.message_id),
    )


async def start_uc2_synthetic_intake_once(
    config: Uc2SyntheticIntakeConfig,
    *,
    starter: Uc2WorkflowStarter | None = None,
) -> Uc2SyntheticIntakeResult:
    request = workflow_start_request_from_email_fixture(config.fixture_path)
    workflow_starter: Uc2WorkflowStarter
    if starter is None:
        workflow_starter = await TemporalUc2WorkflowStarter.connect(
            target_host=config.temporal_target_host,
            namespace=config.temporal_namespace,
            task_queue=config.task_queue,
        )
    else:
        workflow_starter = starter

    started = await workflow_starter.start_uc2(request.intake, request.workflow_id)
    return Uc2SyntheticIntakeResult(
        workflow_type=request.workflow_type,
        workflow_id=request.workflow_id,
        legal_intake_id=request.intake.legal_intake_id,
        legal_intake_ref=request.intake.legal_intake_ref,
        correlation_id=request.intake.correlation_id,
        started=started,
    )


def run_start_uc2_synthetic_intake_once(
    config: Uc2SyntheticIntakeConfig,
) -> Uc2SyntheticIntakeResult:
    return asyncio.run(start_uc2_synthetic_intake_once(config))


def workflow_id_for_email_message_id(*, tenant_id: str, message_id: str) -> str:
    return f"uc2-legal-{_digest('workflow', tenant_id, message_id)}"


def idempotency_key_ref_for_email_message_id(message_id: str) -> str:
    return f"msgid_{_digest('idempotency', message_id)}"


def legal_intake_ref_for_source_payload(source_payload_ref: str) -> str:
    return f"legal_intake_{source_payload_ref.removeprefix('source_payload_')}"


def _digest(*parts: str) -> str:
    material = "\x1f".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixture",
        nargs="?",
        default=str(DEFAULT_UC2_EMAIL_INTAKE_FIXTURE),
        help="Path to a UC2 email_legal_intake JSON fixture.",
    )
    parser.add_argument("--temporal-target-host", default="localhost:7233")
    parser.add_argument("--temporal-namespace", default="default")
    parser.add_argument("--task-queue", default="chorus-uc1")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_start_uc2_synthetic_intake_once(
        Uc2SyntheticIntakeConfig(
            fixture_path=Path(args.fixture),
            temporal_target_host=args.temporal_target_host,
            temporal_namespace=args.temporal_namespace,
            task_queue=args.task_queue,
        )
    )
    print(f"workflow_type: {result.workflow_type}")
    print(f"workflow: {result.workflow_id}")
    print(f"legal_intake_ref: {result.legal_intake_ref}")
    print(f"correlation_id: {result.correlation_id}")
    print(f"started: {str(result.started).lower()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
