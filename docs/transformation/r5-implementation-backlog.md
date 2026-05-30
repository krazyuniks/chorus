---
type: project-doc
status: active
date: 2026-05-25
phase: R5
---

# R5 Implementation Backlog

Single working backlog and continuation handoff for R5. Declarative and
prescriptive: this file states current state, target state, and the slices that
move from one to the other. Each slice prompt is self-contained — orchestration
re-reads the repo at every step rather than carrying forward narrative history.

## R5 Goal

Chorus is locally demonstrable across UC1, UC2, and UC3 with zero "skipped
gate" exceptions, zero silent fallbacks, and runnable evidence that every
documented capability actually executes against the running stack.

R5 is not production hosting, not a SaaS build, and not a generic workflow DSL.

## Current State

- UC1 is locally runnable through the Mailpit email-intake path on the shared
  `WorkflowSpine`.
- UC2 has intake and connector contracts, a shared-spine workflow definition,
  a documented local synthetic email-intake command, deterministic sandbox
  connector adapters, Tool Gateway grants, recorded-replay route policies for
  its four workflow agent tasks, approval-package evidence for
  `engagement_letter.send`, tightened conduct invariants, workflow-path eval
  playback for one happy acceptance/send-approval-gated fixture and one
  conflict-exception branch, and projection/BFF/UI confirmation for triggered
  happy-path evidence. Live-provider replay remains deferred to P3.
- UC3 has intake and connector contracts, a shared-spine workflow definition,
  deterministic sandbox connector adapters, Tool Gateway grants,
  approval-package evidence for `suitability_report.issue`, conduct invariants,
  read-only projection/BFF/UI inspection evidence, schema-only eval fixtures,
  recorded-replay route policies for its workflow agent tasks, and
  workflow-path eval playback for one happy issue fixture and one
  Consumer Duty vulnerability-support handoff branch, with the happy issue
  fixture now projected into the existing BFF/UI inspection surfaces. It does
  **not** have:
  - a documented local intake start path.
- The OpenAI-compatible provider adapter is hardened (prompt loading, prompt
  hash, response schema, structured output, route-governance alignment,
  replay-run records, tiered comparator). Live OpenAI and DeepSeek routes are
  credential-gated and inactive by default.
- The Compose stack runs against Postgres on host `:55432` and Redpanda on
  `:19092`. Tests load `.env` automatically through `tests/conftest.py`.
- The DB-backed persistence, BFF, agent-runtime, tool-gateway, and focused UC2
  playback suites run against the running stack.

## Target State

A use case is **runnable** when every condition below holds simultaneously:

- one documented local intake path starts a workflow with no manual SQL or
  manual API priming;
- the workflow runs on the shared `WorkflowSpine`;
- every LLM invocation passes through the LLM provider port and writes
  decision and transcript records;
- every connector action passes through the Tool Gateway with grant checks,
  argument validation, mode enforcement, approval policy, and tool-action audit;
- material workflow progress projects into read-only BFF/UI surfaces;
- the use-case invariant suite passes on at least one happy-path fixture and
  at least one conduct-relevant branch fixture played end-to-end against the
  running stack;
- when live provider credentials are present, replay compares the captured
  transcript against the configured alternate route;
- every documented gate either runs green or fails loudly — no skipped gate is
  acceptable in R5.

R5 closes when UC1, UC2, and UC3 all meet the runnable definition and the
documented exit criteria are green.

## Exit Criteria

- [x] No test in `tests/` is allowed to skip on missing infrastructure. Either
  the gate runs green or the suite fails.
- [x] Per-service pyprojects under `services/*/` are kept in sync with the
  runtime imports of the `chorus` package by an automated check.
- [x] `.env.example` declares the same keys with the same values as `.env`;
  drift is caught by a check in `just lint` or `just doctor`.
- [ ] UC1, UC2, and UC3 each have a documented local intake command that
  starts a workflow and shows up in BFF/UI projections within a deterministic
  bound.
- [ ] UC1, UC2, and UC3 each have at least one happy-path eval fixture and at
  least one conduct-relevant branch fixture played end-to-end through the
  running stack; the recorded comparator output is green or has explicit
  review findings, not skipped tiers.
