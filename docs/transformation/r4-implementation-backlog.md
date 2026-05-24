---
type: project-doc
status: active
date: 2026-05-24
phase: R4
---

# R4 Implementation Backlog

This is the single working backlog and continuation handoff for R4. Keep this
file current at the end of every R4 session, then print the next continuation
prompt from the final section of this file.

## R4 Goal

Make Chorus locally demonstrable across UC1, UC2, and UC3 while preserving the
six-port thesis:

- the workflow spine stays inside the domain core;
- the LLM provider port is the only model transport boundary;
- the Tool Gateway is the only connector authority boundary;
- audit and transcript remain separate accountability and replay surfaces;
- projections remain read-only inspection surfaces;
- eval uses invariant checks plus replay comparison, not path enumeration.

R4 is local POC readiness. It is not production hosting, production identity,
production customer-data handling, a SaaS product build, or a generic workflow
DSL.

## Current State

Chorus starts R4 from:

- the six-port contract layout and named runtime modules;
- the OpenAI-compatible provider adapter plus deterministic recorded-replay
  route;
- the connector adapter registry and UC1 sandbox connector inventory;
- the workflow spine with UC1 enquiry qualification on it;
- the audit / transcript split;
- per-port projection and doctor decomposition;
- the UC1 invariant-plus-replay eval substrate.

The known gaps are intentional R4 surfaces:

- UC2 and UC3 have confirmations and adapter deltas only, not full product
  briefs or domain models;
- UC1 connector persistence and verdict routing need to be completed beyond
  deterministic refs;
- the projection schema, DB constraints, gateway approval packaging, and eval
  fixture schema still carry UC1 assumptions;
- live provider calls need strict structured-output enforcement before
  cross-provider replay has evidential value;
- route catalogue entries, DB routing policy, provider catalogue rows, UI
  provider views, and eval route selection need to agree.

## Strategy

Do not start UC2 or UC3 implementation until the R4 design decisions and both
use-case briefs are written. The R4 implementation should then proceed in this
order:

1. Close R3 documentation drift so reviewers do not encounter contradictory
   phase status.
2. Write the R4 design decisions note and define what "runnable" means.
3. Write UC2 and UC3 product briefs plus domain models.
4. Generalise the UC1-shaped contracts, migrations, approval primitives, and
   eval fixture surfaces.
5. Complete UC1 to the full R1 connector path, including persistence-backed
   broker-firm-side refs where R3 currently computes deterministic refs.
6. Harden the LLM provider path for live routes: prompt loading, schema-bound
   structured output, provider metadata, and route-governance alignment.
7. Replace exact-output replay with a tiered replay comparator:
   schema/conduct hard failures, decision-agreement failures, review findings,
   and cost/latency metrics.
8. Implement UC2 on the shared spine.
9. Implement UC3 on the shared spine.
10. Close R4 with documented commands, evidence notes, screenshots where
    useful, and green gates or explicit recorded exceptions.

## R4 Definition Of Runnable

Unless a later R4 design decision narrows scope, a use case is runnable when:

- one documented synthetic/local intake path starts a workflow;
- the workflow runs on the shared `WorkflowSpine`;
- every LLM invocation goes through the LLM provider port and writes decision
  and transcript records;
- every connector action goes through the Tool Gateway, grant checks, argument
  validation, mode enforcement, approval policy, and tool-action audit;
- material workflow progress projects into read-only BFF/UI surfaces;
- the use-case invariant suite passes on at least one happy-path fixture and
  one conduct-relevant branch fixture;
- replay can compare the captured transcript against at least one alternate
  route when the required local credentials are present;
- all skipped live-provider or live-stack gates are recorded with reasons.

For channel coverage, use the distinction in
`docs/transformation/r4-design-decisions.md`: use-case runnable status and
channel runnable status are separate claims.

## Backlog

### P0 - Current-Docs Alignment And R4 Scoping

- [x] Create this single R4 backlog and continuation handoff file.
- [x] Remove retrospective/stub documentation and old ADRs from the working tree.
- [x] Align top-level README, runbook, evidence map, task-runner comments, and
  scaffold checks with the current living-docs state.
