---
type: project-doc
status: design-freeze
date: 2026-04-29
---

# Chorus - 3-Minute Demo Script

## Goal

Show that Chorus is a production-shaped governed agent workflow and enterprise architecture artefact set, not a prompt demo. The audience should leave with a clear answer to: who owns state, who grants authority, what happened, how failures are handled, how behaviour is checked, and how runtime governance is enforced.

## Setup Assumptions

- Local stack is already running: `just up`.
- The local stack is migrated and schemas are registered: `just db-migrate` and `just schemas-register`.
- `just doctor` is green for the services that are up.
- The Lighthouse worker is running through Compose or with `just worker`.
- Browser tabs are open for Lighthouse UI, Mailpit, Temporal Console, Redpanda Console, Grafana, and the eval result.
- The demo tenant exists and the fixture lead email is ready to send through Mailpit.
- No editor is required during the walkthrough.

Useful tabs:

- Lighthouse UI: `http://localhost:5173`
- Mailpit: `http://localhost:8025`
- Temporal UI: `http://localhost:8233`
- Redpanda Console: `http://localhost:8080`
- Grafana: `http://localhost:3001`

If ports are overridden in `.env`, use the matching values from
[`runbook.md`](runbook.md).

## Walkthrough

| Time | Screen | Action | Point to make |
|---|---|---|---|
| 0:00-0:20 | README or evidence map | State the claim and show the artefact set: working slice plus architecture, guardrails, decision record, and evidence map. | "This is both a governed workflow implementation and an adoption pattern an enterprise architecture team can inspect." |
| 0:20-0:40 | Mailpit + Lighthouse UI | Run `just demo`, `just intake-once`, `just relay-once`, and `just project-once`; copy/open the workflow correlation ID. | A real SMTP intake event starts a durable workflow, not a loose chain of prompts or a hand-fed form. |
| 0:40-1:05 | Temporal Console | Show intake, research/qualification, drafting, validation, and propose/send or escalation states. | Temporal owns retries, waits, replay, and branches. |
| 1:05-1:30 | Lighthouse decision trail | Open the agent invocation details. | Each step records agent version, prompt hash, model route, input/output summary, justification, cost, duration, and correlation ID. |
| 1:30-1:55 | Tool verdict/audit view | Show the `email.propose_response` proposal verdict and the redacted audit row. | Agents do not hold ambient authority; gateway grants and argument schemas decide action permissions. |
| 1:55-2:15 | Redpanda Console and Grafana | Show emitted events and correlated traces/metrics. | Events, projections, and telemetry are inspectable by the same correlation ID. |
| 2:15-2:35 | Eval result | Run `just eval`; optionally rerun with `CHORUS_EVAL_CORRELATION_ID=<correlation-id> just eval` for persisted evidence assertions. | The system checks behaviour, not just output text. |
| 2:35-2:50 | Governance docs | Show the guardrail matrix and quality gates. | The controls are inspectable as runtime and release gates: contracts, replay, runtime governance, safety/eval, observability, docs. |
| 2:50-3:00 | Architecture or ADR index | Close on deliberate deferrals. | Phase 1 is narrow by design: real connectors, Scylla, production auth, and extra workflows are deferred so the core boundaries are credible. |

## Happy-Path Command Flow

Run these from the repo root before or during the walkthrough:

```zsh
just up && just db-migrate && just schemas-register && just doctor
just demo && just intake-once
just relay-once && just project-once
just eval
```

After projection, take the `correlation_id` from the Lighthouse workflow detail
page, BFF response, or Postgres. Reuse that value in every inspection surface:

- UI workflow detail, decision trail, tool verdicts, registry, grants, and routing.
- Temporal UI workflow search by workflow ID.
- Redpanda Console topic `chorus.workflow.events.v1`.
- Grafana dashboard `$correlation` variable.
- Postgres `decision_trail_entries` and `tool_action_audit`.

For live persisted evidence assertions:

```zsh
CHORUS_EVAL_CORRELATION_ID=<correlation-id> just eval
```

This default live assertion is for the happy-path demo run. Use
`uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/<fixture>.json`
when asserting a live governance/failure fixture.

## Evidence To Point At

- **State owner:** Temporal workflow history and `chorus/workflows/lighthouse.py`.
- **Authority owner:** Tool Gateway verdict and `tool_action_audit`, not agent prompt text.
- **Runtime governance:** registry, routing, grant tables, and decision-trail rows.
- **Projection path:** outbox row -> Redpanda event -> `workflow_read_models`/`workflow_history_events`.
- **Release check:** `chorus/eval/fixtures/*.json` through `just eval`.

Screenshot or screencast stills are optional packaging artefacts. The canonical
review path is this script plus [`evidence-map.md`](evidence-map.md) and
[`governance-evidence.md`](governance-evidence.md).

## Phase 1B Failure Fixtures

- Low-confidence research routes to deeper research.
- Validator rejects a draft and loops back with structured reason.
- Local connector failure triggers retry then compensation or escalation.
- Forbidden write is blocked or downgraded to proposal mode.
- Retry exhaustion records terminal DLQ evidence and escalates.

These fixtures are shipped Phase 1B evidence. The live 3-minute path still
leads with the happy-path proposal verdict because it is the shortest way to
show the full runtime topology; [`governance-evidence.md`](governance-evidence.md)
packages the follow-up failure-fixture inspection.

## Fallback for Screencast Recording

If a live local service is slow, use `just eval` to show the deterministic
fixture set and say plainly that the live evidence inspection requires
Postgres, Mailpit, Temporal worker, Redpanda relay/projection, and the BFF/UI
stack to be running. The evidence point is repeatability: workflow events,
decision records, gateway audit, budgets, latency, and correlation IDs must
line up.