- [ ] OpenAI and DeepSeek live routes activate when `OPENAI_API_KEY` /
  `DEEPSEEK_API_KEY` are present and fail loudly with an explicit error when a
  declared-active route is requested without credentials.
- [x] `just doctor` verifies stack health (postgres, redpanda, mailpit,
  radicale, temporal) and refuses to report success when any long-lived
  container is not running / healthy, any one-shot init container exits
  unsuccessfully, any container has restarted since boot, any required port is
  unreachable, or any migration is unapplied.
- [ ] README, runbook, evidence-map, architecture, and ADR set declare UC1,
  UC2, and UC3 all runnable, with current commands and current evidence
  references only.

## Strategy

R5 proceeds in this order. Each phase must be closed before the next starts.

1. P0 — Infrastructure prerequisites and gate hygiene.
2. P1 — UC2 to runnable.
3. P2 — UC3 to runnable.
4. P3 — Live provider route activation.
5. P4 — Closure.

## Backlog

### P0 — Infrastructure Prerequisites And Gate Hygiene

- [x] Remove every `pytest.mark.skip` / `pytest.skip(...)` and every
  "skip-on-missing-DB" branch from `tests/`. Tests that need Postgres must
  fail when Postgres is unreachable, not skip. Tests that need a live provider
  must be in a separate suite gated by credentials, where the gate emits a
  hard failure if asked to run without them.
  Evidence (2026-05-25): `tests/conftest.py` owns the shared
  `migrated_database_url` and `redpanda_bootstrap` fixtures; both read required
  URLs from `.env` / environment and raise hard fixture errors when unset or
  unreachable. Local skip wrappers and hardcoded Postgres / Redpanda fallbacks
  were removed from the DB-backed persistence, BFF, agent-runtime, and
  tool-gateway suites. Verified with `rg` for `pytest.skip` / `skipif`, focused
  `uv run pytest tests/persistence/test_postgres_foundation.py
  tests/persistence/test_redpanda_projection.py tests/tool_gateway/test_gateway.py
  tests/bff/test_app.py tests/agent_runtime/test_runtime.py`, full
  `uv run pytest`, `just lint`, and `git diff --check`.
- [x] Add `just doctor` (or extend it) to verify, before any other gate:
  postgres reachable at the URL in `.env`, redpanda bootstrap reachable,
  Mailpit reachable, Radicale reachable, Temporal reachable, all declared
  migrations applied, all long-lived Compose containers in `running` or
  `healthy` state, one-shot init containers completed successfully, no
  container with `RestartCount > 0` since boot. Fail loud on any divergence.
  Evidence (2026-05-25): `chorus/doctor/stack_health.py` now checks declared
  Compose services through `scripts/dc`, accepts completed one-shot init
  helpers only with exit 0, fails on unhealthy / missing / restarted
  containers, and runs before downstream probes. `chorus/doctor/projection_port.py`
  now requires `CHORUS_DATABASE_URL`, verifies Postgres reachability and
  migration checksums, and probes Redpanda bootstrap. `chorus/doctor/connector_port.py`
  now fails on missing Mailpit SMTP / HTTP and adds Radicale. `check_temporal`
  fails when the Temporal frontend is unreachable. `chorus/persistence/redpanda.py`
  now registers missing `x-subject` contracts from the current `contracts/`
  tree so the Schema Registry doctor check and `just schemas-register` agree.
  Runbook and architecture docs were updated. Verified with `uv run pytest
  tests/doctor/test_stack_health.py
  tests/persistence/test_redpanda_schema_registration.py`, `just
  schemas-register`, `just doctor`, `just lint`, and `git diff --check`.
- [x] Add a contract check that fails CI when a runtime import in the
  `chorus` package needs a dependency not declared in the per-service
  pyproject that consumes it. Either auto-derive per-service deps from the
  imports or assert the set is the same.
  Evidence (2026-05-25): `chorus/doctor/service_import_contracts.py`
  walks each configured service-owned `chorus` entrypoint via Python AST,
  follows transitive in-package imports, skips `TYPE_CHECKING` imports,
  checks the resulting third-party import roots against explicit
  import-to-dependency mappings, and verifies that every non-template
  `services/*/pyproject.toml` has an explicit service contract. The active
  map covers `services/bff` -> `chorus.bff.app` and `services/intake-poller`
  -> `chorus.workflows.worker`, with Dockerfile entrypoint refs checked for
  drift. The check is wired into `just service-import-contracts`,
  `just lint-python`, `python -m chorus.doctor`, CI lint, and pre-commit;
  `docs/runbook.md` documents the operator command and failure mode.
  Verified with `uv run pytest tests/doctor/test_service_import_contracts.py`,
  `just lint`, `just doctor`, and `git diff --check`.
