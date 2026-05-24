"""Live readiness probe for Temporal (the workflow spine substrate).

Temporal is not a port; it is the durable orchestration runtime the spine
runs on. The probe verifies the frontend is reachable, the UI is up (when
expected), and the UC1 task queue has at least one worker poller registered.
"""

from __future__ import annotations

import asyncio
import os

from chorus.doctor._net import env_int, tcp_reachable
from chorus.doctor._reporting import fail, ok, section, skip


async def _describe_temporal_task_queue(*, task_queue: str) -> int:
    from temporalio.api.enums.v1 import TaskQueueType
    from temporalio.api.taskqueue.v1 import TaskQueue
    from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
    from temporalio.client import Client

    target_host = f"localhost:{env_int('TEMPORAL_PORT', 7233)}"
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    client = await Client.connect(target_host, namespace=namespace)
    response = await client.workflow_service.describe_task_queue(
        DescribeTaskQueueRequest(
            namespace=namespace,
            task_queue=TaskQueue(name=task_queue),
            task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
            report_pollers=True,
        )
    )
    return len(response.pollers)


def check_temporal() -> int:
    section("temporal (workflow spine substrate)")
    port = env_int("TEMPORAL_PORT", 7233)
    ui_port = env_int("TEMPORAL_UI_PORT", 8233)
    if not tcp_reachable("localhost", port):
        skip(f"temporal frontend not reachable on localhost:{port} (run 'just up')")
        return 0
    ok(f"temporal frontend reachable on localhost:{port}")
    if tcp_reachable("localhost", ui_port):
        ok(f"temporal UI reachable on localhost:{ui_port}")
    else:
        skip(f"temporal UI not reachable on localhost:{ui_port}")
    task_queue = os.environ.get("CHORUS_TASK_QUEUE", "chorus-uc1")
    try:
        pollers = asyncio.run(_describe_temporal_task_queue(task_queue=task_queue))
    except Exception as exc:
        fail(f"temporal task queue '{task_queue}' discovery failed: {exc}")
        return 1
    if pollers > 0:
        ok(f"temporal task queue '{task_queue}' has {pollers} worker poller(s)")
        return 0
    fail(f"temporal task queue '{task_queue}' has no worker pollers")
    return 1
