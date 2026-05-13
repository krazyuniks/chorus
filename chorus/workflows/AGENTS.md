# Workflow Implementation Instructions

This package owns Temporal workflow definitions, workflow-local DTOs, activity
entry points, the Mailpit intake boundary, and worker startup.

## Rules

- Keep workflow code deterministic. Do not use network IO, database IO, model
  calls, connector calls, random values, or wall-clock reads inside workflow
  logic.
- Put effectful work in activities in `activities.py` or activity-owned helper
  modules.
- Keep the stable activity names intact unless the architecture docs and replay
  fixtures move with the change.
- Agent invocations go through `lighthouse.invoke_agent_runtime`.
- External tool actions go through `lighthouse.invoke_tool_gateway`.
- Workflow event writes go through `lighthouse.record_workflow_event`.
- Preserve correlation fields: `tenant_id`, `correlation_id`, `workflow_id`,
  and `lead_id`.
- Workflow changes require focused workflow tests and replay coverage with
  `just test-replay`, or a documented exception.

## Local Map

- `lighthouse.py` contains the durable Lighthouse state machine.
- `activities.py` contains Temporal activities that may perform IO.
- `mailpit.py` parses and dedupes inbound Mailpit messages.
- `intake.py` is the poll-once CLI entry point.
- `worker.py` registers workflows and activities with Temporal.
- `types.py` contains serialisation-friendly workflow/activity DTOs.