- [x] Add a `.env` / `.env.example` drift check to `just lint`. The two files
  must declare the same keys; values may differ only for explicitly listed
  secret keys (API keys, passwords).
  Evidence (2026-05-30): `chorus/doctor/env_drift.py` compares parsed
  assignments in `.env` and `.env.example`, fails on missing files, duplicate
  keys, keys present on only one side, and non-secret value mismatches, and
  allows value differences only for the explicit API-key / password allowlist.
  `just env-check` exposes the check directly and `just lint` runs it before
  the Python and frontend lint/type gates. `.env.example`, `AGENTS.md`, and
  `docs/runbook.md` now declare the host ports used by the running local
  stack; the ignored local `.env` is aligned to the template. Focused coverage
  in `tests/doctor/test_env_drift.py` proves matching files, allowed secret
  value differences, missing-file failures, duplicate-key failures, key drift,
  and non-secret value drift. Verified with `uv run pytest
  tests/doctor/test_env_drift.py`, `just env-check`, `just lint`, `just
  doctor`, and `git diff --check`.
- [x] Replace the per-test hardcoded Postgres URL fallbacks with a single
  shared helper that reads from environment only and fails loud when the
  variable is unset.
  Evidence (2026-05-25): completed as part of the skip-removal slice. DB-backed
  tests now use the shared `migrated_database_url` fixture in `tests/conftest.py`;
  `CHORUS_TEST_ADMIN_DATABASE_URL` is required and no test module keeps a
  hardcoded Postgres URL fallback.
- [x] Document the local development bootstrap end-to-end in
  `docs/runbook.md`: how to bring the stack up, how `tests/conftest.py` picks
  the URLs up, what to do when migrations drift, what to do when an image
  needs rebuilding after a dependency change.
  Evidence (2026-05-30): `docs/runbook.md` now documents the fresh-host
  `./scripts/first-time-setup.sh` path, `just env` / `just env-check`,
  `.env` / `.env.example` drift semantics, `scripts/dc`, stack startup,
  migrations, Schema Registry registration, `tests/conftest.py` environment
  loading and infrastructure fixtures, migration checksum recovery, schema
  subject recovery, and service-image rebuilds after dependency changes.
  Verified with `just env-check`, `just lint`, `just doctor`, and
  `git diff --check`.

### P1 — UC2 To Runnable

- [x] Add the UC2 local intake adapter that turns a documented synthetic
  intake artefact into a `start_workflow` call on the shared `WorkflowSpine`.
  Mirror the structure of the existing UC1 Mailpit intake path: a small
  poller or one-shot command that consumes a fixture, validates it against
  `contracts/intake/uc2/`, and starts the workflow with safe correlation
  fields populated.
  Evidence (2026-05-30): `chorus/workflows/uc2_synthetic_intake.py` now reads
  the documented `contracts/intake/uc2/samples/email_legal_intake.sample.json`
  artefact, validates it with the generated `EmailLegalIntake` contract model,
  normalises to `Uc2LegalIntake`, derives stable `uc2-legal-*` workflow IDs /
  safe refs, and delegates to `TemporalUc2WorkflowStarter` for
  `Uc2LegalServicesIntakeConflictCheckWorkflow.run` with duplicate rejection.
  `chorus/workflows/worker.py` now registers the UC2 workflow on the existing
  shared worker task queue. Focused coverage in
  `tests/workflows/test_uc2_synthetic_intake.py` proves fixture parsing,
  contract-validation failure, deterministic start-request construction, and
  starter delegation without adding a generic workflow-start DSL or a
  `just` operator command. Docs were aligned in README, architecture,
  evidence-map, runbook state text, and the intake-poller service README while
  leaving the operator-facing UC2 command to the later runbook slice. Verified
  with `uv run pytest tests/workflows/test_uc2_synthetic_intake.py -q`, `just
  contracts-check`, `just lint`, `just doctor`, and `git diff --check`.
