---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0002: Temporal as Durable Orchestration Spine

## Context

Lighthouse needs long-running workflow state, retries, timeouts, replay, human waits, branch visibility, and deterministic failure handling. Hand-rolled orchestration or top-level agent frameworks would obscure the strongest evidence.

## Decision

Use self-hosted Temporal with the Python SDK as the primary orchestration runtime. Temporal workflows own the durable state machine. Fallible IO, model calls, connector calls, persistence, and event publication happen in activities or service boundaries outside deterministic workflow logic.

## Consequences

- Temporal Console is part of the demo evidence.
- Workflow code must remain deterministic.
- Replay tests are mandatory for workflow changes.
- Sagas and compensations are explicit workflow branches.
- Redpanda events support projections and visibility, but do not own the critical workflow state.

