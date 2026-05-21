---
type: project-doc
status: active
date: 2026-05-20
phase: R3
---

# R3 Checkpoint Ledger

R3 (contract and code terminology refactor) is the first reset phase that
touches runtime code. It is large and multi-session. This ledger is the
durable progress record: the checkpoint set, the green baseline R3 is
measured against, the settled R3 design decisions, and a per-checkpoint
status. There is no per-checkpoint continuation prompt; this ledger plus
the repo commits are the durable state.

R3 is governed by ADRs 0017-0020, the reset bundle in
[`.`](.) (especially `code-refactor-directions.md`,
`eval-reshape-directions.md`, `engineering-reset-roadmap.md`,
`engineering-thesis.md`), and the R1/R2 artefacts in [`../`](../).

## Operating rule

- Checkpoint-based work. Each checkpoint defines outcome, files likely to
  change, gates, a not-done boundary, and a short next-step note.
- Every checkpoint must leave the gates green relative to the baseline
  below. A checkpoint must not leave a gate worse than it found it.
- Gates: `just contracts-check`, `just test`, `just test-replay`,
  `just lint`, `just doctor`, `just eval`, as applicable.
- Do not skip hooks. British English, conventional commits, no AI
  attribution.
- ADRs 0017-0020 are settled. Do not relitigate them.
- R3 runs the continuation-handoff cadence: each session reads this
  ledger and the rolling continuation prompt, executes one checkpoint or
  a bounded slice of one, then updates the ledger and regenerates the
  continuation prompt at close.

## Scope and constraints

This ledger is the durable, cumulative R3 record - the R3 backlog. R3
runs the continuation-handoff cadence: alongside this ledger, a single
rolling continuation prompt at
`records/radianit/projects/chorus/next-session-prompt.md` in the vault
Chorus records frames the next checkpoint and is regenerated at the close
of each session. The ledger holds durable state; the continuation prompt
is the thin rolling handoff pointer. The R3 kickoff prompt has been
consumed; the constraints below are lifted from it so nothing is lost.

- Do not introduce deployment, hosting, identity / IAM, secrets, or other
  Phase 2E concerns; those are parked in `transformation/parked-phase-2e/`.
- Do not start R4 (local POC readiness across UC1, UC2, UC3). R3 lands
  UC1 only; the R4 entry point is prepared at R3 exit.
- Preserve pre-reset evidence: demote or rename with care rather than
  deleting evidence outright (see decision 5 - evidence is git history,
  `phase-2-archive.md`, and the ADRs).
- Apply `feedback_no_artificial_scoping_questions`: default to the most
  ambitious shape that validates the ports-and-adapters thesis; surface
  only genuine design decisions.
- Documentation moves with the code. As each checkpoint lands, update the
  docs that describe the changed code: `architecture.md` (per-port detail
  and implementation-status), `evidence-map.md` (status columns),
  `runbook.md`, and the `AGENTS.md` stack and component-boundary
  sections. Retire or rewrite the pre-reset docs flagged in
  `r2-exit-criteria.md` - `governance-guardrails.md`,
  `governance-evidence.md`, `demo-script.md`, and `docs/components/` - as
  the code they describe is refactored.
- At R3 exit, write `docs/r3-exit-criteria.md` in the shape of
  `r1-exit-criteria.md` and `r2-exit-criteria.md`, and update the vault
  Chorus `README.md` and the `project_chorus_reset` agent-memory entry.

## Green baseline

Recorded 2026-05-20 at commit `9b37338`
(`docs(adr): record the post-reset architecture decisions`), on a fresh
local stack (volumes reset, all 9 migrations plus seed data applied, 5
event schema subjects registered, Temporal worker running).

| Gate | Result | Notes |
|---|---|---|
| `just contracts-check` | green | 18 generated models current; schemas and samples valid. |
| `just doctor-quick` | green | Scaffold, executables, compose all present. |
| `just lint` | green | ruff check, ruff format, pyright strict, frontend `tsc --noEmit` all clean. |
| `just doctor` | green | All live-stack probes pass. Frontend dev server is a `skip`, not a fail. |
| `just test-replay` | green | 7 passed (Temporal replay determinism). |
| `just eval` | green | All path-enumeration fixtures pass. Live-persisted-evidence steps `skip` without `CHORUS_EVAL_*` env vars. |
| `just test` | **red** | 107 passed, 3 errors. |

### Baseline `just test` failure

The 3 errors are all in `tests/bff/test_app.py`
(`UniqueViolation` on `local_ticket_case_update_proposals_pkey`, key
`caseupd_support_bff_001`). Run in isolation the BFF tests `skip` (4
skipped); they only error inside the full-suite run. This is a pre-reset
test-isolation defect - cross-test database contamination unskips the BFF
tests and then collides on a seeded row - not a runtime code defect.