- [x] Seed a UC2 model route policy that selects the recorded-replay route by
  default and records the intended OpenAI promotion metadata without
  activating a live route before the P3 gate. Wire the policy through
  `model_routing_policies` and `model_route_versions` with the same governance
  shape as UC1.
  Evidence (2026-05-30): `infrastructure/postgres/seeds/001_demo_tenants.sql`
  now seeds UC2 agent registry rows for the legal matter classifier and party
  extractor, plus recorded-replay `model_routing_policies` for the four UC2
  model-backed workflow tasks used by
  `uc2_legal_services_intake_conflict_check`. `002_provider_governance.sql`
  extends the recorded-replay provider catalogue and route-version evidence to
  those UC2 task kinds while keeping OpenAI and DeepSeek disabled and recording
  the intended future OpenAI promotion metadata for P3. Migration
  `002_uc2_model_route_roles.sql` moves the role constraints forward without
  rewriting the baseline migration. The Agent Runtime now resolves UC2
  `Uc2AgentIO` contracts through the LLM provider port, passes UC2 response
  shapes to recorded replay, and fails loudly when an approved policy lacks a
  matching approved route version. Focused coverage proves UC2 policy seeding,
  route-version alignment, and runtime resolution without silent fallback.
  Verified with `uv run pytest
  tests/agent_runtime/test_runtime.py::test_runtime_passes_uc2_response_shape_to_provider_port
  tests/agent_runtime/test_runtime.py::test_uc2_policy_resolution_invokes_recorded_replay_route_versions
  tests/persistence/test_postgres_foundation.py::test_uc2_model_route_policies_are_seeded_with_route_versions
  tests/persistence/test_postgres_foundation.py::test_migrations_and_seeds_are_idempotent
  tests/persistence/test_postgres_foundation.py::test_agent_registry_roles_are_constrained_for_seeded_r4_agents
  tests/persistence/test_postgres_foundation.py::test_provider_catalogue_seed_uc1_model
  tests/test_contracts.py::test_generated_models_validate_representative_samples
  -q`, `just contracts-check`, `just lint`, `just doctor`, and `git diff
  --check`.
- [x] Play UC2 happy-path and one branch fixture end-to-end through the
  running stack. The fixtures must drive the actual workflow code path, not
  synthetic captured-run artefacts only. Tighten `chorus/eval/use_cases/uc2_conduct.py`
  invariants so they fail loudly on missing evidence at any stage.
  Evidence (2026-05-30): `chorus/eval/uc2_workflow_playback.py` now plays UC2
  eval fixtures through `Uc2LegalServicesIntakeConflictCheckWorkflow` in a
  Temporal test environment with the real workflow activities, Agent Runtime,
  Tool Gateway, decision/transcript persistence, tool-action audit, approval
  packages, and outbox workflow progress captured back into `CapturedRun`.
  The existing happy fixture now runs through classification, party extraction,
  conflict check, KYC/BO, AML, engagement decision, draft, and the
  approval-required `engagement_letter.send` path. New fixture
  `uc2_conflict_exception_approval_conduct.json` and
  `email_legal_intake_conflict_exception.sample.json` drive the conflict-hit /
  permitted-exception branch through manual review without reaching send. UC2
  recorded replay now derives connector-valid per-run refs and carries the
  conduct evidence required by the tightened invariants; Agent Runtime
  transcripts now persist structured response evidence. Focused coverage in
  `tests/eval/test_uc2_workflow_playback.py` proves both fixtures run through
  the workflow path and that missing workflow progress, agent decision,
  transcript, tool-action audit, or approval-package table evidence fails at
  the absent stage. Verified with `uv run pytest
  tests/eval/test_uc2_workflow_playback.py
  tests/eval/test_run.py::test_uc2_invariant_suite_composes_common_and_conduct_modules
  tests/eval/test_run.py::test_uc2_conduct_invariants_pass_safe_synthetic_acceptance_run
  tests/eval/test_run.py::test_uc2_conduct_invariants_fail_completed_acceptance_without_send_apply
  tests/eval/test_run.py::test_uc2_conduct_invariants_fail_acceptance_with_blocked_conflict
  tests/eval/test_run.py::test_scenario_player_rejects_unsupported_uc2_scenario
  tests/eval/test_run.py::test_uc2_schema_only_eval_fixture_validates_without_default_playback
  tests/agent_runtime/test_runtime.py::test_runtime_records_decision_trail_and_transcript_on_every_invocation
  tests/agent_runtime/test_runtime.py::test_runtime_passes_uc2_response_shape_to_provider_port
  tests/workflows/test_uc2_workflow.py -q`, `just contracts-check`, `just
  lint`, `just doctor`, and `git diff --check`.
