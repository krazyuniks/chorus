---
type: project-doc
status: active
date: 2026-05-19
---

# Engineering Reset Roadmap

## Current Rule

Do not resume feature development from the old Phase 2 continuation prompt.
The project moves through the reset phases below. Deployment is no longer a
Chorus repo phase; it is reframed as a future vault-level RIT project. See
the README and the vault Chorus records for that intent.

## Phase R0 - Checkpoint And Freeze

Goal: preserve the current state and stop unmanaged drift.

Tasks:

- commit the existing Chorus repo state with the original reset bundle;
- keep existing implementation intact;
- record unrelated vault changes as out of scope.

Exit criteria:

- the Chorus repo has a clean committed baseline;
- vault Chorus records point at this reset bundle;
- future work starts from a known commit.

Status: complete (commit `chore(chorus): checkpoint reset baseline`).

## Phase R0.5 - Design Codification

Goal: lock in the architectural decisions taken in the 2026-05-19 design
session before any runtime work resumes.

Tasks:

- rewrite the reset bundle around the ports-and-adapters thesis;
- add `engineering-thesis.md`, `code-refactor-directions.md`, and
  `eval-reshape-directions.md`;
- update the vault Chorus records to reflect the reset, including a
  vault-only `audience-and-purpose.md`;
- record the deployment-phase removal as a future vault-level RIT
  project, not a Chorus repo concern.

Exit criteria:

- the bundle reads coherently as a single thesis-led design package;
- the bundle commits in one checkpoint;
- no ADRs are written in this phase - ADRs come after the bundle settles.

Status: this writing pass.

## Phase R1 - Product And Domain Reframing

Goal: produce the design artefacts for the first UK-regulated use case
under the new thesis, and confirm the two further use cases.

Deliverables:

- `docs/product-brief.md` for use case 1 (UK insurance broking inbound
  quote qualification);
- `docs/domain-model.md` for use case 1 with ubiquitous language,
  state machine, approval boundaries, and FCA-regime touch points;
- R1 confirmation note recording the final use case 2 and use case 3
  selections (proposed: UK legal services intake plus conflict check;
  UK wealth management / IFA inbound enquiry);
- adapter-mapping note showing how use case 1 exercises each named port;
- R1 exit criteria document, including which existing code is preserved,
  which is reframed, and which is retired as historical evidence.

Exit criteria:

- the product brief and domain model can be read without prior Chorus
  context;
- use cases 2 and 3 are confirmed UK-regulated, with their regulators
  named;
- the adapter mapping shows how the intake, connector, and audit ports
  carry the use case;
- the README can describe the project in thesis-led architectural terms
  without platform-first abstraction.

## Phase R2 - Documentation Architecture Refactor

Goal: make the repo readable as a ports-and-adapters exemplar.

Deliverables:

- restructured `README.md`, `docs/overview.md`, `docs/architecture.md`,
  `docs/evidence-map.md`, `docs/runbook.md`, and roadmap docs around the
  ports-and-adapters thesis and the confirmed use cases;
- a single architecture diagram showing the hexagon with the six named
  ports and current adapter inventory;
- chronological Phase 2 ledger detail demoted into archival sections;
- removed or rewritten stale continuation prompts;
- separated local POC readiness from any future hosting concern.

Exit criteria:

- docs make the named ports and their contracts the entry point;
- platform controls are presented as adapter discipline, not as the
  product;
- review path is understandable without source-code archaeology;
- ADR writing pass scheduled: LangGraph reversal of ADR 0012, LLM
  provider port ADR, audit ports plus replay-eval ADR, domain refocus
  ADR.

## Phase R3 - Contract And Code Terminology Refactor

Goal: align contracts and implementation with the named ports and the
confirmed use cases.

Deliverables:

- contracts rewritten around the six ports, with use-case-specific
  payload schemas at the intake and connector ports;
- workflow plumbing factored to remove the Lighthouse / Support Triage
  duplication identified in `code-refactor-directions.md`;
- Tool Gateway hardcoded match dispatch replaced with an adapter
  registry over the connector port;
- `projection.py`, `eval/run.py`, and `doctor.py` decomposed along the
  port boundaries they currently conflate;
- LangGraph removed from the agent execution runtime; reasoning runs
  through the LLM provider port directly using the OpenAI SDK against
  any OpenAI-compatible endpoint;
- compatibility aliases for safe rename of existing schemas / generated
  models / DB tables / workflow names where deletion would break
  preserved evidence.

Exit criteria:

- code reads through the named-port surface, not through legacy workflow
  names;
- platform terms stay inside platform modules;
- eval, replay, and persistence gates pass on the refactored paths;
- the LLM provider port is provider-agnostic by construction, with the
  route catalogue recording provider plus model per call.

## Phase R4 - Local POC Readiness

Goal: make Chorus runnable and demonstrable for the three confirmed
use cases, with cross-provider replay evidence wired through.

Deliverables:

- three scenarios runnable from documented commands;
- synthetic data for each use case under each regulator's expected shape;
- read-only BFF / UI inspection for each scenario;
- demo scripts and screenshots tied to the named ports;
- invariant-based eval suite per use case;
- cross-provider replay eval mode demonstrating gpt-5.4-mini against
  captured DeepSeek V4-Flash transcripts and the reverse.

Exit criteria:

- a reviewer can run or inspect the POC locally without interpreting
  stale phase history;
- `just eval`, replay, contracts, focused tests, and docs gates match
  the implemented flows;
- the demo tells a ports-and-adapters story across three regulators.

## Cadence

Use checkpoint-based work, not one prompt per artefact.

Each checkpoint defines:

- outcome;
- files likely to change;
- gates;
- not-done boundaries;
- one short next-step note.

The durable state is this roadmap plus the current repo commit, not a
chain of increasingly long prompts.

## Deployment Reframed

The previous Phase R5 (Amazon / Terraform deployment) is removed from this
roadmap. Deployment becomes a future vault-level Radian IT project against
a future RIT client engagement; it is not in scope for the Chorus repo.
See the vault Chorus README for the deployment-as-future-RIT-project
sketch.