The bar for every R3 checkpoint is therefore: `just test` no worse than
107 passed / 3 errors, and every other gate green. The eval and test
reshape (checkpoint G) is expected to retire this defect by giving the
suite proper isolation; until then it is the known baseline red.

## R3 design decisions

Settled with Ryan in Phase 1, before any refactoring. Recorded here as
they are agreed.

### 1. Contract directory structure - settled

`contracts/` is regrouped around the six named ports plus `eval/`:
`intake/`, `llm_provider/`, `connector/`, `audit/`, `projection/`,
`observability/`, `eval/`. The intake and connector ports - the two the
thesis says carry use-case variation - get a `uc1/` subdirectory for
use-case-specific payload schemas; port-shared schemas sit directly in
the port directory. The four use-case-invariant ports stay flat. UC2 and
UC3 add `uc2/` and `uc3/` subdirectories under intake and connector in
R4. `audit/` holds both the decision-trail and transcript record
schemas. `projection/` holds the domain event-stream contract
(`workflow_event`) plus read-model schemas. `gen.py` and `check.py` move
from a one-level glob to a recursive `**/*.schema.json` glob; the
generated-model tree mirrors the contract tree.

### 2. Workflow-definition shape (Smell 1) - settled

The step taxonomy becomes typed data; the control flow stays as code over
shared primitives. A `WorkflowDefinition` is a typed step sequence
(`WorkflowStepDefinition` per step: step name, kind - intake / agent /
connector / approval_gate / terminal - plus an agent spec, connector
spec, or approval policy as the kind requires). A shared `WorkflowSpine`
provides the orchestration primitives (event emission, sequence and path
tracking, agent-step call, connector-step call, approval gate,
escalation, bounded retry, retry-exhaustion and compensation) over
generic, shared activity names. Each use case collapses to its
`WorkflowDefinition`, its ubiquitous-language IO types, and a thin
`@workflow.defn` class whose `run()` walks the definition via the spine,
with genuinely use-case-specific branching expressed as plain Python over
spine primitives. A fully declarative transition-and-loop interpreter was
rejected: it rebuilds the in-house orchestration-framework shape ADR 0017
removed, and the control flow is the domain process and is small enough
to read directly.

### 3. Connector adapter registry interface (Smell 2) - settled

Adapter granularity is one adapter per connector (one per sandbox
connector in the R1 adapter mapping), each declaring the family of tools
it serves. A `ConnectorAdapter` protocol exposes `adapter_id`, a
`tool_specs()` sequence of `ToolSpec` (tool name, argument contract,
return contract), and an `invoke(tool_name, mode, context, arguments)`
method. A `ConnectorRegistry` indexes every declared tool name to its
`(adapter, ToolSpec)` pair. Adapters register at a composition root at
startup. The gateway holds the registry: its call path resolves the tool
through the registry, validates arguments against the resolved
`ToolSpec`, applies the mode, dispatches to the adapter, captures audit,
and returns a verdict. Both the dispatch `match` block and the parallel
`_validate_tool_arguments` `match` block are removed; new adapters never
edit the gateway file.

### 4. Lighthouse and Support Triage code disposition - settled

R3 lands UC1 running end-to-end on the new spine. Lighthouse's workflow
role is rewritten as the UC1 workflow (`chorus/workflows/`, UC1 contracts
and ubiquitous language); the Lighthouse name and lead / company-research
language retire. Support Triage is retired outright: `support.py`, the
support agent contract, the support eval fixture, support-specific
projection code, and support runtime are deleted. Support Triage cannot
be rewritten under the new spine in R3 because UC2 has no R1 domain model
and its language is on the UC1 banned-terms list; its second-workflow
proof role passes to UC2 in R4. The branch-enumeration eval fixtures
retire per ADR 0019; Lighthouse's happy path reshapes into UC1's happy
path in checkpoint G. Pre-reset evidence is preserved in git history and
`transformation/phase-2-archive.md`, not as in-tree code. UC2 and UC3 are
deferred to R4.

### 5. Rename strategy - settled

Clean rename, no compatibility aliases. Schemas, generated models,
workflow names, and code rename directly from old to new - no dual-named
schemas, re-exported model names, or `_unused` / `// removed` shims. DB
tables restructure via new forward migrations; applied migrations are
never edited (the checksum guard enforces this). Preserved evidence is
git history (the pre-R3 baseline commit `9b37338` is tagged so the
pointer is concrete), `transformation/phase-2-archive.md`, and the ADRs -
all documentation or history that needs no live code to remain valid.
This supersedes the R0.5 `engineering-reset-roadmap.md` "compatibility
aliases" clause; `r3-exit-criteria.md` will record the supersession.

