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

- UC2 and UC3 have product briefs and domain models; runtime implementation
  for both still waits for shared-surface generalisation, UC1 connector
  persistence completion, and provider / replay hardening;
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
- [x] Write `docs/product-brief-uc2.md`.
- [x] Write `docs/domain-model-uc2.md`.
- [x] Write `docs/product-brief-uc3.md`.
- [x] Write `docs/domain-model-uc3.md`.
- [x] Verify current SRA/FCA regulatory references from official sources for
  UC2 and UC3 before encoding them as conduct hooks.
  - [x] UC2 SRA and UK AML sources verified from official sources on
    2026-05-24 in `docs/product-brief-uc2.md` and
    `docs/domain-model-uc2.md`.
  - [x] UC3 FCA sources verified from official sources on 2026-05-24 in
    `docs/product-brief-uc3.md` and `docs/domain-model-uc3.md`.
- [ ] Verify exact OpenAI and DeepSeek model identifiers and credential names
  before live-provider route wiring.

### P1 - Multi-Use-Case Foundation

- [x] Widen projection contracts and DB constraints beyond
  `uc1_enquiry_qualification` and `enq_` subject refs.
- [x] Remove UC1-specific workflow type and actor hardcoding from shared
  activity-owned DLQ/outbox paths.
- [x] Generalise Tool Gateway approval package creation and apply semantics
  beyond the current calendar-shaped path.
- [x] Introduce use-case-neutral subject summary vocabulary across projection,
  DLQ, and audit payloads.
- [x] Refactor eval into common invariants plus per-use-case conduct invariant
  modules.
- [x] Update fixture schema so UC1, UC2, and UC3 scenarios can be represented
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

### 2026-05-24 - UC2 Product Brief And Domain Model

- Scope: UC2 legal services intake and conflict-check product/domain preflight.
- Files changed: `docs/product-brief-uc2.md`, `docs/domain-model-uc2.md`,
  top-level UC2 documentation pointers, and this backlog handoff.
- Regulatory references verified from official sources:
  - SRA Principles and SRA Codes of Conduct current versions in effect from
    11 April 2025.
  - SRA AML obligations page updated 18 February 2026, including LSAG 2025
    official guidance for SRA-supervised firms approved by HM Treasury and
    effective from 23 April 2025.
  - SRA Sectoral Risk Assessment published 31 July 2025.
  - GOV.UK National Risk Assessment of Money Laundering and Terrorist
    Financing 2025 published by HM Treasury on 17 July 2025.
  - Money Laundering Regulations 2017 regulations 18, 19, 27, 28, 33, and 40.
- Gates run:
  - `git diff --check` - green.
- Skipped gates: `just doctor`, `just contracts-check`, `just test`, replay,
  eval, frontend, and e2e gates were not run because this slice only adds UC2
  documentation and backlog / pointer updates. No contracts, runtime code,
  connectors, routes, replay code, or database schema changed.

### 2026-05-24 - UC3 Product Brief And Domain Model

- Scope: UC3 independent financial advice suitability intake product/domain
  preflight.
- Files changed: `docs/product-brief-uc3.md`,
  `docs/domain-model-uc3.md`, top-level UC3 documentation pointers,
  `docs/r1-adapter-mapping.md`, and this backlog handoff.
- Regulatory references verified from official FCA sources:
  - COBS 2.1 client best interests.
  - COBS 6.1A adviser charging and COBS 6.2B independent / restricted advice
    service disclosure, sufficient range, focused independent advice, and
    selection process requirements.
  - COBS 9.2 suitability obligations, COBS 9.4 suitability report evidence,
    COBS 9.5 / COBS Sch 1 suitability record references, and COBS 9A noted as
    out of local POC runtime scope unless later added with fresh verification.
  - PROD 3 product governance for distributor understanding, target-market
    compatibility, distribution strategy, information from manufacturers, and
    review.
  - PRIN 2 Principle 12 and PRIN 2A Consumer Duty cross-cutting obligations,
    outcomes, consumer understanding, support, expected standards, and outcome
    monitoring.
  - FCA MiFID II retail investment advice firms page, FCA FG21/1 vulnerable
    customers guidance, FCA glossary refs for retail investment product /
    activity / independent advice, and PERG 13.3 personal recommendation.
- Gates run:
  - `git diff --check` - green.
