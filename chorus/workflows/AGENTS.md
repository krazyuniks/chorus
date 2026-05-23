# Workflow Implementation Instructions

This package owns Temporal workflow definitions, workflow-local DTOs, activity
entry points, the shared `WorkflowSpine`, the Mailpit intake boundary, and
worker startup. R3 lands UC1 (`Uc1EnquiryQualificationWorkflow`) running on
the shared spine; UC2 and UC3 join in R4 as new `WorkflowDefinition`s over
the same primitives.

## Rules

- Keep workflow code deterministic. Do not use network IO, database IO, model
  calls, connector calls, random values, or wall-clock reads inside workflow
  logic.
- Put effectful work in activities in `activities.py` or activity-owned helper
  modules.
- Keep the stable activity names intact unless the architecture docs and
  replay fixtures move with the change. Activity names are workflow-agnostic
  (`chorus.*`) and shared across every use case on the spine.
- Agent invocations go through `WorkflowSpine.agent_call`.
- External tool actions go through `WorkflowSpine.connector_call`.
- Workflow event writes go through `WorkflowSpine.emit` (raw) or
  `WorkflowSpine.step` (start + completion pair).
- Preserve correlation fields: `tenant_id`, `correlation_id`, `workflow_id`,
  and the use case's `subject_id` / `subject_ref` (UC1: `enquiry_id` /
  `enquiry_ref`).
- Workflow changes require focused workflow tests and replay coverage with
  `just test-replay`, or a documented exception.

## Local Map

- `spine.py` holds `WorkflowSpine`, `WorkflowDefinition`,
  `WorkflowStepDefinition`, and the typed step taxonomy. Use-case workflows
  walk their definition over spine primitives.
- `uc1.py` contains the `Uc1EnquiryQualificationWorkflow` and its
  `WorkflowDefinition` for UC1.
- `activities.py` contains Temporal activities that may perform IO.
- `mailpit.py` parses inbound Mailpit messages as UC1 email-channel
  enquiries and dedupes by Message-ID.
- `intake.py` is the poll-once CLI entry point.
- `worker.py` registers workflows and activities with Temporal.
- `types.py` contains serialisation-friendly workflow / activity DTOs.
