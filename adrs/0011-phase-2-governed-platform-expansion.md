---
type: adr
status: accepted
date: 2026-05-03
---

# ADR 0011 - Phase 2 governed platform expansion

## Context

Phase 1 is complete: Lighthouse proves the narrow evidence slice with durable
workflow execution, explicit Agent Runtime identity, Tool Gateway authority,
audit, projections, observability, eval, replay, and governance/failure
fixtures.

The next risk is expanding in the wrong direction. A second workflow, mutating
admin surface, real provider adapter, connector integration, or production
deployment can each be justified in isolation. Taken together without a phase
boundary, they would turn Chorus into a broad platform skeleton and weaken the
evidence-first posture established by ADR 0001.

Phase 2 needs to reopen selected deferrals while preserving the Phase 1
evidence baseline.

## Decision

Phase 2 is a governed platform expansion, not a generic framework expansion.

The recommended sequence is:

1. provider and model governance;
2. governed runtime change control;
3. connector expansion and approval hardening;
4. a second workflow proof;
5. a production-readiness architecture pack.

The first implementation workstream is provider and model governance. It should
add real provider adapter boundaries, route-version evidence, fallback and
degradation fixtures, budget telemetry, and UI/BFF inspection while keeping the
local structured boundary as the default runnable path.

Phase 2 may revisit Phase 1 deferrals only through documented milestones in
`docs/phase-2-plan.md`. Production SaaS packaging, production customer data,
production writes to closed third-party systems, and broad workflow-DSL work
remain out of scope until an ADR explicitly changes that boundary.

## Consequences

- Phase 1 remains the stable demo and regression baseline.
- Provider/model selection becomes the first Phase 2 implementation focus
  because it directly strengthens the governance story without adding business
  workflow breadth too early.
- Runtime mutation is treated as governed change control, not simple admin CRUD.
- A second workflow is delayed until Agent Runtime, Tool Gateway, eval, and
  observability have clearer reuse evidence.
- Each Phase 2 milestone must extend the evidence map and gates before it is
  called delivered.

## Alternatives considered

### Add a second workflow first

Rejected for the first Phase 2 milestone. A second workflow would show reuse,
but it would not answer the user's immediate model-governance and failover
questions. It also risks copying Lighthouse patterns before the provider and
change-control boundaries are mature.

### Build mutating admin first

Rejected as the opening milestone. Mutating registry, route, and grant data is
valuable, but a serious admin surface needs proposal, approval, rollback,
audit, and eval promotion semantics. That work is better once 2A clarifies
route versions and provider evidence.

### Start cloud deployment first

Rejected. Cloud deployment would make the project look more production-shaped,
but it would not materially improve the core agent governance evidence. The
production-readiness architecture pack remains a later Phase 2 milestone.
