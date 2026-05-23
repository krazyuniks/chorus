"""Run the Chorus UC1 Temporal worker."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from chorus.workflows.activities import (
    invoke_agent_runtime_activity,
    invoke_tool_gateway_activity,
    poll_mailpit_activity,
    record_retry_exhaustion_dlq_activity,
    record_tool_failure_compensation_activity,
    record_workflow_event_activity,
)
from chorus.workflows.uc1 import Uc1EnquiryQualificationWorkflow


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


async def _run(target_host: str, namespace: str, task_queue: str) -> None:
    interceptors = _tracing_interceptors()
    client = await Client.connect(target_host, namespace=namespace, interceptors=interceptors)
    with ThreadPoolExecutor(max_workers=8) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[Uc1EnquiryQualificationWorkflow],
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
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
