# Projection Worker

Consumes schema-governed events from Redpanda and updates Postgres read models:

- Workflow timeline (per workflow run).
- Decision trail (per agent invocation).
- Tool audit (per gateway verdict).
- DLQ / escalation surface.

Survives reconnect. Idempotent on event redelivery. Owns no critical workflow state — Temporal remains source of truth.

Phase 1A workstream **A** (Persistence + projection). See [implementation-plan.md](../../docs/implementation-plan.md).
