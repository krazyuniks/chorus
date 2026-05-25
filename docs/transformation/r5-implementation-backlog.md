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
- UC2 and UC3 have intake and connector contracts, shared-spine workflow
  definitions, deterministic sandbox connector adapters, Tool Gateway grants,
  approval-package evidence (`engagement_letter.send`, `suitability_report.issue`),
  conduct invariants, read-only projection/BFF/UI inspection evidence, and
  schema-only eval fixtures. They do **not** have:
  - a documented local intake start path,
  - use-case-specific model route policies,
  - full eval fixture playback against the runtime.
- The OpenAI-compatible provider adapter is hardened (prompt loading, prompt
  hash, response schema, structured output, route-governance alignment,
  replay-run records, tiered comparator). Live OpenAI and DeepSeek routes are
  credential-gated and inactive by default.
- The Compose stack runs against Postgres on host `:55432` and Redpanda on
  `:19092`. Tests load `.env` automatically through `tests/conftest.py`.
- 165 pytest cases pass against the running stack, including all DB-backed
  persistence, BFF, agent-runtime, and tool-gateway suites.

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
- [ ] Per-service pyprojects under `services/*/` are kept in sync with the
  runtime imports of the `chorus` package by an automated check.
- [ ] `.env.example` declares the same keys with the same values as `.env`;
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
- [ ] `just doctor` verifies stack health (postgres, redpanda, mailpit,
  radicale, temporal) and refuses to report success when any container is in a
  restart loop, any port is unreachable, or any migration is unapplied.
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
- [ ] Add `just doctor` (or extend it) to verify, before any other gate:
  postgres reachable at the URL in `.env`, redpanda bootstrap reachable, all
  declared migrations applied, all Compose containers in `running` or
  `healthy` state, no container with `RestartCount > 0` since boot. Fail loud
  on any divergence.
- [ ] Add a contract check that fails CI when a runtime import in the
  `chorus` package needs a dependency not declared in the per-service
  pyproject that consumes it. Either auto-derive per-service deps from the
  imports or assert the set is the same.
- [ ] Add a `.env` / `.env.example` drift check to `just lint`. The two files
  must declare the same keys; values may differ only for explicitly listed
  secret keys (API keys, passwords).
- [x] Replace the per-test hardcoded Postgres URL fallbacks with a single
  shared helper that reads from environment only and fails loud when the
  variable is unset.
  Evidence (2026-05-25): completed as part of the skip-removal slice. DB-backed
  tests now use the shared `migrated_database_url` fixture in `tests/conftest.py`;
  `CHORUS_TEST_ADMIN_DATABASE_URL` is required and no test module keeps a
  hardcoded Postgres URL fallback.
- [ ] Document the local development bootstrap end-to-end in
  `docs/runbook.md`: how to bring the stack up, how `tests/conftest.py` picks
  the URLs up, what to do when migrations drift, what to do when an image
  needs rebuilding after a dependency change.

### P1 — UC2 To Runnable

- [ ] Add the UC2 local intake adapter that turns a documented synthetic
  intake artefact into a `start_workflow` call on the shared `WorkflowSpine`.
  Mirror the structure of the existing UC1 Mailpit intake path: a small
  poller or one-shot command that consumes a fixture, validates it against
  `contracts/intake/uc2/`, and starts the workflow with safe correlation
  fields populated.
- [ ] Seed a UC2 model route policy that selects the recorded-replay route by
  default and the OpenAI route when credentials are present. Wire the policy
  through `model_routing_policies` and `model_route_versions` with the same
  governance shape as UC1.
- [ ] Play UC2 happy-path and one branch fixture end-to-end through the
  running stack. The fixtures must drive the actual workflow code path, not
  synthetic captured-run artefacts only. Tighten `chorus/eval/use_cases/uc2_conduct.py`
  invariants so they fail loudly on missing evidence at any stage.
- [ ] Project UC2 workflow progress, decision trail, and approval-package
  state into the existing BFF/UI surfaces with the same density and behaviour
  as UC1. Confirm via Playwright or a focused frontend test that a triggered
  UC2 workflow appears in projection within a deterministic bound.
- [ ] Document the UC2 runnable command in `docs/runbook.md` and the README
  with the exact one-liner used to start it locally.

### P2 — UC3 To Runnable

- [ ] Add the UC3 local intake adapter following the same pattern as P1.
- [ ] Seed a UC3 model route policy following the same pattern as P1.
- [ ] Play UC3 happy-path and one branch fixture end-to-end through the
  running stack with tightened conduct invariants.
- [ ] Project UC3 workflow progress, decision trail, and approval-package
  state into BFF/UI with Playwright or frontend-test evidence.
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
We are in /home/ryan/Work/chorus. Continue R5 P0 — Infrastructure
Prerequisites And Gate Hygiene — by extending `just doctor` so stack health is
verified before any other gate.

Read AGENTS.md and docs/transformation/r5-implementation-backlog.md, then run
`git status --short --branch`. Preserve unrelated user changes.

Inspect the current command surface before editing: `just --list`, `justfile`,
doctor-related scripts/modules under `scripts/`, `chorus/doctor/`, compose
configuration, migration code, and docs/runbook.md. Use `scripts/dc` or
existing `just` recipes for Compose interaction; do not run destructive Docker,
volume, database, reset, or checkout commands.

Implement or extend `just doctor` so it fails loudly when any required local
stack prerequisite is unhealthy: Postgres reachable at the URL in `.env`,
Redpanda bootstrap reachable, Mailpit reachable, Radicale reachable, Temporal
reachable, declared migrations applied, all Compose containers in `running` or
`healthy` state, and no container has `RestartCount > 0` since boot. Prefer
small, testable checks in the existing doctor boundary; do not widen runtime
behaviour unless the current doctor code requires a narrow helper.

Add focused tests for the doctor health checks, update docs/runbook.md if
commands or failure modes change, and run the relevant focused pytest targets,
`just doctor`, `just lint`, and `git diff --check`. If the local stack is not
running or an existing runtime path silently swallows an infrastructure error,
stop without committing or touching checkboxes and surface the blocker.

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