- Skipped gates: `just doctor`, `just contracts-check`, `just test`, replay,
  eval, frontend, and e2e gates were not run because this slice only adds UC3
  documentation and backlog / pointer updates. No contracts, runtime code,
  connectors, provider routes, replay code, or database schema changed.

### 2026-05-24 - Projection Identifier Generalisation

- Scope: first P1 multi-use-case foundation slice for projection contract and
  DB-constraint generalisation only.
- Files changed: `contracts/projection/workflow_event.schema.json`, generated
  projection model, Postgres current-state baseline, focused contract and
  persistence tests, projection / persistence documentation references, and
  this backlog handoff.
- Behaviour changed:
  - the shared `workflow_event` contract now admits
    `uc1_enquiry_qualification`,
    `uc2_legal_services_intake_conflict_check`, and
    `uc3_ifa_suitability_intake`;
  - shared projection subject refs now admit `enq_`, `legal_intake_`, and
    `advice_enquiry_` safe root-subject prefixes;
  - Postgres `workflow_read_models`, `outbox_events`, and
    `approval_packages` workflow-type checks mirror the declared workflow
    family set;
  - UC1 connector contracts, UC1 connector `enq_` argument refs, eval fixture
    enums, DLQ code, gateway approval creation / apply semantics, and UI
    breadth were intentionally left for later P1 / P2 slices.
- Gates run:
  - `just contracts-gen` - regenerated the projection Pydantic model.
  - `just contracts-check` - green after regeneration.
  - `uv run pytest tests/test_contracts.py tests/persistence/test_postgres_foundation.py -rs`
    - 4 passed and 13 skipped; the skipped persistence cases include the new
    database-backed R4 identifier-constraint checks because local Postgres on
    `localhost:5432` rejected the configured `chorus` user.
  - `uv run pytest tests/bff/test_app_unit.py tests/workflows/test_activities.py`
    - green, 5 passed.
  - `just lint` - green after shortening generated schema descriptions.
  - `git diff --check` - green.
- Skipped gates: live `just db-migrate`, Redpanda projection tests, full
  `just test`, replay, eval, frontend e2e, and live-stack gates were not run;
  the local Postgres credential failure blocked DB-backed verification, and
  the slice did not implement runtime workflows, connectors, replay, or UI
  behaviour.

### 2026-05-24 - Activity-Owned DLQ / Outbox Correlation Generalisation

- Scope: second P1 multi-use-case foundation slice for shared
  activity-owned DLQ / outbox hardcoding only.
- Files changed: shared workflow DTOs, `WorkflowSpine` command construction,
  shared workflow activities, UC1 workflow constants, focused workflow /
  persistence tests, workflow package instructions, and this backlog handoff.
- Behaviour changed:
  - shared tool-failure compensation and retry-exhaustion DLQ commands now
    carry `workflow_type`, `workflow_actor_id`, `subject_id`, and
    `subject_ref` from the use-case workflow correlation;
  - activity-owned compensation and retry-DLQ audit records use the supplied
    workflow actor instead of a hardcoded UC1 actor;
  - activity-owned retry-DLQ workflow events persist the supplied
    `workflow_type` and safe `subject_ref` instead of hardcoding
    `uc1_enquiry_qualification` or omitting the subject ref;
  - UC1 preserves its existing workflow actor through the use-case-owned
    `UC1_WORKFLOW_ACTOR_ID` constant in `chorus/workflows/uc1.py`;
  - the projection contract / DB identifier surface from the previous slice
    was not changed, and the UC1-shaped `enquiry_summary` vocabulary was
    intentionally left for the later subject-summary vocabulary slice.
- Gates run:
  - `uv run pytest tests/workflows/test_uc1_workflow.py tests/workflows/test_activities.py tests/persistence/test_postgres_foundation.py -rs`
    - 5 passed and 13 skipped; the skipped persistence cases include the
    updated DB-backed retry-DLQ assertion because local Postgres on
    `localhost:5432` rejected the configured `chorus` user.
  - `just test-replay` - green, 2 passed and 5 deselected.
  - `just lint` - green, including ruff, pyright, and frontend type checking.
  - `git diff --check` - green.
  - `just contracts-check` - green via the commit hook.
