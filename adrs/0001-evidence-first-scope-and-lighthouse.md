---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0001: Evidence-First Scope and Lighthouse Vertical Slice

## Context

Chorus is an architecture evidence artefact. The risk is building a wide agent platform skeleton that looks ambitious but does not prove durable orchestration, authority boundaries, auditability, failure handling, schema discipline, or evaluation.

## Decision

Phase 1 will build one complete vertical slice: Lighthouse, an inbound-lead concierge for a fictional SMB. Lighthouse is the only business workflow in Phase 1.

The slice must show intake, research/qualification, drafting, validation, propose/send or escalation, plus visible failure paths for low confidence, validator rejection, connector failure, and forbidden write attempts.

## Consequences

- Breadth is deliberately constrained so engineering depth is visible.
- A second workflow, full admin surface, real third-party connectors, production auth, cloud deployment, and Scylla implementation are deferred.
- README, architecture, ADRs, tests, eval fixtures, and the demo script must all map back to the same public evidence map.