### 6. Checkpoint ordering - settled

Execution order is A, B, C, D, E, F, G. Contracts first as the
foundation; then the three port implementations that change behaviour -
B (LLM provider), C (audit), D (connector); then E (the spine, built
against the final port surfaces); then F (structural decomposition) and
G (eval reshape). B precedes C because the transcript port records what
the LLM provider port emits. One refinement to the checkpoint set: F
covers `projection.py` and `doctor.py` only; `eval/run.py`'s
decomposition is done inside G, because decomposing path-enumeration eval
is inseparable from the reshape that replaces it.

## R1-deferred items carried into R3

`r1-exit-criteria.md` carried three items explicitly into R3. Tracked
here so they are resolved before R3 exit:

- **Exact regulatory citations** (ICOBS 2.5.-1R, ICOBS 5, PROD 4,
  Consumer Duty rules). Verify before any policy snapshot ships in code -
  checkpoint E (workflow spine and policy snapshot).
- **Referral inbox adapter shape** - a separate sandbox adapter versus a
  tagged subscription on the quoting-queue adapter - checkpoint D
  (connector adapter registry).
- **Customer-profile store boundary** inside the broker firm - settle
  when the `sandbox-customer-profile` connector contract is authored -
  checkpoint D.

## Cross-checkpoint watch items

Surfaced by the 2026-05-21 plan validation:

- **Checkpoint B must keep eval deterministic.** Removing the canned
  `LocalLighthouseModelAdapter` while the eval reshape is checkpoint G
  means B must stand up a deterministic recorded / replay route in the
  route catalogue so `just eval` and `just test` stay green between B and
  G. Consistent with ADR 0018 (route catalogue) and ADR 0019 (replay);
  it is not a mock.
- **Support Triage retirement is distributed.** Each checkpoint that
  removes support code deletes the matching support tests in the same
  checkpoint, to stay gate-green. `r3-exit-criteria.md` asserts the clean
  sweep: no `lighthouse`, `support`, or `ticket` identifiers remain in
  runtime code or contracts at R3 exit.
- **The shared spine is proven by one use case in R3.** Design the
  `WorkflowSpine` and `WorkflowDefinition` (checkpoint E) against the
  UC2 / UC3 deltas in `r1-adapter-mapping.md`, not only UC1, so the
  abstraction is not silently UC1-shaped before R4 exercises it.

## Checkpoints

The checkpoint set derives from the four smells in
`code-refactor-directions.md`, the contract rewrite, and ADRs 0017-0020.
Order is settled by Phase 1 decision 6.

| Checkpoint | Outcome | Status |
|---|---|---|
| A | Contract rewrite around the six named ports. | pending - specified |
| B | LLM provider port: LangGraph removed, OpenAI-SDK adapter, route catalogue. | pending |
| C | Audit ports: decision-trail port and transcript port split. | pending |
| D | Connector adapter registry replacing the hardcoded match dispatch. | pending |
| E | Shared workflow spine factored out of the Lighthouse / Support duplication. | pending |
| F | `projection.py` and `doctor.py` decomposed along port boundaries. | pending |
| G | Eval reshape: invariants plus one happy path per use case, `eval replay`. | pending |

Per-checkpoint detail (files, gates run, not-done boundary, next-step
note) is appended below as each checkpoint lands.

### Checkpoint A - contract structure rewrite

**Outcome.** `contracts/` is reorganised into the six named-port
directories plus `eval/` (Phase 1 decision 1). Every existing schema is
relocated by `git mv` into its port home, shape preserved, so runtime
behaviour is unchanged. `gen.py` and `check.py` move to a recursive,
port-aware layout; the generated-model tree mirrors the new contract
tree. All code imports and contract-reference strings are re-pointed.

**Not-done boundary.** A is a structural rewrite only. It does not author
the new-shape port contracts - the `llm_provider` invocation contracts
(checkpoint B), the `audit` decision-trail / transcript split (C), the
`connector` UC1 payloads (D), the `intake` UC1 channel payloads (E), the
reshaped `eval` fixture (G) - each port's contract content is rewritten
by that port's checkpoint. A does not retire Support Triage: support and
ticket schemas relocate shape-preserved alongside everything else;
Support Triage retirement (decision 4) is executed incrementally by the
checkpoints that rewrite each affected module - B (runtime support
paths, `support_agent_io`), D (ticket connector and contracts), E
(`support.py`, `support_request_intake`), F (`projection.py` support),
G (eval support). R3 exit is the point at which Support Triage is fully
retired.

**Gates.** `just contracts-check`, `just lint`, `just test`,
`just test-replay`, `just eval`.