- [x] Decide and execute the database baseline strategy so migration filenames
  and SQL comments also read as current-state artefacts. The current migration
  chain still contains old executable SQL and should be squashed or replaced in
  a dedicated DB-baseline slice rather than edited casually.
- [x] Write the R4 design decisions note covering:
  - [x] whether R4 completes UC1 broker-firm-side persistence before UC2/UC3;
  - [x] what counts as "runnable" for channel coverage;
  - [x] what cross-provider replay compares;
  - [x] how generic approval packages work beyond calendar writes;
  - [x] how provider route catalogue, DB policy, provider catalogue rows, UI,
    and eval route selection stay aligned.
- [ ] Write `docs/product-brief-uc2.md`.
- [ ] Write `docs/domain-model-uc2.md`.
- [ ] Write `docs/product-brief-uc3.md`.
- [ ] Write `docs/domain-model-uc3.md`.
- [ ] Verify current SRA/FCA regulatory references from official sources for
  UC2 and UC3 before encoding them as conduct hooks.
- [ ] Verify exact OpenAI and DeepSeek model identifiers and credential names
  before live-provider route wiring.

### P1 - Multi-Use-Case Foundation

- [ ] Widen projection contracts and DB constraints beyond
  `uc1_enquiry_qualification` and `enq_` subject refs.
- [ ] Remove UC1-specific workflow type and actor hardcoding from shared
  activity-owned DLQ/outbox paths.
- [ ] Generalise Tool Gateway approval package creation and apply semantics
  beyond the current calendar-shaped path.
- [ ] Introduce use-case-neutral subject summary vocabulary across projection,
  DLQ, and audit payloads.
- [ ] Refactor eval into common invariants plus per-use-case conduct invariant
  modules.
- [ ] Update fixture schema so UC1, UC2, and UC3 scenarios can be represented
  without copying UC1-only enum names.

### P2 - UC1 Completion

- [ ] Persist UC1 broker-firm-side refs for quoting queue, referral inbox, and
  decline ledger behind the existing connector adapters.
- [ ] Persist or deterministically seed customer profile and product catalogue
  lookup data behind the existing read connectors.
- [ ] Route accepted, referred, declined, and missing-data verdicts through the
  appropriate connector paths.
- [ ] Materialise the UC1 policy snapshot row behind `policy_snapshot_ref`.
- [ ] Add eval fixtures and invariants that prove the full UC1 connector path,
  not only outbound missing-data messaging.

### P3 - Provider And Replay Hardening

- [ ] Load registered prompt references and prompt hashes into the live provider
  call path.
- [ ] Pass task-specific response schemas to OpenAI-compatible routes and reject
  malformed or empty `structured_data`.
- [ ] Align `default_route_catalogue`, `model_routing_policies`,
  `model_route_versions`, provider catalogue seeds, BFF provider views, and
  eval route selection.
- [ ] Add replay run records that link the original invocation, alternate route,
  comparator result, and cost/latency metrics.
- [ ] Implement tiered replay comparison:
  - [ ] hard fail for schema, policy snapshot, conduct hook, and unsafe action
    defects;
  - [ ] decision fail for terminal verdict or routing mismatch;
  - [ ] review finding for rationale, confidence, field, or evidence
    divergence;
  - [ ] metrics only for token, latency, retry, and cost deltas.

### P4 - UC2 Legal Services Intake And Conflict Check

- [ ] Add UC2 intake and connector contracts under the named ports.
- [ ] Add UC2 workflow definition on the shared spine.
- [ ] Add sandbox conflict-check, KYC/beneficial-ownership, AML record-store,
  and engagement-letter-store connectors.
- [ ] Add UC2 approval gates and conduct invariants.
- [ ] Add UC2 projections, BFF/UI inspection, fixtures, and documented commands.
- [ ] Run focused contracts, tests, replay, and eval gates for UC2.

### P5 - UC3 IFA Suitability Intake

