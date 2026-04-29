---
type: project-doc
status: phase-0-draft
date: 2026-04-29
---

# Chorus — Evidence Map

## Purpose

This document maps Chorus's engineering claims to the artefacts that support them.

The map is structured for architecture review: each capability links to the artefacts and code locations that demonstrate it. Where Phase 1A implementation has not yet landed, the documentation set carries the claim; the map is updated in Phase 1A docs closeout and Phase 1C final pass with cross-links to implemented evidence (code, eval fixture results, audit views, dashboards, screenshots).

## Position

Chorus addresses governed runtime orchestration for agent-enabled business processes: durable workflow state, provider/model policy, tool authority, auditability, observability, and evaluation. The companion inner-loop SDLC project is **Woof** at [`github.com/krazyuniks/woof`](https://github.com/krazyuniks/woof), which governs AI-assisted developer work (discovery -> definition -> breakdown -> execution -> gate, with schema-governed contracts and a per-epic JSONL audit trail). Woof is separate from the Chorus runtime architecture.

## Evidence matrix

| Capability | Chorus artefacts | Status |
|---|---|---|
| Governed agent workflow orchestration | [`architecture.md`](architecture.md) — principles, runtime topology, workflow architecture, component boundaries. [`governance-guardrails.md`](governance-guardrails.md) — control matrix and guardrail layers. | Docs complete (Phase 0). |
| Overarching architecture for multi-agent workflows and LLM integrations | [`architecture.md`](architecture.md) — principles, domain language, components, runtime flow, contracts, testing, operations, and deferrals. [`../adrs/`](../adrs/) — accepted decision record. | Docs complete (Phase 0). |
| Stakeholder-readable project brief | [`overview.md`](overview.md) — narrative scope, review path, demo shape, and decision-record pointer. | Docs complete (Phase 0). |
| Provider/model governance | [`governance-guardrails.md`](governance-guardrails.md) — Phase 1 Provider Catalogue, Provider and Model Governance, routing and budget policy. [`architecture.md`](architecture.md) — Agent Runtime Architecture and Model Routing. | Docs complete (Phase 0). Implementation: Phase 1A workstream C (Agent Runtime + model boundary). |
| LLM guardrails for transparency, security, prompt governance, auditability, and responsible-AI alignment | [`governance-guardrails.md`](governance-guardrails.md) — Governance Principles, Control Matrix, Guardrail Layers, Prompt Governance, Safety and Evaluation Governance, Responsible-AI Alignment. | Docs complete (Phase 0). |
| Cross-team component interaction model | [`architecture.md`](architecture.md) — component boundaries, runtime topology, contract ownership, repository structure, testing, and operations surface. [`../adrs/`](../adrs/). | Docs complete (Phase 0). |
| Schema-governed contracts and generated model drift checks | [`../contracts/`](../contracts/) — canonical JSON Schemas and samples. [`../chorus/contracts/generated/`](../chorus/contracts/generated/) — generated Pydantic models. [`../chorus/contracts/check.py`](../chorus/contracts/check.py) — schema, sample, and generated-model drift gate. | Initial Phase 0 implementation complete. |
| Postgres persistence, projections, outbox relay, and tenant isolation | [`../infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql`](../infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql) — tenant-scoped registry, routing, grants, read model, decision trail, audit, history, outbox lifecycle, and RLS. [`../infrastructure/postgres/seeds/001_demo_tenants.sql`](../infrastructure/postgres/seeds/001_demo_tenants.sql) — idempotent two-tenant seed. [`../chorus/persistence/`](../chorus/persistence/) — migration runner, projection adapter, outbox store, Redpanda relay, and projection consumer. [`../tests/persistence/test_postgres_foundation.py`](../tests/persistence/test_postgres_foundation.py) — real Postgres migration, seed, RLS, read-model, and outbox transition checks. [`../tests/persistence/test_redpanda_projection.py`](../tests/persistence/test_redpanda_projection.py) — real Redpanda publish/consume and idempotent projection evidence. | Phase 1A Workstream A complete. |
| Work decomposition and implementation path | [`implementation-plan.md`](implementation-plan.md) — phased delivery with parallel-workstream decomposition. | Docs complete (Phase 0). |
| AI lifecycle management, safety, and evaluation | [`governance-guardrails.md`](governance-guardrails.md) — Safety and Evaluation Governance. [`architecture.md`](architecture.md) — Evaluation and Assurance. [`../adrs/0007-trace-evaluation-harness.md`](../adrs/0007-trace-evaluation-harness.md). | Docs complete (Phase 0). Implementation: Phase 1A workstreams B + F; Phase 1B governance fixtures. |

## Evidence by artefact

For reverse navigation, the artefacts that this map cites:

- [`overview.md`](overview.md) — project brief, review path, demo shape, design inputs, and decision-record pointer.
- [`architecture.md`](architecture.md) — principles, domain language, component boundaries, runtime flow, contracts, repo structure, testing, operations, and deferrals.
- [`governance-guardrails.md`](governance-guardrails.md) — control matrix; provider / prompt / safety governance; responsible-AI alignment; out-of-scope.
- [`implementation-plan.md`](implementation-plan.md) — phased delivery, parallel workstreams, deferred items.
- [`demo-script.md`](demo-script.md) — guided walkthrough script (rewritten in 1A doc closeout for the SMTP-receive trigger).
- [`../adrs/`](../adrs/) — eight accepted decisions covering evidence-first scope, Temporal orchestration, Redpanda event visibility, Agent Runtime + Tool Gateway, Postgres-first storage, JSON Schema contracts, trace/eval harness, and email intake via Mailpit.

## Updates

This map is a Phase 0 deliverable. It is updated in:

- **Phase 1A docs closeout** (implementation-plan item 11) — cross-link each row to the implementation that lands during 1A.
- **Phase 1C final pass** (implementation-plan item 12) — cross-link to eval results, audit views, dashboards, and the polished review path.
