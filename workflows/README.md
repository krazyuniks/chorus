# Workflows

Temporal workflow definitions and their activities.

Workflows are deterministic — all IO (HTTP calls, model invocations, database writes, tool calls) sits inside activities, never inside workflow code. Workflow histories must replay deterministically across code changes; replay tests are part of the Workstream B exit criteria.

Phase 1A Workstream B implements the **Lighthouse** workflow with states intake → research/qualification → draft → validation → propose/send → complete, plus the escalation branch needed by the state machine. Effectful boundaries are registered as Temporal activities:

- `lighthouse.record_workflow_event` builds generated `WorkflowEvent` payloads and calls `ProjectionStore.record_workflow_event()`.
- `lighthouse.invoke_agent_runtime` is the stable Workstream C boundary.
- `lighthouse.invoke_tool_gateway` is the stable Workstream D boundary.
- `lighthouse.poll_mailpit` reads Mailpit's HTTP API, dedupes by Message-ID, and starts Lighthouse workflows.

Run the worker with `just worker`; poll once with `just intake-once`. Replay coverage lives in `tests/workflows/fixtures/lighthouse_happy_history.json`.

See [ADR 0002 — Temporal durable orchestration](../adrs/0002-temporal-durable-orchestration.md) and [implementation-plan.md](../docs/implementation-plan.md).