- [x] Project UC2 workflow progress, decision trail, and approval-package
  state into the existing BFF/UI surfaces with the same density and behaviour
  as UC1. Confirm via Playwright or a focused frontend test that a triggered
  UC2 workflow appears in projection within a deterministic bound.
  Evidence (2026-05-30): `tests/bff/test_app.py` now drives the UC2 happy
  acceptance fixture through `play_uc2_workflow_fixture_async`, applies the
  emitted workflow events to the existing projection read model within a
  two-second deterministic bound, and verifies the BFF exposes the triggered
  UC2 workflow summary, timeline steps through `engagement_letter_send`,
  decision-trail rows for all four UC2 agent tasks, Tool Gateway audit rows
  for conflict/KYC/AML/draft/send, and the requested
  `engagement_letter.send.write` approval package with safe action refs.
  The frontend now handles the BFF's named `progress` SSE event, scopes
  workflow-detail progress subscriptions by workflow ID, invalidates the
  workflow summary, timeline, decision, verdict, and approval-package queries
  together, and displays step and task-kind evidence in the dense read-only
  timeline and decision tables. Fixture and E2E coverage prove the UC2 detail
  view renders projected workflow progress, decision evidence, tool/audit
  evidence, and approval-package state without adding a mutating admin UI or a
  new projection model. Docs were aligned in README, architecture,
  evidence-map, and runbook state text while leaving the operator-facing UC2
  command to the next P1 slice. Verified with `uv run pytest
  tests/bff/test_app.py tests/bff/test_app_unit.py
  tests/persistence/test_postgres_foundation.py::test_projection_store_lists_uc2_approval_package_state
  -q`, `cd frontend && npm test -- --run src/api/sse.test.ts
  src/api/queries.test.ts 'src/routes/-workflows.$workflowId.test.tsx'`, `cd
  frontend && npm run test:e2e`, `just contracts-check`, `just lint`, `just
  doctor`, and `git diff --check`.
- [x] Document the UC2 runnable command in `docs/runbook.md` and the README
  with the exact one-liner used to start it locally.
  Evidence (2026-05-30): `docs/runbook.md` and `README.md` now document the
  exact operator command `uv run python -m
  chorus.workflows.uc2_synthetic_intake`, the default UC2
  `email_legal_intake` fixture, the stable workflow ID
  `uc2-legal-ddbe16eabd909b417f25119f`, correlation ID
  `cor_legal_email_001`, the `started: false` duplicate semantics, the
  `just relay-once` / `just project-once` evidence loop, and the BFF,
  frontend, and Temporal inspection targets. `docs/evidence-map.md` and
  `docs/architecture.md` now describe UC2 as having a documented local
  synthetic-intake path while leaving UC3 local intake and live-provider route
  activation open. No command/output contract changed, so the existing
  focused UC2 intake, BFF projection, and UI smoke suites remain the evidence
  surface. Verified with `uv run pytest
  tests/workflows/test_uc2_synthetic_intake.py tests/bff/test_app.py -q`, `cd
  frontend && npm run test:e2e`, `just contracts-check`, `just lint`, `just
  doctor`, and `git diff --check`.

### P2 — UC3 To Runnable

