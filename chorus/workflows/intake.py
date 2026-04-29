"""Run one Mailpit intake poll against Temporal."""

from __future__ import annotations

import argparse
import sys

from chorus.workflows.activities import run_poll_mailpit_once
from chorus.workflows.types import MailpitPollConfig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mailpit-base-url", default="http://localhost:8025")
    parser.add_argument("--temporal-target-host", default="localhost:7233")
    parser.add_argument("--temporal-namespace", default="default")
    parser.add_argument("--task-queue", default="lighthouse")
    parser.add_argument("--tenant-id", default="tenant_demo")
    parser.add_argument("--recipient", default="leads@chorus.local")
    parser.add_argument("--page-size", type=int, default=50)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_poll_mailpit_once(
        MailpitPollConfig(
            mailpit_base_url=args.mailpit_base_url,
            temporal_target_host=args.temporal_target_host,
            temporal_namespace=args.temporal_namespace,
            task_queue=args.task_queue,
            tenant_id=args.tenant_id,
            recipient=args.recipient,
            page_size=args.page_size,
        )
    )
    print(f"parsed: {len(result.parsed_message_ids)}")
    print(f"started: {len(result.started_workflow_ids)}")
    print(f"duplicates: {len(result.duplicate_message_ids)}")
    print(f"ignored: {len(result.ignored_message_ids)}")
    for workflow_id in result.started_workflow_ids:
        print(f"workflow: {workflow_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
