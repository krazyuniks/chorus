---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0007: Trace/Evaluation Harness as Phase 1 Requirement

## Context

Observability can show what happened, but it does not prove the behaviour was acceptable. The architecture claim depends on repeatable checks for governance, contracts, path selection, and cost/latency discipline.

## Decision

Build a trace/evaluation harness as a Phase 1 exit criterion. It will run fixture leads through the workflow and assert expected path, final outcome, tool grant mode, blocked-action behaviour, validator route diversity, cost/latency budgets, emitted events, and decision-trail rows.

Fault-injection fixtures must cover low-confidence research, validator rejection, connector failure, and forbidden write attempts.

## Consequences

- Eval is not deferred until after the demo.
- Tests must inspect traces and persisted evidence, not only final UI state.
- CI can catch governance regressions that would otherwise look like successful text generation.
- The demo can close by showing a repeatable assurance gate rather than relying on a one-off live run.