- Skipped gates: live `just db-migrate`, Redpanda projection tests, full
  `just test`, eval, frontend e2e, and live-stack gates were not run; the
  local Postgres credential failure blocked DB-backed verification, and the
  slice did not implement runtime workflows, connectors, replay, contract, or
  UI behaviour.

### 2026-05-24 - Tool Gateway Approval Generalisation

- Scope: third P1 multi-use-case foundation slice for generic Tool Gateway
  approval package creation and apply semantics only.
- Files changed: Tool Gateway request DTOs and gateway implementation,
  `WorkflowSpine` request construction, Postgres approval-package constraints,
  focused gateway and persistence tests, approval lifecycle docs, Tool Gateway
  package instructions, and this backlog handoff.
- Behaviour changed:
  - `ToolGatewayRequest` now carries `workflow_type`, `subject_id`, and
    `subject_ref`; `WorkflowSpine` passes those values from workflow
    correlation so approval packages no longer hardcode UC1 workflow type;
  - approval-required write grants create approval packages for any registered
    connector write tool, with generic `subject_refs` and safe `action_refs`
    metadata; `calendar_refs` remains only as calendar projection
    compatibility metadata;
  - approval-package DB constraints now validate safe tool/action label
    shapes instead of enumerating only calendar create/cancel actions;
  - `apply_approved_write` re-enters the Tool Gateway generically and rechecks
    package state, expiry, grant, workflow type, policy refs, idempotency, and
    safe subject/action refs before connector execution;
  - `apply_approved_calendar_write` remains as a compatibility wrapper and
    calendar apply outputs still include calendar-specific status fields.
- Gates run:
  - `uv run pytest tests/tool_gateway/test_gateway.py -rs` - 3 passed and
    6 skipped; the skipped cases are DB-backed because local Postgres on
    `localhost:5432` rejected the configured `chorus` user.
  - `uv run pytest tests/persistence/test_postgres_foundation.py -rs` -
    14 skipped because local Postgres rejected the configured `chorus` user.
  - `uv run pytest tests/workflows/test_uc1_workflow.py tests/workflows/test_activities.py -rs`
    - green, 5 passed.
  - `just test-replay` - green, 2 passed and 5 deselected.
  - `just lint` - green after formatting the touched Python files.
  - `just contracts-check` - green.
  - `git diff --check` - green.
- Skipped gates: live `just db-migrate`, full `just test`, eval, frontend
  e2e, and live-stack gates were not run; DB-backed verification and migration
  execution were blocked by the local Postgres credential failure, and the
  slice did not change contracts, runtime use-case breadth, connector
  adapters, eval, or UI behaviour.

### 2026-05-24 - Subject Summary Vocabulary Generalisation

- Scope: fourth P1 multi-use-case foundation slice for neutral root-subject
  summary vocabulary across projection, retry-DLQ, and audit payloads.
- Files changed: shared workflow DTOs and spine payload enrichment,
  UC1 workflow event payloads, activity-owned retry-DLQ / compensation audit
  payloads, Tool Gateway audit payloads, projection helper vocabulary,
  BFF source-summary fallback, eval scenario projection payloads, projection
  contract sample / description, focused tests, architecture / observability
  docs, and this backlog handoff.
- Behaviour changed:
  - `WorkflowCorrelation` now carries safe `subject_summary`; `WorkflowSpine`
    injects it into emitted workflow-event payloads unless a caller already
    supplied one;
  - active UC1 workflow events use `subject_summary`, `subject_from`, and
    `source_message_id`, while projection fallback still accepts legacy
    `enquiry_summary`, `sender`, and `message_id` for old rows and current UI
    compatibility;
  - retry-exhaustion DLQ events now separate the root `subject_summary` from
    the DLQ marker as `dlq_summary`;
  - workflow retry-DLQ, connector-failure compensation, and Tool Gateway audit
    events carry a generic `subject` context with workflow type, subject refs,
    and safe subject summary;
  - offline eval scenario projection events now use `subject_summary` without
    changing fixture schema breadth or adding UC2 / UC3 runtime paths.
