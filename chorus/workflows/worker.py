"""Run the Chorus Temporal worker."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import psycopg
from temporalio.client import Client
from temporalio.worker import Worker

from chorus.llm_provider import LLMProviderInvocationError, RouteCatalogue, default_route_catalogue
from chorus.persistence.migrate import database_url_from_env
from chorus.workflows.activities import (
    invoke_agent_runtime_activity,
    invoke_tool_gateway_activity,
    poll_mailpit_activity,
    record_retry_exhaustion_dlq_activity,
    record_tool_failure_compensation_activity,
    record_workflow_event_activity,
)
from chorus.workflows.uc1 import Uc1EnquiryQualificationWorkflow
from chorus.workflows.uc2 import Uc2LegalServicesIntakeConflictCheckWorkflow
from chorus.workflows.uc3 import Uc3IfaSuitabilityIntakeWorkflow


class WorkerStartupConfigurationError(RuntimeError):
    """Raised when governed worker startup configuration is not runnable."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-host",
        default=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
    )
    parser.add_argument("--namespace", default=os.environ.get("TEMPORAL_NAMESPACE", "default"))
    parser.add_argument(
        "--task-queue",
        default=os.environ.get("CHORUS_TASK_QUEUE", "chorus-uc1"),
    )
    return parser


def _tracing_interceptors() -> list[Any]:
    try:
        from temporalio.contrib.opentelemetry import TracingInterceptor
    except ImportError:
        return []
    return [TracingInterceptor()]


def registered_workflow_classes() -> list[Any]:
    return [
        Uc1EnquiryQualificationWorkflow,
        Uc2LegalServicesIntakeConflictCheckWorkflow,
        Uc3IfaSuitabilityIntakeWorkflow,
    ]


def validate_live_provider_route_credentials(
    database_url: str | None = None,
    route_catalogue: RouteCatalogue | None = None,
) -> None:
    """Fail worker startup when approved live-provider routes lack credentials."""

    catalogue = route_catalogue or default_route_catalogue()
    with psycopg.connect(database_url or database_url_from_env()) as conn:
        runtime_route_ids = _approved_runtime_route_ids(conn)

    missing_credentials: list[tuple[str, str]] = []
    for route_id in runtime_route_ids:
        try:
            route = catalogue.get(route_id)
        except LLMProviderInvocationError as exc:
            raise WorkerStartupConfigurationError(
                "Approved model_routing_policies row selects unregistered LLM provider "
                f"route {route_id!r}."
            ) from exc
        credential_env = route.required_credential_env
        if credential_env and not os.environ.get(credential_env, "").strip():
            missing_credentials.append((route.route_id, credential_env))

    if missing_credentials:
        details = ", ".join(
            f"route {route_id!r} missing credential {credential_env!r}"
            for route_id, credential_env in missing_credentials
        )
        raise WorkerStartupConfigurationError(
            f"Live provider route credential gate failed: {details}."
        )


def _approved_runtime_route_ids(conn: psycopg.Connection[Any]) -> tuple[str, ...]:
    rows = conn.execute(
        """
        SELECT DISTINCT policy.runtime_route_id
        FROM model_routing_policies AS policy
        JOIN tenants AS tenant
          ON tenant.tenant_id = policy.tenant_id
         AND tenant.status = 'active'
        WHERE policy.lifecycle_state = 'approved'
        ORDER BY policy.runtime_route_id
        """
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


async def _run(target_host: str, namespace: str, task_queue: str) -> None:
    validate_live_provider_route_credentials()
    interceptors = _tracing_interceptors()
    client = await Client.connect(target_host, namespace=namespace, interceptors=interceptors)
    with ThreadPoolExecutor(max_workers=8) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=registered_workflow_classes(),
            activities=[
                record_workflow_event_activity,
                invoke_agent_runtime_activity,
                invoke_tool_gateway_activity,
                record_tool_failure_compensation_activity,
                record_retry_exhaustion_dlq_activity,
                poll_mailpit_activity,
            ],
            activity_executor=activity_executor,
            interceptors=interceptors,
        )
        await worker.run()


def main() -> int:
    args = _parser().parse_args()
    try:
        asyncio.run(_run(args.target_host, args.namespace, args.task_queue))
    except WorkerStartupConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