- [x] Add the UC3 local intake adapter following the same pattern as P1.
  Evidence (2026-05-30): `chorus/workflows/uc3_synthetic_intake.py` now reads
  the documented
  `contracts/intake/uc3/samples/email_advice_enquiry.sample.json` artefact,
  validates it with the generated `EmailAdviceEnquiry` contract model,
  normalises it to `Uc3AdviceEnquiry`, derives stable `uc3-advice-*` workflow
  IDs / safe refs / idempotency refs, and delegates to
  `TemporalUc3WorkflowStarter` for `Uc3IfaSuitabilityIntakeWorkflow.run` with
  duplicate rejection. `chorus/workflows/worker.py` now registers the UC3
  workflow on the existing shared worker task queue. Focused coverage in
  `tests/workflows/test_uc3_synthetic_intake.py` proves fixture parsing,
  contract-validation failure, deterministic start-request construction,
  starter delegation, and duplicate behaviour without requiring live Temporal;
  `tests/workflows/test_worker_registration.py` proves the shared worker
  registers UC1, UC2, and UC3 workflows. Docs were aligned in README,
  architecture, evidence-map, and runbook state text while leaving the
  operator-facing UC3 command to the later P2 documentation slice. Verified
  with `uv run pytest tests/workflows/test_uc3_synthetic_intake.py
  tests/workflows/test_worker_registration.py -q`, `just contracts-check`,
  `just lint`, `just doctor`, and `git diff --check`.
- [x] Seed a UC3 model route policy following the same pattern as P1.
  Evidence (2026-05-30): `infrastructure/postgres/migrations/003_uc3_model_route_roles.sql`
  widens the governed runtime role constraints without rewriting the baseline
  migration. `infrastructure/postgres/seeds/001_demo_tenants.sql` now seeds
  UC3 workflow model-agent rows for advice-scope classification, fact-find
  summary, risk-profile assessment, Consumer Duty support assessment, and
  suitability conclusion, plus recorded-replay `model_routing_policies` for
  the five UC3 model-backed workflow tasks used by
  `uc3_ifa_suitability_intake`. `002_provider_governance.sql` extends the
  recorded-replay provider catalogue and route-version evidence to those UC3
  task kinds while keeping OpenAI and DeepSeek disabled and recording the
  intended future OpenAI promotion metadata for P3. The Agent Runtime now
  resolves `Uc3AgentIO` contracts through the LLM provider port, supplies
  UC3 task response shapes, records UC3 audit/transcript records, returns
  deterministic recorded-replay UC3 suitability evidence, and fails loudly
  when an approved UC3 policy lacks a matching approved route version. Docs
  were aligned in README, architecture, evidence-map, and runbook while
  leaving UC3 workflow playback, projection evidence, operator command, and
  live-provider activation to later slices. Verified with `uv run pytest
  tests/agent_runtime/test_runtime.py::test_runtime_passes_uc3_response_shape_to_provider_port
  tests/agent_runtime/test_runtime.py::test_uc3_policy_resolution_invokes_recorded_replay_route_versions
  tests/agent_runtime/test_runtime.py::test_uc3_policy_resolution_fails_without_matching_route_version
  tests/persistence/test_postgres_foundation.py::test_uc3_model_route_policies_are_seeded_with_route_versions
  tests/persistence/test_postgres_foundation.py::test_migrations_and_seeds_are_idempotent
  tests/persistence/test_postgres_foundation.py::test_agent_registry_roles_are_constrained_for_seeded_r4_agents
  tests/persistence/test_postgres_foundation.py::test_provider_catalogue_seed_uc1_model
  tests/test_contracts.py::test_generated_models_validate_representative_samples
  -q`, `just contracts-check`, `just db-migrate`, `just lint`, `just
  doctor`, and `git diff --check`.
