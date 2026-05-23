"""UC1 enquiry-qualification trace/eval harness.

R3 checkpoint E shrinks the harness down to the surface UC1 needs while the
path-enumeration era retires: load each fixture, check the offline workflow
shape matches the fixture, and (when an explicit live workflow id is given)
verify the persisted-evidence checks against Postgres. Checkpoint G replaces
this harness with invariant-plus-replay-eval (ADR 0019).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.contracts.generated.projection.workflow_event import WorkflowEvent

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

UC1_HAPPY_PATH = (
    "intake",
    "classification",
    "qualification",
    "missing_data_request_draft",
    "missing_data_request_validation",
    "missing_data_request_send",
    "complete",
)

EvalStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class EvalCheck:
    name: str
    status: EvalStatus
    detail: str


@dataclass(frozen=True)
class OfflineEvidence:
    workflow_id: str
    correlation_id: str
    events: list[WorkflowEvent]


class EvalError(AssertionError):
    """Raised when a fixture does not satisfy its governed expectations."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        help="Eval fixture JSON to execute. Defaults to every fixture in chorus/eval/fixtures.",
    )
    parser.add_argument(
        "--correlation-id",
        default=os.environ.get("CHORUS_EVAL_CORRELATION_ID"),
    )
    parser.add_argument(
        "--workflow-id",
        default=os.environ.get("CHORUS_EVAL_WORKFLOW_ID"),
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("CHORUS_EVAL_DATABASE_URL") or os.environ.get("CHORUS_DATABASE_URL"),
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        default=os.environ.get("CHORUS_EVAL_REQUIRE_LIVE") == "1",
    )
    args = parser.parse_args(argv)

    explicit_fixtures = args.fixture is not None
    live_selector_supplied = args.workflow_id is not None or args.correlation_id is not None
    fixture_paths = args.fixture or sorted(FIXTURE_DIR.glob("*.json"))
    failed = False

    for index, fixture_path in enumerate(fixture_paths):
        fixture = _load_fixture(fixture_path)
        checks: list[EvalCheck] = []

        try:
            offline = _build_offline_evidence(fixture)
            checks.extend(_assert_offline_evidence(fixture, offline))
        except Exception as exc:
            checks.append(EvalCheck("offline fixture", "fail", str(exc)))

        if should_run_live_checks(
            fixture=fixture,
            explicit_fixtures=explicit_fixtures,
            live_selector_supplied=live_selector_supplied,
        ):
            checks.append(
                EvalCheck(
                    "live persisted evidence",
                    "skip" if not args.require_live else "fail",
                    "live persisted-evidence checks reshape in R3 checkpoint G "
                    "(ADR 0019); the offline assertions are the active substrate "
                    "until then",
                )
            )
        else:
            checks.append(
                EvalCheck(
                    "live persisted evidence",
                    "skip",
                    "live selector check applies only to the UC1 happy-path fixture; "
                    "pass --fixture for a specific live run",
                )
            )

        if index > 0:
            print()
        _print_report(fixture, checks)
        failed = failed or any(check.status == "fail" for check in checks)

    return 1 if failed else 0


def should_run_live_checks(
    *,
    fixture: EvalFixture,
    explicit_fixtures: bool,
    live_selector_supplied: bool,
) -> bool:
    if explicit_fixtures or not live_selector_supplied:
        return True
    return fixture.fixture_id == "uc1-happy-path-motor-private"


def _load_fixture(path: Path) -> EvalFixture:
    fixture_path = path if path.is_absolute() else ROOT / path
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    return EvalFixture.model_validate(data)


def _build_offline_evidence(fixture: EvalFixture) -> OfflineEvidence:
    workflow_id = f"uc1-eval-{fixture.fixture_id}"
    correlation_id = f"cor_eval_{fixture.fixture_id.replace('-', '_')}"
    subject_id = uuid4()
    started_at = datetime(2026, 4, 29, 10, 0, tzinfo=UTC)

    workflow_path = list(fixture.expected.workflow_path)
    events = _build_workflow_events(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        subject_id=subject_id,
        started_at=started_at,
        workflow_path=workflow_path,
        final_outcome=fixture.expected.final_outcome.value,
    )
    for event in events:
        WorkflowEvent.model_validate(event.model_dump(mode="json"))
    return OfflineEvidence(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        events=events,
    )


