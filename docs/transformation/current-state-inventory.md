---
type: project-doc
status: active
date: 2026-05-19
---

# Current State Inventory

This inventory captures the reset baseline. It is not a full code review.

## Implementation Worth Preserving

| Area | Current value |
|---|---|
| Temporal workflow spine | Durable workflow state and replay discipline remain the core architecture. |
| Agent Runtime | Agent invocation, model route resolution, LangGraph execution, and decision-trail evidence are useful platform controls. |
| Tool Gateway | Grants, tool modes, schema validation, idempotency, approval hooks, redaction, verdicts, and audit are central to the exemplar. |
| Contracts | JSON Schema and generated Pydantic models support contract-first development. |
| Postgres | Current audit, projection, outbox, local CRM, calendar approval, and local ticket sandbox evidence remains valuable. |
| Redpanda | Event visibility and projection pipeline are still useful for inspectability. |
| Eval and replay | Release-control evidence is a strong differentiator and should stay. |
| BFF/UI inspection | Read-only inspection surfaces are the right direction for local POC review. |
| Local connector sandboxes | Mailpit, local CRM, Radicale, and local ticket sandbox prove authority boundaries without production credentials. |

## Implementation To Reframe

| Area | Issue | Reset treatment |
|---|---|---|
| Lighthouse | Business use case is clearer than the later support workflow, but the name can be confused with the whole project. | Keep as existing evidence unless the selected domain replaces it; document it as a use case. |
| Support Desk Triage | Technically proves a second workflow, but business language is thin and not aligned to a strong client-facing story. | Rename, reframe, or retire after domain selection. |
| Ticket/case/account refs | Safe for synthetic evidence, weak as ubiquitous language without a domain. | Replace or define through the selected domain model. |
| Phase 2E docs | Useful boundaries, but the continuation cadence is too fine-grained. | Batch remaining docs or close as architecture archive after reset. |

## Pre-Reset Chorus Worktree

Before this reset package was added, `/home/ryan/Work/chorus` contained broad
uncommitted work:

- modified docs and agent guidance:
  `AGENTS.md`, `README.md`, `docs/architecture.md`,
  `docs/evidence-map.md`, `docs/implementation-plan.md`,
  `docs/overview.md`, `docs/phase-2-plan.md`, `docs/runbook.md`,
  `adrs/README.md`;
- modified implementation/test files from completed prior slices:
  `chorus/bff/app.py`, `chorus/persistence/__init__.py`,
  `chorus/persistence/projection.py`, `tests/bff/test_app.py`,
  `tests/bff/test_app_unit.py`,
  `tests/persistence/test_postgres_foundation.py`;
- untracked Phase 2E architecture artefacts:
  `adrs/0016-production-readiness-architecture-pack-scope.md`,
  `docs/production-identity-iam-mapping.md`,
  `docs/secrets-credential-handling.md`,
  `docs/deployment-topology-architecture.md`,
  `docs/backup-restore-dr-architecture.md`,
  `docs/retention-audit-storage-architecture.md`.

This reset package should be committed with that state to create a clean break.

## Vault State

The Chorus vault records are sidecar project records, not runtime authority.
They should point to this reset package and stop promoting the old `2E-06`
continuation as the next action.

Other dirty vault records under accounts, business development, and the
Radian IT website are unrelated to this reset and should not be committed as
part of the Chorus checkpoint.

## Next Safe Engineering Move

The next safe move is not a runtime change. It is Phase R1 from
[engineering-reset-roadmap.md](engineering-reset-roadmap.md): product and
domain reframing, followed by a documentation architecture refactor.