- Gates run:
  - `uv run pytest tests/workflows/test_activities.py tests/workflows/test_uc1_workflow.py tests/tool_gateway/test_gateway.py tests/bff/test_app_unit.py -rs`
    - 12 passed and 6 skipped; skipped cases were DB-backed Tool Gateway
    tests because local Postgres on `localhost:5432` rejected the configured
    `chorus` user.
  - `uv run pytest tests/persistence/test_postgres_foundation.py -rs` -
    1 passed and 14 skipped; skipped cases were DB-backed persistence tests
    because local Postgres rejected the configured `chorus` user.
  - `uv run pytest tests/eval/test_run.py -rs` - green, 5 passed.
  - `just eval` - green for the two current UC1 offline eval fixtures.
  - `just test-replay` - green, 2 passed and 5 deselected.
  - `just contracts-check` - green after the projection contract sample /
    description update.
  - `just lint` - green after promoting projection payload helpers from
    private helpers to module-level names used by focused tests.
  - `git diff --check` - green.
- Skipped gates: live `just db-migrate`, Redpanda projection integration,
  full `just test`, frontend e2e, and other live-stack gates were not run; the
  local Postgres credential failure blocked DB-backed verification, and this
  slice did not implement runtime use-case breadth, connector adapters,
  provider routes, replay comparator code, or business-specific UI breadth.

### 2026-05-24 - Eval Invariant Module Decomposition

- Scope: fifth P1 multi-use-case foundation slice for eval module
  decomposition only.
- Files changed: eval invariant composition, new common invariant module,
  new shared eval result types, new UC1 conduct invariant module, eval replay
  / runner imports, focused eval tests, eval package instructions,
  architecture / evidence-map references, and this backlog handoff.
- Behaviour preserved:
  - `chorus/eval/invariants.py` still exposes the current `UC1_INVARIANTS`
    suite and `run_invariants` runner surface;
  - current UC1 invariant order, check names, check details, and CLI report
    outcomes are preserved;
  - architecture-wide checks now live in `chorus/eval/common_invariants.py`;
  - UC1 qualification conduct hooks now live in
    `chorus/eval/use_cases/uc1_conduct.py`, giving UC2 and UC3 a module shape
    to mirror later;
  - eval fixture schema breadth, UC2 / UC3 fixtures, replay comparator code,
    provider route selection, workflows, connectors, UI behaviour, and UC1
    broker-firm-side connector persistence were intentionally left untouched.
- Gates run:
  - `uv run pytest tests/eval/test_run.py -rs` - green, 6 passed.
  - `just eval` - green for the two current UC1 offline eval fixtures with
    unchanged invariant names and outcomes.
  - `just lint` - green, including ruff, ruff format check, pyright, and
    frontend type checking.
  - `just contracts-check` - green via the commit hook.
  - `git diff --check` - green.
- Skipped gates: live stack, DB-backed tests, full `just test`, replay beyond
  the focused eval replay test, frontend e2e, UC2 / UC3 runtime gates, and
  live-provider gates were not run because this slice only decomposed eval
  modules and docs.

### 2026-05-24 - Eval Fixture Schema Breadth

- Scope: final P1 multi-use-case foundation slice for eval fixture contract
  breadth only.
- Files changed: eval fixture JSON Schema and sample, generated eval fixture
  model, UC1 scenario player compatibility guard, focused eval tests, eval
  package instructions, and this backlog handoff.
- Behaviour changed:
  - the eval fixture `workflow_type` contract now admits
    `uc1_enquiry_qualification`,
    `uc2_legal_services_intake_conflict_check`, and
    `uc3_ifa_suitability_intake`;
  - `scenario` is now a constrained use-case-owned identifier instead of a
    UC1-only enum, so future UC2 and UC3 fixtures can use domain scenario
    labels without reusing `validator_redraft` or other UC1 branch names;
  - fixture input / expected payloads now include neutral
    `source_fixture_path`, `subject_fixture_ref`, and `use_case_outcome`
    fields while current UC1 compatibility fields remain valid;
  - the offline scenario player still executes only current UC1 recorded-replay
    scenarios and explicitly rejects non-UC1 fixtures until their runtime
    playback slices land;
  - current UC1 eval CLI report shape, invariant order, check names, and pass
    outcomes were preserved.
- Gates run:
  - `just contracts-gen` - regenerated the eval fixture Pydantic model.
  - `uv run pytest tests/eval/test_run.py -rs` - green, 8 passed.
  - `just contracts-check` - green.
  - `just eval` - green for the two current UC1 offline eval fixtures with
    unchanged invariant names, order, and pass outcomes.
  - `just lint` - green after sorting `__all__` and formatting the touched
    scenario-player module.
  - `git diff --check` - green.