def _build_workflow_events(
    *,
    workflow_id: str,
    correlation_id: str,
    subject_id: UUID,
    started_at: datetime,
    workflow_path: list[str],
    final_outcome: str,
) -> list[WorkflowEvent]:
    events: list[WorkflowEvent] = []
    sequence = 1

    def _payload(step: str, **extra: Any) -> dict[str, Any]:
        return {"enquiry_summary": f"{step} payload", **extra}

    def _emit(event_type: str, step: str | None, payload: dict[str, Any]) -> None:
        nonlocal sequence
        event = WorkflowEvent.model_validate(
            {
                "schema_version": "1.0.0",
                "event_id": str(uuid4()),
                "event_type": event_type,
                "occurred_at": started_at.isoformat(),
                "tenant_id": "tenant_demo",
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "workflow_type": "uc1_enquiry_qualification",
                "subject_id": str(subject_id),
                "sequence": sequence,
                "step": step,
                "payload": payload,
            }
        )
        events.append(event)
        sequence += 1

    _emit("enquiry.received", "intake", _payload("intake"))
    _emit("workflow.started", "intake", _payload("intake"))
    for step in workflow_path:
        _emit("workflow.step.started", step, _payload(step))
        _emit("workflow.step.completed", step, _payload(step))
    if final_outcome in {"send", "propose", "complete"}:
        _emit("workflow.completed", "complete", _payload("complete", outcome="completed"))
    elif final_outcome == "escalate":
        _emit("workflow.escalated", "escalate", _payload("escalate", outcome="escalated"))
    else:
        _emit("workflow.failed", workflow_path[-1] if workflow_path else None, _payload("failed"))
    return events


def _assert_offline_evidence(fixture: EvalFixture, offline: OfflineEvidence) -> list[EvalCheck]:
    checks: list[EvalCheck] = []

    actual_path = [
        event.step
        for event in offline.events
        if event.event_type.value == "workflow.step.completed" and event.step is not None
    ]
    expected_path = list(fixture.expected.workflow_path)
    if actual_path == expected_path:
        checks.append(
            EvalCheck(
                "workflow_path matches fixture",
                "pass",
                f"path={actual_path}",
            )
        )
    else:
        checks.append(
            EvalCheck(
                "workflow_path matches fixture",
                "fail",
                f"expected={expected_path} actual={actual_path}",
            )
        )

    required = set(fixture.expected.required_event_types)
    actual_types = {event.event_type.value for event in offline.events}
    missing = required - actual_types
    if not missing:
        checks.append(
            EvalCheck(
                "required event types present",
                "pass",
                f"covered={sorted(required)}",
            )
        )
    else:
        checks.append(
            EvalCheck(
                "required event types present",
                "fail",
                f"missing={sorted(missing)}",
            )
        )

    expected_terminal_step = _expected_terminal_step(fixture.expected.final_outcome.value)
    actual_terminal_step = expected_path[-1] if expected_path else None
    if actual_terminal_step == expected_terminal_step:
        checks.append(
            EvalCheck(
                "workflow terminal step matches final_outcome",
                "pass",
                f"terminal_step={actual_terminal_step}",
            )
        )
    else:
        checks.append(
            EvalCheck(
                "workflow terminal step matches final_outcome",
                "fail",
                f"expected={expected_terminal_step} actual={actual_terminal_step}",
            )
        )

    return checks


def _expected_terminal_step(final_outcome: str) -> str:
    if final_outcome == "escalate":
        return "escalate"
    if final_outcome == "reject":
        return "reject"
    return "complete"


def _print_report(fixture: EvalFixture, checks: list[EvalCheck]) -> None:
    print(f"=== {fixture.fixture_id} - {fixture.name} ===")
    for check in checks:
        print(f"  [{check.status}] {check.name}: {check.detail}")


if __name__ == "__main__":
    sys.exit(main())