- [x] Play UC3 happy-path and one branch fixture end-to-end through the
  running stack with tightened conduct invariants.
  Evidence (2026-05-30): `chorus/eval/uc3_workflow_playback.py` now mirrors
  the UC2 playback harness and plays UC3 eval fixtures through
  `Uc3IfaSuitabilityIntakeWorkflow` in a Temporal test environment with the
  real workflow activities, Agent Runtime, recorded-replay LLM provider route,
  Tool Gateway, decision/transcript persistence, tool-action audit,
  approval-package capture, and outbox workflow progress captured back into
  `CapturedRun`. The happy fixture now reaches `suitability_report.issue` and
  records the approval-required package path; new fixture
  `uc3_vulnerability_support_handoff_conduct.json` and
  `email_advice_enquiry_vulnerability_support.sample.json` drive the
  Consumer Duty vulnerability-support handoff branch to manual review without
  reaching report issue. UC3 conduct invariants now fail loudly when required
  workflow progress, agent decision, transcript, tool-action audit, or issue
  approval-package table evidence is missing, while keeping fixtures safe-ref
  only and bounded-category only. Focused coverage in
  `tests/eval/test_uc3_workflow_playback.py` proves both fixtures run through
  the workflow path and that missing evidence fails at the absent stage. Route
  version eval refs now include both UC3 fixtures. Docs were aligned in
  README, architecture, evidence-map, and runbook while leaving triggered-run
  projection evidence and the documented UC3 operator command to later P2
  slices. Verified with `uv run pytest
  tests/eval/test_uc3_workflow_playback.py
  tests/eval/test_run.py::test_uc3_invariant_suite_composes_common_and_conduct_modules
  tests/eval/test_run.py::test_uc3_conduct_invariants_pass_safe_synthetic_suitability_run
  tests/eval/test_run.py::test_uc3_conduct_invariants_fail_completed_suitability_without_issue_apply
  tests/eval/test_run.py::test_uc3_conduct_invariants_fail_positive_suitability_with_risk_mismatch
  tests/eval/test_run.py::test_uc3_manual_handoff_invariants_pass_vulnerability_support_branch
  tests/eval/test_run.py::test_uc3_schema_only_eval_fixture_validates_without_default_playback
  tests/eval/test_run.py::test_scenario_player_rejects_unsupported_uc3_scenario
  tests/workflows/test_uc3_workflow.py
  tests/agent_runtime/test_runtime.py::test_runtime_passes_uc3_response_shape_to_provider_port
  tests/agent_runtime/test_runtime.py::test_uc3_policy_resolution_invokes_recorded_replay_route_versions
  tests/tool_gateway/test_gateway.py::test_uc3_seeded_suitability_report_issue_requires_approval_and_applies
  tests/persistence/test_postgres_foundation.py::test_uc3_model_route_policies_are_seeded_with_route_versions
  -q`, `just contracts-check`, `just lint`, `just doctor`, and `git diff
  --check`.
- [x] Project UC3 workflow progress, decision trail, and approval-package
  state into BFF/UI with Playwright or frontend-test evidence.
  Evidence (2026-05-30): `tests/bff/test_app.py` now drives the UC3 happy
  suitability-report issue fixture through `play_uc3_workflow_fixture_async`,
  applies the emitted outbox workflow events to the existing projection read
  model within a two-second deterministic bound, and verifies the BFF exposes
  the triggered UC3 workflow summary, timeline steps through
  `suitability_report_issue`, decision-trail rows for all five UC3 workflow
  agent tasks, Tool Gateway audit rows for attitude-to-risk, capacity,
  platform research, report draft, and approval-required report issue, and
  the requested `suitability_report.issue.write` approval package with safe
  action refs. Frontend fixture and route coverage now render the same UC3
  progress, decision, audit, and approval-package state on the existing
  read-only workflow detail surface without adding a projection model,
  mutating approval UI, live-provider path, production connector, or workflow
  route DSL. Docs were aligned in README, architecture, evidence-map, and
  runbook while leaving the operator-facing UC3 command to the next P2 slice.
  Verified with `uv run pytest tests/bff/test_app.py
  tests/bff/test_app_unit.py
  tests/persistence/test_postgres_foundation.py::test_projection_store_lists_uc3_approval_package_state
  -q`, `uv run pytest tests/eval/test_uc3_workflow_playback.py -q`, `cd
  frontend && npm test -- --run src/api/queries.test.ts
  'src/routes/-workflows.$workflowId.test.tsx'`, `just contracts-check`,
  `just lint`, `just doctor`, and `git diff --check`.
- [ ] Document the UC3 runnable command.

### P3 — Live Provider Route Activation

- [ ] Implement a startup gate: when `model_routing_policies` selects a live
  route and the required credential env var is missing, the worker fails fast
  on boot with a specific error message naming the route and the missing
  credential. No fallback to recorded replay; no silent skip.
- [ ] Implement a focused integration test (gated on credentials being set)
  that drives UC1, UC2, and UC3 happy-path fixtures through the live OpenAI
  route end-to-end, captures the comparator record, and asserts the
  comparator outcome is one of {success, review-finding, metrics-only}, with
  hard-fail and decision-fail treated as test failures.
- [ ] Same integration test against the DeepSeek route.
- [ ] Wire the replay comparator into the live integration test so each live
  run produces a `replay_run_records` row joining the live transcript with
  the recorded-replay transcript.

### P4 — Closure

