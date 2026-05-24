"""Shared workflow spine and `WorkflowDefinition` primitives.

The spine carries the orchestration work that every use-case workflow shares -
event emission with sequence + path tracking, agent-step calls, connector-step
calls, approval-gate hand-off, escalation, bounded retry, retry-exhaustion DLQ
evidence, and tool-failure compensation. The control flow of each use case
stays as readable Python over the spine primitives; the step taxonomy lives
as typed `WorkflowDefinition` data.

The spine is designed against the UC1 / UC2 / UC3 deltas catalogued in
`docs/r1-adapter-mapping.md`. UC1 lands first; UC2 and UC3 reuse the same
primitives with different `WorkflowDefinition`s, different agent/connector
specs, and different approval policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    RetryExhaustionDlqCommand,
    RetryExhaustionDlqResult,
    ToolFailureCompensationCommand,
    ToolFailureCompensationResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowCorrelation,
    WorkflowEventCommand,
)

ACTIVITY_RECORD_WORKFLOW_EVENT = "chorus.record_workflow_event"
ACTIVITY_INVOKE_AGENT_RUNTIME = "chorus.invoke_agent_runtime"
ACTIVITY_INVOKE_TOOL_GATEWAY = "chorus.invoke_tool_gateway"
ACTIVITY_RECORD_TOOL_FAILURE_COMPENSATION = "chorus.record_tool_failure_compensation"
ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ = "chorus.record_retry_exhaustion_dlq"

EVENT_ENQUIRY_RECEIVED = "enquiry.received"
EVENT_WORKFLOW_STARTED = "workflow.started"
EVENT_STEP_STARTED = "workflow.step.started"
EVENT_STEP_COMPLETED = "workflow.step.completed"
EVENT_WORKFLOW_COMPLETED = "workflow.completed"
EVENT_WORKFLOW_ESCALATED = "workflow.escalated"
EVENT_WORKFLOW_FAILED = "workflow.failed"

STEP_ESCALATE = "escalate"

DEFAULT_ACTIVITY_TIMEOUT = timedelta(seconds=30)
DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=3)


class WorkflowStepKind(StrEnum):
    """Kinds the spine recognises for a `WorkflowStepDefinition`.

    The kind drives which spec the spine expects on the step and which
    primitive the use-case workflow calls.
    """

    INTAKE = "intake"
    AGENT = "agent"
    CONNECTOR = "connector"
    APPROVAL_GATE = "approval_gate"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class AgentSpec:
    """Declarative inputs the spine needs to invoke an agent step."""

    agent_role: str
    task_kind: str
    expected_output_contract: str


@dataclass(frozen=True)
class ConnectorSpec:
    """Declarative inputs the spine needs to invoke a connector step."""

    agent_id: str
    tool_name: str
    mode: str


@dataclass(frozen=True)
class ApprovalPolicy:
    """Approval-gate parameters: the connector mode that triggers the gate.

    For UC1 the missing-data-request send is the only synchronous gate; UC2
    adds engagement-letter send and conflict acceptance; UC3 adds suitability
    statement send, attitude-to-risk classification override, and
    vulnerability-marker handoff. The spine carries the shape; each use case
    declares which gates apply.
    """

    agent_id: str
    tool_name: str
    requested_mode: str = "write"


@dataclass(frozen=True)
class WorkflowStepDefinition:
    """One step in a use-case workflow definition.

    `kind` selects which spec is required. Steps of kind `agent` carry
    `agent_spec`; kind `connector` carries `connector_spec`; kind
    `approval_gate` carries `approval_policy`; kinds `intake` and `terminal`
    carry just a step name.
    """

    step_name: str
    kind: WorkflowStepKind
    agent_spec: AgentSpec | None = None
    connector_spec: ConnectorSpec | None = None
    approval_policy: ApprovalPolicy | None = None


@dataclass(frozen=True)
class WorkflowDefinition:
    """Typed sequence of step definitions for one use-case workflow.

    Each use case ships one of these. The spine does not enforce the order of
    execution; the use-case workflow walks the definition in domain-shaped
    Python.
    """

    workflow_type: str
    steps: tuple[WorkflowStepDefinition, ...]


class ActivityRetryExhaustedError(Exception):
    """Raised by spine primitives when the retry policy gives up on an activity.

    The use-case workflow catches this to record DLQ evidence and escalate.
    """

    def __init__(self, *, failed_step: str, failed_activity: str, source: ActivityError) -> None:
        self.failed_step = failed_step
        self.failed_activity = failed_activity
        self.source = source
        super().__init__(_activity_failure_reason(source))


class WorkflowSpine:
    """Orchestration primitives shared by every use-case workflow.

    One instance is created per workflow run. It carries the per-run sequence
    counter and the step path; both are exposed for the use-case workflow to
    embed into outcome records.
    """

    def __init__(self, correlation: WorkflowCorrelation) -> None:
        self._correlation = correlation
        self._sequence = 1
        self._path: list[str] = []

    @property
    def correlation(self) -> WorkflowCorrelation:
        return self._correlation

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def path(self) -> list[str]:
        return list(self._path)

    async def emit(
        self,
        event_type: str,
        step: str | None,
        payload: dict[str, Any],
    ) -> None:
        await workflow.execute_activity(
            ACTIVITY_RECORD_WORKFLOW_EVENT,
            WorkflowEventCommand(
                tenant_id=self._correlation.tenant_id,
                correlation_id=self._correlation.correlation_id,
                workflow_id=self._correlation.workflow_id,
                workflow_type=self._correlation.workflow_type,
                subject_id=self._correlation.subject_id,
                subject_ref=self._correlation.subject_ref,
                sequence=self._sequence,
                event_type=event_type,
                step=step,
                payload=payload,
            ),
            start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_RETRY_POLICY,
        )
        self._sequence += 1

    async def step(
        self,
        step_name: str,
        completion_payload: dict[str, Any],
        *,
        started_payload: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            EVENT_STEP_STARTED,
            step_name,
            started_payload or {"step_name": step_name},
        )
        self._path.append(step_name)
        await self.emit(EVENT_STEP_COMPLETED, step_name, completion_payload)

    async def agent_call(
        self,
        step: WorkflowStepDefinition,
        input_payload: dict[str, Any],
    ) -> AgentInvocationResponse:
        if step.agent_spec is None:
            raise ValueError(
                f"WorkflowStepDefinition {step.step_name!r} declared kind=agent without agent_spec"
            )
        try:
            return await workflow.execute_activity(
                ACTIVITY_INVOKE_AGENT_RUNTIME,
                AgentInvocationRequest(
                    tenant_id=self._correlation.tenant_id,
                    correlation_id=self._correlation.correlation_id,
                    workflow_id=self._correlation.workflow_id,
                    subject_id=self._correlation.subject_id,
                    agent_role=step.agent_spec.agent_role,
                    task_kind=step.agent_spec.task_kind,
                    input=input_payload,
                    expected_output_contract=step.agent_spec.expected_output_contract,
                ),
                start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY_POLICY,
                result_type=AgentInvocationResponse,
            )
        except ActivityError as exc:
            raise ActivityRetryExhaustedError(
                failed_step=step.step_name,
                failed_activity=ACTIVITY_INVOKE_AGENT_RUNTIME,
                source=exc,
            ) from exc

    async def connector_call(
        self,
        step: WorkflowStepDefinition,
        *,
        invocation_id: str,
        idempotency_key: str,
        arguments: dict[str, Any],
        mode_override: str | None = None,
    ) -> ToolGatewayResponse:
        if step.connector_spec is None:
            raise ValueError(
                f"WorkflowStepDefinition {step.step_name!r} declared kind=connector "
                "without connector_spec"
            )
        try:
            return await workflow.execute_activity(
                ACTIVITY_INVOKE_TOOL_GATEWAY,
                ToolGatewayRequest(
                    tenant_id=self._correlation.tenant_id,
                    correlation_id=self._correlation.correlation_id,
                    workflow_id=self._correlation.workflow_id,
                    invocation_id=invocation_id,
                    agent_id=step.connector_spec.agent_id,
                    tool_name=step.connector_spec.tool_name,
                    mode=mode_override or step.connector_spec.mode,
                    idempotency_key=idempotency_key,
                    arguments=arguments,
                ),
                start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY_POLICY,
                result_type=ToolGatewayResponse,
            )
        except ActivityError as exc:
            raise ActivityRetryExhaustedError(
                failed_step=step.step_name,
                failed_activity=ACTIVITY_INVOKE_TOOL_GATEWAY,
                source=exc,
            ) from exc

    async def compensate_tool_failure(
        self,
        *,
        step: WorkflowStepDefinition,
        invocation_id: str,
        idempotency_key: str,
        arguments: dict[str, Any],
        failure_reason: str,
        mode: str | None = None,
    ) -> ToolFailureCompensationResult:
        if step.connector_spec is None:
            raise ValueError(
                "compensate_tool_failure requires a step with connector_spec; "
                f"got {step.step_name!r}"
            )
        return await workflow.execute_activity(
            ACTIVITY_RECORD_TOOL_FAILURE_COMPENSATION,
            ToolFailureCompensationCommand(
                tenant_id=self._correlation.tenant_id,
                correlation_id=self._correlation.correlation_id,
                workflow_id=self._correlation.workflow_id,
                workflow_type=self._correlation.workflow_type,
                workflow_actor_id=self._correlation.workflow_actor_id,
                subject_id=self._correlation.subject_id,
                subject_ref=self._correlation.subject_ref,
                invocation_id=invocation_id,
                agent_id=step.connector_spec.agent_id,
                tool_name=step.connector_spec.tool_name,
                mode=mode or step.connector_spec.mode,
                idempotency_key=idempotency_key,
                arguments=arguments,
                failure_reason=failure_reason,
            ),
            start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_RETRY_POLICY,
            result_type=ToolFailureCompensationResult,
        )

    async def record_retry_exhaustion_dlq(
        self,
        *,
        failure: ActivityRetryExhaustedError,
    ) -> RetryExhaustionDlqResult:
        return await workflow.execute_activity(
            ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ,
            RetryExhaustionDlqCommand(
                tenant_id=self._correlation.tenant_id,
                correlation_id=self._correlation.correlation_id,
                workflow_id=self._correlation.workflow_id,
                workflow_type=self._correlation.workflow_type,
                workflow_actor_id=self._correlation.workflow_actor_id,
                subject_id=self._correlation.subject_id,
                subject_ref=self._correlation.subject_ref,
                sequence=self._sequence,
                failed_step=failure.failed_step,
                failed_activity=failure.failed_activity,
                failure_reason=activity_failure_reason(failure.source),
                attempts=DEFAULT_RETRY_POLICY.maximum_attempts or 1,
            ),
            start_to_close_timeout=DEFAULT_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_RETRY_POLICY,
            result_type=RetryExhaustionDlqResult,
        )

    def advance_sequence(self, by: int = 1) -> None:
        """Advance the sequence counter after an externally-emitted event.

        Used when a downstream activity (DLQ recorder, compensation) records
        events on the same outbox stream; the spine needs to keep its
        in-memory counter aligned so subsequent emissions stay monotonic.
        """

        self._sequence += by


def activity_failure_reason(exc: ActivityError) -> str:
    """Return a bounded-length reason string for an activity failure.

    Keeps failure messages legible inside DLQ payloads, escalation events, and
    audit records.
    """

    return _activity_failure_reason(exc)


def _activity_failure_reason(exc: ActivityError) -> str:
    cause = exc.cause
    message = str(cause) if cause is not None and str(cause) else str(exc)
    if len(message) <= 500:
        return message
    return f"{message[:497]}..."
