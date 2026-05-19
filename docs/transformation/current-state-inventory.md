---
type: project-doc
status: active
date: 2026-05-19
---

# Current State Inventory

This inventory captures the reset baseline. It is not a full code review.

## Design Decisions Made On 2026-05-19

The reset bundle was extended in a single design session on 2026-05-19.
The decisions inventoried here are the gravity centre for R0.5 onwards.

| Decision | Status | Affects |
|---|---|---|
| Architectural thesis: hexagonal / ports-and-adapters for governed agentic systems with data-contract-first design at every port. | Locked. | All bundle docs, R1, R2, R3. |
| Six named ports: intake, LLM provider, connector, audit / transcript, projection sink, observability sink. | Locked. | `engineering-thesis.md`, R2 docs, R3 contracts. |
| LangGraph removed from Chorus. ADR 0012 will be reversed in the ADR pass. | Locked. | R3 code refactor; ADR pass after R2. |
| LLM adapter is the OpenAI Python SDK against any OpenAI-compatible endpoint. | Locked. | R3 LLM provider port implementation. |
| Dev provider route is DeepSeek V4-Flash with thinking-mode for reasoning steps. | Locked. | R3 route catalogue. |
| Demo / eval canonical route is OpenAI gpt-5.4-mini. | Locked. | R3 route catalogue; R4 eval. |
| Two audit ports: structured decision-trail + full-fidelity transcript. | Locked. | `engineering-thesis.md`, R3 audit refactor. |
| Replay-as-eval-substrate. Transcript port stores enough to replay any captured invocation against an alternate provider. Cross-provider replay is a first-class eval mode. | Locked. | `eval-reshape-directions.md`, R4 eval. |
| Domain story: one fleshed-out use case plus two further use cases that demonstrate adapter reuse. | Locked. | `domain-refocus-plan.md`, R1. |
| Use case 1 is UK insurance broking inbound quote qualification. Replaces fictional Lighthouse domain. | Locked. | R1 product brief. |
| Use cases 2 and 3 proposed: UK legal services intake plus conflict check (SRA); UK wealth management / IFA inbound enquiry (FCA). | Proposed; confirmed in R1. | R1 confirmation note. |
| Deployment phase removed from the Chorus repo and reframed as a future vault-level RIT project. | Locked. | Roadmap; vault README. |
| WOOF and Chorus are unrelated projects with no shared substrate. | Recorded. | Vault records. |

## Implementation Worth Preserving (Ports-And-Adapters Frame)

Existing code is preserved as evidence and reframed against the named-port
surface. Nothing is deleted in R0.5.

| Existing component | Port it maps to | Notes |
|---|---|---|
| Temporal workflow spine | Workflow durability is internal to the domain core, not a port. The reuse of Temporal stays as the workflow engine for now. | The plumbing duplication between Lighthouse and Support Triage workflows is a refactor target in R3 (see `code-refactor-directions.md`). |
| Agent Runtime | LLM provider port. | LangGraph executor leaves in R3. The OpenAI-SDK-against-compatible-endpoint adapter takes its place. Route catalogue records provider and model per call. |
| Tool Gateway | Connector port authority layer. | The hardcoded match dispatch in `tool_gateway/gateway.py` becomes an adapter registry in R3. Grants, modes, idempotency, approval hooks, redaction, and verdicts stay. |
| Contracts (JSON Schema + generated Pydantic) | Contract definitions across every port. | Contracts are the source of truth at the port boundary. Use-case-specific payload schemas land at the intake and connector ports in R3. |
| Postgres audit and projection store | Audit ports plus projection sink. | The audit store splits into the structured decision-trail port and the full-fidelity transcript port in R3. |
| Redpanda event stream | Projection sink event source plus observability sink hooks. | Event visibility stays; the contracts on the wire move under the named-port discipline. |
| Eval and replay harness | Eval substrate over the audit ports. | Shape moves from path enumeration to invariant-based eval plus replay-as-comparison; see `eval-reshape-directions.md`. |
| BFF / UI inspection | Projection sink consumer. | Stays read-only. R2 reorganises around the named ports. |
| Local connector sandboxes (Mailpit, local CRM, Radicale, ticket sandbox) | Connector port adapters. | They are kept as adapter examples. Use-case-specific connector adapters arrive in R3 / R4. |

## Implementation To Reframe Or Retire

| Area | Issue | Reset treatment |
|---|---|---|
| Lighthouse | Was the project's named exemplar. Replaced by use case 1 (UK insurance broking). | Code stays as historical evidence until R3 retires or renames it. |
| Support Desk Triage | Second-workflow proof, business language is thin, does not map to a confirmed UK-regulated use case. | Retired or replaced in R3. Its workflow-proof role passes to use case 2 (UK legal intake / conflict check) once confirmed. |
| Ticket / case / account refs | Generic helpdesk language; not aligned to the UK-regulated domains. | Replaced with domain language for the confirmed use cases. |
| Workflow plumbing duplication | `chorus/workflows/support.py` imports activity names and patterns from `chorus/workflows/lighthouse.py` and reproduces the orchestration shape. | R3 factors the shared spine out. |
| Tool Gateway match dispatch | `chorus/tool_gateway/gateway.py` dispatches connector calls via a hardcoded `match tool_name` block. | R3 replaces it with an adapter registry behind the connector port. |
| Oversize files | `chorus/persistence/projection.py` (~1,572 lines), `chorus/eval/run.py` (~2,219 lines), `chorus/doctor.py` (~612 lines) each conflate multiple concerns. | R3 decomposes them along port boundaries. |
| Phase 2E production-readiness pack | Useful research, but written before the thesis was settled. | Parked. The deployment phase is reframed as a vault-level RIT project. |

## Pre-Reset Chorus Worktree

Before the original reset checkpoint, the Chorus working tree held broad
uncommitted work across docs, implementation, tests, and Phase 2E
architecture artefacts. That state was committed as the reset baseline
(commit `chore(chorus): checkpoint reset baseline`). R0.5 then layered the
design codification on top.

## Vault State

The Chorus vault records are sidecar project records, not runtime
authority. They point at this reset bundle and at the vault-only
`audience-and-purpose.md` for the three-audience model. Unrelated dirty
vault records under accounts, business development, and the Radian IT
website are not part of the Chorus checkpoint.

## Next Safe Engineering Move

R1: product brief and domain model for use case 1 (UK insurance broking
inbound quote qualification), plus confirmation of use cases 2 and 3. No
runtime code changes in R1.
