---
type: project-doc
status: phase-0-draft
date: 2026-04-29
---

# Chorus — Evidence Map

## Purpose

This document maps Chorus's engineering claims to the artefacts that support them.

The map is structured for architecture review: each capability links to the artefacts and code locations that demonstrate it. Where Phase 1A implementation has not yet landed, the documentation set carries the claim; the map is updated in Phase 1A docs closeout and Phase 1C final pass with cross-links to implemented evidence (code, eval fixture results, audit views, dashboards, screenshots).

## Position — outer loop / programme level

Chorus addresses **outer-loop / programme-level** concerns: governance frameworks, provider catalogue, organisational adoption pattern, runtime architecture, and an eval lifecycle that scales across teams. The companion **inner-loop** artefact is **Woof** at [`github.com/krazyuniks/woof`](https://github.com/krazyuniks/woof) — an SDLC tool for AI-assisted developer work (discovery -> definition -> breakdown -> execution -> gate, with schema-governed contracts and a per-epic JSONL audit trail). Together the two projects demonstrate a split between programme-level agent architecture and developer-loop delivery controls.

## Evidence matrix

| Capability | Chorus artefacts | Status |
|---|---|---|
| Governed agent adoption across SDLC | [`sdlc-operating-model.md`](sdlc-operating-model.md) — lifecycle stages, quality gates, change control. [`governance-guardrails.md`](governance-guardrails.md) — control matrix and guardrail layers. | Docs complete (Phase 0). |
| Overarching architecture for multi-agent workflows and LLM integrations | [`technical-architecture.md`](technical-architecture.md) — implementation architecture. [`architecture.md`](architecture.md) — decision narrative. [`adrs/`](../adrs/) — accepted decisions. | Docs complete (Phase 0). |
| Stakeholder-readable operating model | [`sdlc-operating-model.md`](sdlc-operating-model.md) — Roles and Responsibilities, Provider Collaboration Model, Team Enablement. [`overview.md`](overview.md) — narrative scope and demo shape. | Docs complete (Phase 0). |
| Provider/model governance | [`governance-guardrails.md`](governance-guardrails.md) — Phase 1 Provider Catalogue, Provider and Model Governance, routing and budget policy. [`sdlc-operating-model.md`](sdlc-operating-model.md) — Provider Collaboration Model. | Docs complete (Phase 0). Implementation: Phase 1A workstream C (Agent Runtime + model boundary). |
| LLM guardrails for transparency, security, prompt governance, auditability, and responsible-AI alignment | [`governance-guardrails.md`](governance-guardrails.md) — Governance Principles, Control Matrix, Guardrail Layers, Prompt Governance, Safety and Evaluation Governance, Responsible-AI Alignment. | Docs complete (Phase 0). |
| Cross-team component interaction model | [`technical-architecture.md`](technical-architecture.md) — Logical Components, Runtime Flow, Contract Ownership, Repository Structure, Testing and Assurance, Operations Surface. [`adrs/`](../adrs/). | Docs complete (Phase 0). |
| Team enablement and repeatable architecture practice | [`sdlc-operating-model.md`](sdlc-operating-model.md) — Team Enablement; the artefact set is structured to be readable in order. | Docs complete (Phase 0). |
| Programme planning and work decomposition | [`implementation-plan.md`](implementation-plan.md) — phased delivery with parallel-workstream decomposition. [`sdlc-operating-model.md`](sdlc-operating-model.md) — lifecycle and gates. | Docs complete (Phase 0). |
| AI lifecycle management, safety, and evaluation | [`governance-guardrails.md`](governance-guardrails.md) — Safety and Evaluation Governance. [`sdlc-operating-model.md`](sdlc-operating-model.md) — Quality Gates. [`../adrs/0007-trace-evaluation-harness.md`](../adrs/0007-trace-evaluation-harness.md). | Docs complete (Phase 0). Implementation: Phase 1A workstreams B + F; Phase 1B governance fixtures. |

## Evidence by artefact

For reverse navigation, the artefacts that this map cites:

- [`overview.md`](overview.md) — narrative scope, demo shape, design inputs.
- [`architecture.md`](architecture.md) — decision narrative; trade-offs; relationship to research inputs.
- [`technical-architecture.md`](technical-architecture.md) — components, data flow, contracts, repo structure, testing, operations, deferrals.
- [`governance-guardrails.md`](governance-guardrails.md) — control matrix; provider / prompt / safety governance; responsible-AI alignment; out-of-scope.
- [`sdlc-operating-model.md`](sdlc-operating-model.md) — lifecycle, artefact set, roles, quality gates, change control, provider collaboration, team enablement.
- [`implementation-plan.md`](implementation-plan.md) — phased delivery, parallel workstreams, deferred items.
- [`demo-script.md`](demo-script.md) — guided walkthrough script (rewritten in 1A doc closeout for the SMTP-receive trigger).
- [`../adrs/`](../adrs/) — eight accepted decisions covering evidence-first scope, Temporal orchestration, Redpanda event visibility, Agent Runtime + Tool Gateway, Postgres-first storage, JSON Schema contracts, trace/eval harness, and email intake via Mailpit.

## Updates

This map is a Phase 0 deliverable. It is updated in:

- **Phase 1A docs closeout** (implementation-plan item 11) — cross-link each row to the implementation that lands during 1A.
- **Phase 1C final pass** (implementation-plan item 12) — cross-link to eval results, audit views, dashboards, and the polished review path.
