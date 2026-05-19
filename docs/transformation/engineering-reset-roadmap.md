---
type: project-doc
status: active
date: 2026-05-19
---

# Engineering Reset Roadmap

## Current Rule

Do not resume feature development from the old Phase 2 continuation prompt.
The project should move through the reset phases below.

## Phase R0 - Checkpoint And Freeze

Goal: preserve the current state and stop unmanaged drift.

Tasks:

- commit the current Chorus repo state, including the reset package;
- commit only Chorus-specific vault record updates separately if needed;
- record unrelated vault changes as out of scope;
- keep existing implementation intact;
- do not rename code or delete docs yet.

Exit criteria:

- the Chorus repo has a clean committed baseline;
- vault Chorus records point at this reset package;
- future work can start from a known commit.

## Phase R1 - Product And Domain Reframing

Goal: select a real domain and define the exemplar's value.

Tasks:

- research candidate domains against the criteria in
  [domain-refocus-plan.md](domain-refocus-plan.md);
- select one primary domain and one optional follow-up use case;
- produce a product/domain brief;
- define the client pain, process actors, domain artefacts, and business
  outcomes;
- decide whether Lighthouse and Support Desk Triage survive, are renamed, or
  are retired as historical evidence.

Exit criteria:

- `docs/product-brief.md` exists or an equivalent replacement is approved;
- `docs/domain-model.md` exists with ubiquitous language;
- the README can describe the project without platform-first abstraction.

## Phase R2 - Documentation Architecture Refactor

Goal: make the docs useful to a fresh client/reviewer.

Tasks:

- restructure `README.md`, `docs/overview.md`, `docs/architecture.md`,
  `docs/evidence-map.md`, `docs/runbook.md`, and roadmap docs around the
  chosen domain;
- demote chronological ledger detail into archival sections;
- separate local POC readiness from optional deployment;
- batch and close remaining Phase 2E documentation if still useful;
- remove or rewrite stale vault-facing continuation prompts.

Exit criteria:

- docs clearly separate domain, platform controls, local POC, and deployment;
- the old one-item continuation cadence is retired;
- review path is understandable without source-code archaeology.

## Phase R3 - Contract And Code Terminology Refactor

Goal: align contracts and implementation names with the selected domain.

Tasks:

- map existing schemas, generated models, DB tables, workflow names, tool names,
  eval fixtures, and BFF routes to the new domain language;
- decide which terms can be changed safely and which require compatibility
  aliases;
- update contracts first, then generated models, runtime code, migrations or
  compatibility views, eval fixtures, replay histories, tests, and docs;
- preserve Lighthouse and existing evidence until replacement coverage exists.

Exit criteria:

- business contracts use ubiquitous language;
- platform terms remain in platform modules only;
- eval/replay/persistence gates prove the renamed or replaced workflow paths.

## Phase R4 - Local POC Readiness

Goal: make the project runnable and demonstrable for a few coherent use cases.

Tasks:

- define two or three local scenarios with synthetic data;
- make each scenario runnable from documented commands;
- expose read-only UI/BFF inspection for the selected scenarios;
- add or refresh demo scripts, screenshots, and evaluation fixtures;
- run a release-style local gate set.

Recommended scenarios after domain selection:

- primary intake-to-outcome workflow;
- second workflow or branch proving reuse;
- connector approval/idempotency evidence only if it supports the selected
  domain.

Exit criteria:

- a reviewer can run or inspect the POC locally without interpreting stale
  phase history;
- `just eval`, replay, contracts, focused tests, and docs gates match the
  implemented flows;
- the demo tells a client-facing story.

## Phase R5 - Optional Deployment Phase

Goal: host the exemplar if useful, without mixing deployment into local domain
development.

Tasks may include:

- Amazon/Terraform architecture decision;
- environment model;
- secrets and credential handling implementation;
- deployment automation;
- hosted observability;
- DNS/certificates;
- backup/restore mechanics;
- production provider or connector credentials if explicitly approved.

Exit criteria:

- deployment has its own ADRs, threat boundaries, credentials plan, and gates;
- local POC remains useful without the hosted deployment.

## Cadence

Use checkpoint-based work, not one prompt per artefact.

Each checkpoint should define:

- outcome;
- files likely to change;
- gates;
- not-done boundaries;
- one short next-step note.

Avoid copying a long continuation prompt at the end of every session. The
durable state should be this roadmap plus the current repo commit, not a chain
of increasingly large prompts.