- [ ] Add UC3 intake and connector contracts under the named ports.
- [ ] Add UC3 workflow definition on the shared spine.
- [ ] Add sandbox attitude-to-risk profiler, capacity-for-loss tool,
  suitability-report store, and platform-research connectors.
- [ ] Add UC3 approval gates and conduct invariants.
- [ ] Add UC3 projections, BFF/UI inspection, fixtures, and documented commands.
- [ ] Run focused contracts, tests, replay, and eval gates for UC3.

### P6 - R4 Closure

- [ ] Update `README.md`, `docs/overview.md`, `docs/architecture.md`,
  `docs/evidence-map.md`, and `docs/runbook.md` with final R4 status.
- [ ] Record final commands, gates, skipped gates, and evidence notes.
- [ ] Add R4 exit criteria.
- [ ] Update this backlog so every item is checked, deferred with reason, or
  blocked with reason.
- [ ] Print the next phase continuation prompt or explicitly state that R4 is
  closed.

## Evidence Notes

### 2026-05-24 - Living-Docs And R4 Backlog Setup

- Scope: current-docs alignment and R4 handoff cadence.
- Files changed: this file plus top-level docs/status references, retrospective/stub
  deletions, stale comment/sample cleanup, fixture rename to UC1 enquiry
  examples, current ADR rewrite, and scaffold updates.
- Gates run:
  - `just doctor-quick` - green.
  - `just contracts-check` - green.
  - `uv run pytest tests/test_scaffold.py tests/test_contracts.py` - green,
    5 passed.
  - `just lint` - green after formatting `chorus/doctor/scaffold.py`.
  - `git diff --check` - green.
  - living-docs stale-term sweep excluding executable migrations and
    `frontend/package-lock.json` - green except false positives on CSS
    `leading-*` class names.
- Skipped gates: live stack, provider, replay, and full `just test` are not
  relevant to this documentation/scaffold setup.
- Remaining known current-state cleanup from that session: Postgres migration
  baseline strategy, resolved by the evidence note below.

### 2026-05-24 - Postgres Current-State Baseline

- Scope: database baseline cleanup for `infrastructure/postgres/migrations`.
- Strategy: squashed the executable migration chain into
  `001_current_state_baseline.sql`; previous migration history remains in git
  history, while the live migration directory now starts from the current R4
  local POC schema baseline. The baseline is idempotent for a local database
  that already recorded the previous chain; a fresh local database or local
  volume reset is the clean path for removing pre-baseline experimental extra
  tables.
- Files changed: Postgres migration baseline, Postgres README, scaffold doctor
  path, migration runner docstring, architecture/evidence migration references,
  and this backlog handoff.
- Gates run:
  - `just doctor-quick` - green.
  - `just contracts-check` - green.
  - `uv run pytest tests/test_scaffold.py tests/test_contracts.py tests/persistence/test_postgres_foundation.py tests/tool_gateway/test_gateway.py`
    - green, 5 passed and 15 skipped.
  - `uv run pytest tests/persistence/test_postgres_foundation.py tests/tool_gateway/test_gateway.py -rs`
    - skipped all 15 database-backed tests because local Postgres on
    `localhost:5432` rejected the configured `chorus` user.
  - `just lint` - green.
  - `git diff --check` - green.
- Skipped gates: live `just db-migrate`, full `just test`, replay, eval, and
  frontend/e2e gates were not run; this slice changed the DB baseline and docs
  only, and the local Postgres service was not available with the configured
  credentials for migration execution.

### 2026-05-24 - R4 Design Decisions

- Scope: design-control note for R4 sequencing, runnable channel coverage,
  cross-provider replay comparison, generic approval packages, and provider
  route alignment.
- Files changed: `docs/transformation/r4-design-decisions.md`,
  `docs/transformation/README.md`, and this backlog handoff.