- Skipped gates: live stack, DB-backed tests, full `just test`, Temporal
  replay beyond the focused eval replay test, frontend e2e, UC2 / UC3 runtime
  gates, and live-provider gates were not run because this slice only widens
  the eval fixture contract/model surface and preserves current UC1 offline
  playback.

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

Current target slice: start P2 UC1 Completion in Strategy order by persisting UC1 broker-firm-side refs for quoting queue, referral inbox, and decline ledger behind the existing connector adapters.

Previous slice completed: eval fixture schema breadth was widened without adding UC2 or UC3 runtime fixtures. `contracts/eval/eval_fixture.schema.json` now admits UC1, UC2, and UC3 workflow families, treats `scenario` as a constrained use-case-owned identifier, and adds neutral `source_fixture_path`, `subject_fixture_ref`, and `use_case_outcome` fields while current UC1 compatibility fields remain valid. `chorus/eval/scenario_player.py` still executes only current UC1 recorded-replay scenarios and rejects non-UC1 fixtures until their runtime playback lands. Current UC1 eval CLI output, invariant order, check names, and pass outcomes were preserved.

Use the architecture authority order from AGENTS.md plus docs/transformation/r4-design-decisions.md, docs/product-brief.md, docs/domain-model.md, docs/r1-adapter-mapping.md, docs/architecture.md, docs/evidence-map.md, docs/runbook.md, and the current P2 backlog items. Keep this slice focused on persistence-backed UC1 broker-firm-side connector refs for quoting queue, referral inbox, and decline ledger only.

Before editing, inspect `chorus/connectors/uc1.py`, `chorus/connectors/types.py`, `chorus/tool_gateway/gateway.py`, the UC1 connector contracts and generated models under `contracts/connector/uc1/` and `chorus/contracts/generated/connector/uc1/`, `chorus/workflows/uc1.py`, `chorus/workflows/spine.py`, `chorus/workflows/activities.py`, `chorus/persistence/`, `infrastructure/postgres/migrations/001_current_state_baseline.sql`, `tests/tool_gateway/test_gateway.py`, `tests/workflows/test_uc1_workflow.py`, `tests/workflows/test_activities.py`, `tests/persistence/test_postgres_foundation.py`, and searches for deterministic refs such as `quote_ref`, `referral_ref`, `decline_ref`, `quoting_queue`, `referral_inbox`, `decline_ledger`, `deterministic`, and `uc1` connector persistence. Preserve current UC1 workflow and eval behaviour while moving only the broker-firm-side write connector refs behind persistence-backed local sandbox records.

Keep this slice focused on the first P2 UC1 connector-persistence item only. Do not implement UC2 or UC3 runtime work, add new provider route wiring, add replay comparator code, broaden eval fixture coverage beyond what is needed to preserve current UC1 behaviour, change UI behaviour, or complete the remaining P2 items for customer profile/product catalogue seeding, verdict routing, policy snapshot persistence, or full UC1 connector-path eval fixtures unless a tiny supporting test assertion is required for the broker-firm-side ref persistence change. If the persistence design exposes a contract or migration boundary that would materially change more than these three connector write surfaces, stop and surface the blocking question before committing.

End-of-session contract (mandatory; see Session Cadence in the backlog):
- Update checkboxes and evidence notes for the slice you completed.
- Rewrite the body of the `## Next Continuation Prompt` section in the backlog with the next slice's prompt, in Strategy order. If R4 is fully closed, write the literal `R4-COMPLETE` there instead.
- Run relevant focused gates for the files touched, likely including `just contracts-gen` and `just contracts-check` if connector contracts change, focused connector / workflow / persistence tests, `just eval` if UC1 eval behaviour is affected, `just lint`, and `git diff --check`. If DB-backed gates cannot run because local Postgres or another live-stack dependency is unavailable, record the skipped gate and reason.
- Stage everything and create one Conventional Commit (`type(scope): description`). Do not add `Co-Authored-By` or any AI attribution.
- Leave the working tree clean.

If a blocking decision the prompt does not cover comes up, stop without committing or touching checkboxes. Surface the question clearly as the final content of your response so the next session can be reprompted with an answer.
```
