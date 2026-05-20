---
type: project-doc
status: active
date: 2026-05-20
phase: R2
---

# R2 Exit Criteria

R2 is documentation-only. The exit criteria below confirm that R2 has
restructured the repository so it reads as a ports-and-adapters exemplar, and
that the ADR writing pass can start.

No runtime code was changed in R2. No ADRs were written in R2.

## Artefacts Produced

| Artefact | Path | Status |
|---|---|---|
| Project README rewritten around the thesis | `README.md` | Complete. |
| Project overview rewritten | `docs/overview.md` | Complete. |
| Architecture reference rewritten | `docs/architecture.md` | Complete. |
| Evidence map rewritten port-by-port | `docs/evidence-map.md` | Complete. |
| Local runbook rewritten (hybrid shape) | `docs/runbook.md` | Complete. |
| Architecture diagram (Mermaid plus port table) | Embedded in `README.md`, `docs/overview.md`, `docs/architecture.md` | Complete. |
| Pre-reset phase history archive | `docs/transformation/phase-2-archive.md` | Complete. Consolidates the former `phase-2-plan.md` and `implementation-plan.md`. |
| Phase 2E pack relocated and given a parked README | `docs/transformation/parked-phase-2e/` | Complete. Five documents plus a README. |
| Forwarding stubs at the demoted doc paths | `docs/phase-2-plan.md`, `docs/implementation-plan.md` | Complete. |
| Agent guide aligned to the thesis | `AGENTS.md` | Complete. Authority order, intro, and project shape repointed; see open questions. |
| R2 exit criteria | `docs/r2-exit-criteria.md` | This document. |

## Decisions Confirmed

The five R2 readability-shape decisions were settled with Ryan before writing.
None was deferred.

| Decision | Confirmed value |
|---|---|
| Architecture diagram format | Mermaid diagram plus a structured port table. The Mermaid carries the visual shape; the table carries the UC1, UC2, and UC3 adapter inventory. |
| Phase 2 ledger demotion target | A single consolidated archive at `docs/transformation/phase-2-archive.md`. The former `phase-2-plan.md` and `implementation-plan.md` become forwarding stubs. |
| evidence-map.md treatment | Retired the phase-by-phase structure; rewritten as a port-by-port evidence map. The pre-reset chronological ledger is linked to the archive, not reproduced. |
| runbook.md re-orientation | Hybrid: a per-port operations reference plus a single UC1 happy-path walk-through that closes with cross-provider replay-eval. |
| Phase 2E pack treatment | Moved to `docs/transformation/parked-phase-2e/` with a README that records the parked status. Removed from the top-level `docs/` surface. |

## What The ADR Writing Pass Starts From

The ADR writing pass follows R2. It starts from the following.

- The reset bundle in `docs/transformation/` remains the architectural
  authority. `engineering-thesis.md` is load-bearing.
- The rewritten top-level docs (`README.md`, `docs/overview.md`,
  `docs/architecture.md`, `docs/evidence-map.md`, `docs/runbook.md`) are the
  current architecture surface and read in thesis-led terms.
- The R1 product and domain artefacts (`product-brief.md`, `domain-model.md`,
  `r1-use-case-confirmation.md`, `r1-adapter-mapping.md`,
  `r1-exit-criteria.md`) are the authority for the product, the domain
  language, and the adapter shape.
- The existing ADR set in `adrs/` is unchanged by R2.

The ADR writing pass writes four short, decision-led ADRs in the project's
existing ADR style:

- the LangGraph reversal, which reverses ADR 0012;
- the LLM provider port ADR;
- the audit ports plus replay-eval ADR;
- the domain refocus ADR.

R3 (contract and code terminology refactor) follows the ADR pass. R4 (local
POC readiness across UC1, UC2, and UC3) follows R3.

## R2 Open Questions

No R2 shape decision was deferred. The items below are carried forward as
known work, not open R2 questions.

- Several pre-reset documents were outside the R2 rewrite scope and still
  carry Lighthouse-era framing: `docs/governance-guardrails.md`,
  `docs/governance-evidence.md`, `docs/demo-script.md`, and the two pages
  under `docs/components/`. They are superseded by the thesis and the
  rewritten top-level docs. R3 should retire or rewrite them alongside the
  code refactor.
- `AGENTS.md` was aligned to the thesis in R2 even though it was not on the
  original R2 deliverable list, because its authority order and project-shape
  section pointed at superseded documents and would have misdirected the ADR
  pass. Its stack table and component-boundary sections were left intact
  because they accurately describe the current pre-reset code; R3 updates them
  when the code moves onto the named-port surface.
- The archive and the parked Phase 2E pack preserve their source documents'
  internal relative links unchanged. Those links were written for the `docs/`
  directory; the archive preface and the parked-pack README note the
  resolution offsets. The documents are frozen, so the links were not
  repointed.

## Sign-Off

R2 exit criteria are satisfied. The repository reads as a ports-and-adapters
exemplar: the named ports and their contracts are the entry point, the
chronological phase ledger is demoted to the archive, deployment material is
parked, and the review path is understandable without source-code archaeology.

The ADR writing pass is the next phase.
