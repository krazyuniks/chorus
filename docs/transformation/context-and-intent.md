---
type: project-doc
status: active
date: 2026-05-19
---

# Context And Intent

## Why This Reset Exists

Chorus has accumulated strong technical evidence:

- durable Temporal workflows;
- explicit Agent Runtime and Tool Gateway boundaries;
- contract-generated payloads;
- Postgres audit and projections;
- Redpanda event visibility;
- eval and replay gates;
- local connector sandboxes;
- read-only BFF inspection surfaces.

The problem is not absence of engineering. The problem is that the project
story and code language have become too abstract. Recent work has focused on
architecture controls, production-readiness deferrals, and continuation
ledger hygiene. That makes the project hard to understand as a client-facing
exemplar.

The reset exists because a reviewer or potential client should be able to
answer these questions quickly:

1. What real-world business process is this?
2. Who benefits from it?
3. What pain does the workflow reduce?
4. Which decisions are made by agents, which are deterministic, and which need
   approval?
5. Where are the business rules, contracts, evidence, and audit trail?
6. What can be run locally today?

The current docs answer the technical-control questions better than the
business-domain questions. That balance must change before more development.

## Target Intent

Chorus should be a grounded exemplar for governed AI-assisted operations. It
should show how an organisation can intake operational work, classify it, route
it, gather context, propose actions, require approval where risk demands it,
and keep a replayable audit trail.

The project should still prove the engineering thesis:

- agents participate inside durable business workflows;
- agents do not own ambient authority;
- connector actions are mediated by contracts, grants, modes, idempotency,
  approval hooks, redaction, and audit;
- business outcomes are visible through read models and eval evidence;
- infrastructure deployment is a later phase, not mixed into local domain work.

But the business language must come first. The architecture should serve the
domain, not replace it.

## Layering

Use these layers consistently:

| Layer | Meaning |
|---|---|
| Chorus | The overall governed workflow exemplar and codebase. |
| Domain | The real operational problem space selected for the exemplar. |
| Use case | A runnable business workflow inside that domain. |
| Platform controls | Temporal, Agent Runtime, Tool Gateway, audit, eval, replay, observability, and policy boundaries. |
| Deployment | Optional later Amazon/Terraform or other hosting work. |

Lighthouse is currently a use case, not the product. Support Desk Triage is
currently a second workflow proof, not a compelling product story. Calendar
approval is connector evidence, not a standalone domain.

## Current Drift

The following signals show why development should pause:

- The continuation cadence is now more work than the individual docs-first
  artefacts it creates.
- Terms such as `support`, `ticket`, `case`, and `account` are technically
  implemented but not grounded in a clear client-facing domain.
- Phase 2E repeatedly says what not to implement, which makes optional
  deployment concerns feel interleaved with local POC development.
- Existing docs contain useful decisions but too much chronological ledger
  detail for a fresh reviewer.
- The worktree has broad uncommitted changes across code, tests, docs, ADRs,
  and vault records.

## Reset Decisions

1. Feature development is paused until the domain and roadmap are reset.
2. The existing code should be preserved as evidence, not discarded.
3. The support/ticket/case workflow should be reviewed for rename, reframe, or
   replacement once the domain is chosen.
4. Phase 2E documentation work should be batched and closed later, not advanced
   one continuation prompt at a time.
5. Optional Amazon/Terraform deployment belongs to its own phase after local
   POC readiness.
6. The next engineering plan must describe code, contract, docs, test, eval,
   replay, and UI changes in domain language.

## Non-Goals Of This Reset Package

This package does not select the final domain, rename code, remove existing
workflows, introduce deployment resources, or change runtime behaviour. It
creates the control surface needed to make those decisions deliberately.
