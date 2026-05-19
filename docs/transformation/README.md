---
type: project-doc
status: active
date: 2026-05-19
---

# Chorus Transformation Reset

This directory is the control point for the Chorus reset.

Development is paused until the reset work has produced a clearer domain,
roadmap, documentation structure, and engineering cadence. The project has
useful runtime evidence, but its business language and phase plan have drifted
too far towards platform abstractions. Future work must restore a client-facing
exemplar with a real operational domain, contract-first business logic, and a
local POC that can be understood without reading the implementation history.

## Reset Decision

Chorus remains the whole project: a governed multi-agent workflow exemplar.
Lighthouse is one existing use case inside Chorus, not the project itself. The
current support/ticket/case workflow is technical reuse evidence, but it is not
yet a strong client-facing domain story. Phase 2E production-readiness
architecture work is paused as a one-item continuation cadence; any remaining
2E documentation should be batched after the reset, not allowed to drive the
project.

## Bundle

- [context-and-intent.md](context-and-intent.md) records why the reset exists,
  what Chorus should become, and which boundaries now matter.
- [domain-refocus-plan.md](domain-refocus-plan.md) defines how to select and
  model the real domain before more runtime work.
- [engineering-reset-roadmap.md](engineering-reset-roadmap.md) lays out the
  transformation phases from cleanup through local POC readiness and optional
  deployment.
- [current-state-inventory.md](current-state-inventory.md) captures the current
  repo/vault state and how existing implementation should be classified.

## Operating Rule

Do not resume feature development by copying the old continuation prompt.
The next session should work from this reset bundle and either refine the reset
artefacts or start the first reset roadmap item.

Use larger checkpoints:

1. Current-state checkpoint and reset package.
2. Domain/product reframing.
3. Documentation structure refactor.
4. Code and contract terminology refactor.
5. Local POC readiness.
6. Optional Amazon/Terraform deployment phase.

Each checkpoint should have a concrete outcome and a short handoff note. Do
not generate another long-lived prompt chain where every artefact requires a
new copied prompt.