- [ ] Update README, runbook, evidence-map, architecture, ADRs to declare
  UC1, UC2, and UC3 all runnable, with current commands only. No historical
  references; no "as of R4" qualifiers. The docs describe the system that
  exists.
- [ ] Run the full gate matrix and capture green output: `just contracts-check`,
  `just lint`, `just doctor`, `just db-migrate`, `just test-replay`,
  `just eval`, `just test-frontend`, `uv run pytest`, and the credentials-gated
  live-provider integration test.
- [ ] Rewrite the body of `## Next Continuation Prompt` below to the literal
  `R5-COMPLETE`.

## Session Cadence

Codex drives R5 as a chain of `codex exec` sessions through this backlog. Each
session:

1. Reads `AGENTS.md`, this backlog, and the architecture authority order.
2. Runs `git status --short --branch` and preserves unrelated changes.
3. Picks the next unticked slice in Strategy order.
4. Implements the slice end-to-end including documentation alignment.
5. Runs the relevant gates and confirms they are green. Skipped gates are not
   acceptable in R5; if a gate genuinely cannot run, the session stops and
   surfaces the blocker without committing.
6. Updates checkboxes and evidence notes for the completed slice.
7. Rewrites the body of `## Next Continuation Prompt` below with the next
   slice's bounded prompt. If R5 is closed, writes the literal `R5-COMPLETE`
   wrapped in a `text`-fenced code block.
8. Stages everything and creates one Conventional Commit
   (`type(scope): description`). No AI attribution.

If a blocking design or product question appears mid-slice, the session stops
without committing and surfaces the question as the final response. The next
session is reprompted with the answer included.

## Next Continuation Prompt

```text
We are in /home/ryan/Work/chorus. Continue R5 P2 — UC3 To Runnable — by
documenting the UC3 local synthetic intake operator command.

Read AGENTS.md and docs/transformation/r5-implementation-backlog.md, then run
`git status --short --branch`. Preserve unrelated user changes.

Inspect the UC3 synthetic intake and the UC2 command documentation pattern
before editing: `just --list`, `justfile`,
`chorus/workflows/uc3_synthetic_intake.py`,
`chorus/workflows/uc2_synthetic_intake.py`, `chorus/workflows/worker.py`,
`tests/workflows/test_uc3_synthetic_intake.py`,
`tests/workflows/test_worker_registration.py`, `tests/bff/test_app.py`,
`docs/runbook.md`, `docs/evidence-map.md`, `docs/architecture.md`, and
`README.md`.

Implement the next narrow slice: document the exact UC3 operator command
`uv run python -m chorus.workflows.uc3_synthetic_intake`, the default
`contracts/intake/uc3/samples/email_advice_enquiry.sample.json` fixture, the
stable clean-database workflow ID `uc3-advice-3e7d1d3cd3d8236776a0fb8a`,
advice enquiry ref `advice_enquiry_advice_email_001`, correlation ID
`cor_advice_email_001`, duplicate `started: false` semantics, the bounded
`just relay-once` / `just project-once` evidence loop, and the BFF,
frontend, and Temporal inspection targets. Mirror the UC2 runbook and README
documentation shape closely.

Keep scope tight: do not add live provider credentials or live-provider tests,
do not add mutating approval or admin UI, do not add production connector
paths, do not add a generic workflow-route DSL, and do not run destructive
Docker/database operations. Update README, runbook, evidence-map,
architecture, and this backlog only for the documented UC3 operator command
status.

Run focused docs-alignment tests that prove the documented command is still
backed by code (`uv run pytest tests/workflows/test_uc3_synthetic_intake.py
tests/workflows/test_worker_registration.py tests/bff/test_app.py -q`), plus
`just contracts-check`, `just lint`, `just doctor`, and `git diff --check`.

End-of-session contract:
- Update checkboxes and evidence notes for the slice you completed.
- Rewrite the body of the `## Next Continuation Prompt` section in the
  backlog with the next slice's prompt, in Strategy order. If R5 is fully
  closed, write the literal `R5-COMPLETE` wrapped in a `text`-fenced code
  block.
- Run `git diff --check`, stage everything, and create one Conventional
  Commit. No AI attribution. Leave the working tree clean.

If a blocking decision the prompt does not cover comes up, stop without
committing or touching checkboxes. Surface the question clearly as the final
content of your response.
```
