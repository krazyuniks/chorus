"""One-shot UC3 synthetic intake adapter.

The adapter reads the documented UC3 email advice-enquiry contract sample,
validates it with the generated contract model, normalises it to the workflow
input DTO, derives stable Temporal IDs, and starts the UC3 workflow. It is a
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

from chorus.contracts.generated.intake.uc3.email_advice_enquiry import EmailAdviceEnquiry
from chorus.observability import set_current_span_attributes
from chorus.workflows.types import Uc3AdviceEnquiry, Uc3AttachmentSummary
from chorus.workflows.uc3 import UC3_WORKFLOW_TYPE, Uc3IfaSuitabilityIntakeWorkflow

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UC3_EMAIL_INTAKE_FIXTURE = (
    _REPO_ROOT / "contracts/intake/uc3/samples/email_advice_enquiry.sample.json"
)


@dataclass(frozen=True)
class Uc3SyntheticIntakeConfig:
    fixture_path: Path = DEFAULT_UC3_EMAIL_INTAKE_FIXTURE
    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "chorus-uc1"


@dataclass(frozen=True)
class Uc3WorkflowStartRequest:
    workflow_type: str
    workflow_id: str
    intake: Uc3AdviceEnquiry


@dataclass(frozen=True)
class Uc3SyntheticIntakeResult:
    workflow_type: str
    workflow_id: str
    advice_enquiry_id: str
    advice_enquiry_ref: str
    correlation_id: str
    started: bool


class Uc3WorkflowStarter(Protocol):
    async def start_uc3(self, intake: Uc3AdviceEnquiry, workflow_id: str) -> bool:
        """Start a UC3 IFA suitability workflow.

        Returns True when a new workflow was started and False when the
        deterministic workflow ID already exists.
        """
        ...


class TemporalUc3WorkflowStarter:
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
    ) -> TemporalUc3WorkflowStarter:
        client = await Client.connect(target_host, namespace=namespace)
        return cls(client, task_queue)

    async def start_uc3(self, intake: Uc3AdviceEnquiry, workflow_id: str) -> bool:
        set_current_span_attributes(
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            workflow_id=workflow_id,
        )
        try:
            await self._client.start_workflow(
                Uc3IfaSuitabilityIntakeWorkflow.run,
                intake,
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
        except WorkflowAlreadyStartedError:
            return False
        return True


def load_email_advice_enquiry_fixture(path: Path) -> EmailAdviceEnquiry:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TypeError(f"UC3 intake fixture {path} must contain a JSON object")
    return EmailAdviceEnquiry.model_validate(cast(Mapping[str, Any], raw))


def workflow_start_request_from_email_fixture(path: Path) -> Uc3WorkflowStartRequest:
    return workflow_start_request_from_email_contract(load_email_advice_enquiry_fixture(path))


def workflow_start_request_from_email_contract(
    contract: EmailAdviceEnquiry,
) -> Uc3WorkflowStartRequest:
    return Uc3WorkflowStartRequest(
        workflow_type=UC3_WORKFLOW_TYPE,
        workflow_id=workflow_id_for_email_message_id(
            tenant_id=contract.tenant_id,
            message_id=contract.message_id,
        ),
        intake=uc3_advice_enquiry_from_email_contract(contract),
    )


def uc3_advice_enquiry_from_email_contract(contract: EmailAdviceEnquiry) -> Uc3AdviceEnquiry:
    return Uc3AdviceEnquiry(
        schema_version=contract.schema_version,
        advice_enquiry_id=str(contract.advice_enquiry_id),
        tenant_id=contract.tenant_id,
        correlation_id=contract.correlation_id,
        channel=contract.channel,
        adapter_id=contract.adapter_id,
        received_at=contract.received_at.isoformat(),
        source_payload_ref=contract.source_payload_ref,
        advice_enquiry_ref=advice_enquiry_ref_for_source_payload(contract.source_payload_ref),
        subject_summary=contract.subject_summary,
        advice_need_summary=contract.advice_need_summary,
        advice_need_categories=[category.value for category in contract.advice_need_categories],
        declared_objective_categories=[
            category.value for category in contract.declared_objective_categories
        ],
        support_need_categories=[category.value for category in contract.support_need_categories],
        attachments_summary=[
            Uc3AttachmentSummary(
                attachment_ref=attachment.attachment_ref,
                document_category=attachment.document_category.value,
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes,
                sha256=attachment.sha256,
            )
            for attachment in contract.attachments_summary
        ],
        prospective_retail_client_ref=contract.prospective_retail_client_ref,
        product_context_categories=[
            category.value for category in (contract.product_context_categories or [])
        ],
        idempotency_key_ref=idempotency_key_ref_for_email_message_id(contract.message_id),
    )


async def start_uc3_synthetic_intake_once(
    config: Uc3SyntheticIntakeConfig,
    *,
    starter: Uc3WorkflowStarter | None = None,
) -> Uc3SyntheticIntakeResult:
    request = workflow_start_request_from_email_fixture(config.fixture_path)
    workflow_starter: Uc3WorkflowStarter
    if starter is None:
        workflow_starter = await TemporalUc3WorkflowStarter.connect(
            target_host=config.temporal_target_host,
            namespace=config.temporal_namespace,
            task_queue=config.task_queue,
        )
    else:
        workflow_starter = starter

    started = await workflow_starter.start_uc3(request.intake, request.workflow_id)
    return Uc3SyntheticIntakeResult(
        workflow_type=request.workflow_type,
        workflow_id=request.workflow_id,
        advice_enquiry_id=request.intake.advice_enquiry_id,
        advice_enquiry_ref=request.intake.advice_enquiry_ref,
        correlation_id=request.intake.correlation_id,
        started=started,
    )


def run_start_uc3_synthetic_intake_once(
    config: Uc3SyntheticIntakeConfig,
) -> Uc3SyntheticIntakeResult:
    return asyncio.run(start_uc3_synthetic_intake_once(config))


def workflow_id_for_email_message_id(*, tenant_id: str, message_id: str) -> str:
    return f"uc3-advice-{_digest('workflow', tenant_id, message_id)}"


def idempotency_key_ref_for_email_message_id(message_id: str) -> str:
    return f"msgid_{_digest('idempotency', message_id)}"


def advice_enquiry_ref_for_source_payload(source_payload_ref: str) -> str:
    return f"advice_enquiry_{source_payload_ref.removeprefix('source_payload_')}"


def _digest(*parts: str) -> str:
    material = "\x1f".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixture",
        nargs="?",
        default=str(DEFAULT_UC3_EMAIL_INTAKE_FIXTURE),
        help="Path to a UC3 email_advice_enquiry JSON fixture.",
    )
    parser.add_argument("--temporal-target-host", default="localhost:7233")
    parser.add_argument("--temporal-namespace", default="default")
    parser.add_argument("--task-queue", default="chorus-uc1")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_start_uc3_synthetic_intake_once(
        Uc3SyntheticIntakeConfig(
            fixture_path=Path(args.fixture),
            temporal_target_host=args.temporal_target_host,
            temporal_namespace=args.temporal_namespace,
            task_queue=args.task_queue,
        )
    )
    print(f"workflow_type: {result.workflow_type}")
    print(f"workflow: {result.workflow_id}")
    print(f"advice_enquiry_ref: {result.advice_enquiry_ref}")
    print(f"correlation_id: {result.correlation_id}")
    print(f"started: {str(result.started).lower()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