- Decisions recorded:
  - UC2 and UC3 product briefs/domain models come before runtime breadth, but
    UC2/UC3 runtime implementation waits until UC1 broker-firm-side connector
    persistence is complete.
  - Use-case runnable status and channel runnable status are separate claims.
  - Cross-provider replay uses the tiered comparator from the eval direction,
    not exact live-provider output equality.
  - Approval packages are generic Tool Gateway authority envelopes; calendar
    writes are only the current local subset.
  - Live-provider routes are usable only when executable catalogue, DB policy,
    route versions, provider catalogue rows, BFF views, and eval selection
    agree.
- Gates run:
  - `git diff --check` - green.
- Skipped gates: `just doctor`, `just contracts-check`, `just test`, replay,
  eval, frontend, and e2e gates were not run because this slice only adds a
  prescriptive design note and backlog/index updates.

## Session Cadence

A session is one autonomous agent invocation. Each session must complete a
slice end-to-end, commit it, and hand off the next prompt through this
file.

At the start of every R4 session:

1. Read `AGENTS.md`.
2. Read this file (including this section).
3. Read only the architecture, domain, contract, or code files required for
   the next unchecked item.
4. Run `git status --short --branch`.
5. Pick one bounded unchecked backlog item unless the prompt names a
   different slice. Honour the Strategy ordering.
6. State the chosen slice before editing.

At the end of every R4 session the working tree must be clean and one
commit must record the slice. Specifically:

1. Update this backlog's checkboxes and evidence notes for the work just
   completed.
2. Record gates run and gates skipped with reasons in the evidence notes.
3. Rewrite the body of the `## Next Continuation Prompt` section so it
   describes the next slice the next session should pick, in Strategy
   order. If every backlog item is checked or deferred with a recorded
   reason, write the literal `R4-COMPLETE` as the body of that section
   instead.
4. Run `git diff --check` on touched tracked files when practical.
5. Stage everything and create one Conventional Commit (`type(scope):
   description`). Do not add `Co-Authored-By` or any AI attribution. The
   working tree must be clean afterwards.
6. Re-check `git status --short --branch` to confirm cleanliness.

If you cannot proceed without a decision the prompt did not cover, stop
without committing and without editing any checkbox or the Next
Continuation Prompt section. Surface the blocking question clearly as the
final content of your response so the next session can be reprompted with
an answer; leave your uncommitted work in place for that resume.

## Next Continuation Prompt

```text
We are in /home/ryan/Work/chorus. Continue the Chorus R4 preflight using docs/transformation/r4-implementation-backlog.md as the single source of backlog and handoff state.

Read AGENTS.md and docs/transformation/r4-implementation-backlog.md (including its Session Cadence section), then run `git status --short --branch`. Preserve unrelated user changes.

Current target slice: write the UC2 product brief and UC2 domain model in Strategy order. Create docs/product-brief-uc2.md and docs/domain-model-uc2.md.

Before encoding UC2 conduct hooks, verify current SRA and UK AML regulatory references from official sources. Use the architecture authority order from AGENTS.md plus docs/transformation/r4-design-decisions.md. Keep this slice focused on UC2 docs and matching backlog/docs updates. Do not implement UC2 contracts, workflow code, connector adapters, provider routes, replay code, or database schema changes in this slice.

The UC2 brief/model must cover actors and roles, inbound artefacts, lifecycle records and state machine, commands and events, value objects and safe refs, approval points, policies and conduct invariants, connector inventory, failure/escalation paths, field placement across ports, banned/ambiguous terms, and R4 local POC boundaries.

End-of-session contract (mandatory; see Session Cadence in the backlog):
- Update checkboxes and evidence notes for the slice you completed.
- Rewrite the body of the `## Next Continuation Prompt` section in the backlog with the next slice's prompt, in Strategy order. If R4 is fully closed, write the literal `R4-COMPLETE` there instead.
- Run `git diff --check`.
- Stage everything and create one Conventional Commit (`type(scope): description`). Do not add `Co-Authored-By` or any AI attribution.
- Leave the working tree clean.

If a blocking decision the prompt does not cover comes up, stop without committing or touching checkboxes. Surface the question clearly as the final content of your response so the next session can be reprompted with an answer.
```
