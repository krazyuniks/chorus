# Workflows

Temporal workflow definitions and their activities.

Workflows are deterministic — all IO (HTTP calls, model invocations, database writes, tool calls) sits inside activities, never inside workflow code. Workflow histories must replay deterministically across code changes; replay tests are part of the Workstream B exit criteria.

Phase 1A: the **Lighthouse** workflow with states intake → research/qualification → draft → validation → propose/send-or-escalate. Failure branches added in Phase 1B.

See [ADR 0002 — Temporal durable orchestration](../adrs/0002-temporal-durable-orchestration.md) and [implementation-plan.md](../docs/implementation-plan.md).
