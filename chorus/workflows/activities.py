"""Temporal activities for Lighthouse workflow boundaries."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

import psycopg
from temporalio import activity

from chorus.agent_runtime import AgentRuntime, AgentRuntimeStore, LocalLighthouseModelBoundary
from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.observability import set_current_span_attributes
from chorus.persistence import ProjectionStore
from chorus.persistence.migrate import database_url_from_env
from chorus.tool_gateway.gateway import LocalToolConnector, ToolGateway, ToolGatewayStore
from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
)
from chorus.workflows.mailpit import MailpitPoller, TemporalWorkflowStarter
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    MailpitPollConfig,
    MailpitPollResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)


class WorkflowEventSink(Protocol):
    def record_workflow_event(self, event: WorkflowEvent) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


class WorkflowEventRecorder:
    def __init__(self, sink_factory: Callable[[], WorkflowEventSink]) -> None:
        self._sink_factory = sink_factory

    def record(self, command: WorkflowEventCommand) -> WorkflowEventResult:
        event = WorkflowEvent.model_validate(
            {
                "schema_version": "1.0.0",
                "event_id": str(uuid4()),
                "event_type": command.event_type,
                "occurred_at": _now().isoformat(),
                "tenant_id": command.tenant_id,
                "correlation_id": command.correlation_id,
                "workflow_id": command.workflow_id,
                "lead_id": command.lead_id,
                "sequence": command.sequence,
                "step": command.step,
                "payload": command.payload,
            }
        )
        self._sink_factory().record_workflow_event(event)
        return WorkflowEventResult(
            event_id=str(event.event_id),
            sequence=event.sequence,
            event_type=event.event_type.value,
            step=event.step.value if event.step is not None else None,
        )


def _postgres_sink_factory() -> WorkflowEventSink:
    database_url = os.environ.get("CHORUS_DATABASE_URL", database_url_from_env())
    conn = psycopg.connect(database_url)

    class _ProjectionSink:
        def record_workflow_event(self, event: WorkflowEvent) -> None:
            try:
                ProjectionStore(conn).record_workflow_event(event)
            finally:
                conn.close()

    return _ProjectionSink()


@activity.defn(name=ACTIVITY_RECORD_WORKFLOW_EVENT)
def record_workflow_event_activity(command: WorkflowEventCommand) -> WorkflowEventResult:
    set_current_span_attributes(
        tenant_id=command.tenant_id,
        correlation_id=command.correlation_id,
        workflow_id=command.workflow_id,
    )
    return WorkflowEventRecorder(_postgres_sink_factory).record(command)


@activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
def invoke_agent_runtime_activity(request: AgentInvocationRequest) -> AgentInvocationResponse:
    """Stable Agent Runtime activity boundary implemented by Workstream C."""

    set_current_span_attributes(
        tenant_id=request.tenant_id,
        correlation_id=request.correlation_id,
        workflow_id=request.workflow_id,
    )
    database_url = os.environ.get("CHORUS_DATABASE_URL", database_url_from_env())
    with psycopg.connect(database_url) as conn:
        runtime = AgentRuntime(
            AgentRuntimeStore(conn),
            LocalLighthouseModelBoundary(),
        )
        return runtime.invoke(request)


@activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
def invoke_tool_gateway_activity(request: ToolGatewayRequest) -> ToolGatewayResponse:
    """Stable Tool Gateway activity boundary implemented by Workstream D."""

    set_current_span_attributes(
        tenant_id=request.tenant_id,
        correlation_id=request.correlation_id,
        workflow_id=request.workflow_id,
    )
    database_url = os.environ.get("CHORUS_DATABASE_URL", database_url_from_env())
    with psycopg.connect(database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn))
        return gateway.invoke(request)


@activity.defn(name="lighthouse.poll_mailpit")
async def poll_mailpit_activity(config: MailpitPollConfig) -> MailpitPollResult:
    set_current_span_attributes(tenant_id=config.tenant_id)
    starter = await TemporalWorkflowStarter.connect(
        target_host=config.temporal_target_host,
        namespace=config.temporal_namespace,
        task_queue=config.task_queue,
    )
    poller = MailpitPoller(config, starter)
    return await poller.poll_once()


async def poll_mailpit_once(config: MailpitPollConfig) -> MailpitPollResult:
    """Run the intake poller directly for CLI/demo use."""

    return await poll_mailpit_activity(config)


def run_poll_mailpit_once(config: MailpitPollConfig) -> MailpitPollResult:
    return asyncio.run(poll_mailpit_once(config))
