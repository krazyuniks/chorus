---
type: project-doc
status: design-freeze
date: 2026-04-29
---

# Chorus - 3-Minute Demo Script

## Goal

Show that Chorus is a production-shaped governed agent workflow and enterprise architecture artefact set, not a prompt demo. The audience should leave with a clear answer to: who owns state, who grants authority, what happened, how failures are handled, how behaviour is checked, and how the pattern fits SDLC governance.

## Setup Assumptions

- Local stack is already running.
- Browser tabs are open for Lighthouse UI, Mailpit, Temporal Console, Redpanda Console, Grafana, and the eval result.
- The demo tenant exists and the fixture lead email is ready to send through Mailpit.
- No editor is required during the walkthrough.

## Walkthrough

| Time | Screen | Action | Point to make |
|---|---|---|---|
| 0:00-0:20 | README or evidence map | State the claim and show the artefact set: working slice plus architecture, guardrails, decision record, and SDLC model. | "This is both a governed workflow implementation and an adoption pattern an enterprise architecture team can inspect." |
| 0:20-0:40 | Mailpit + Lighthouse UI | Send the fixture email to `leads@chorus.local` through Mailpit and copy/open the workflow correlation ID. | A real SMTP intake event starts a durable workflow, not a loose chain of prompts or a hand-fed form. |
| 0:40-1:05 | Temporal Console | Show intake, research/qualification, drafting, validation, and propose/send or escalation states. | Temporal owns retries, waits, replay, and branches. |
| 1:05-1:30 | Lighthouse decision trail | Open the agent invocation details. | Each step records agent version, prompt hash, model route, input/output summary, justification, cost, duration, and correlation ID. |
| 1:30-1:55 | Tool verdict/audit view | Show an allowed tool action, then the blocked or downgraded write fixture. | Agents do not hold ambient authority; gateway grants and argument schemas decide action permissions. |
| 1:55-2:15 | Redpanda Console and Grafana | Show emitted events and correlated traces/metrics. | Events, projections, and telemetry are inspectable by the same correlation ID. |
| 2:15-2:35 | Eval result | Show passing trace/eval checks for happy path and governance failure fixtures. | The system checks behaviour, not just output text. |
| 2:35-2:50 | Governance/SDLC docs | Show the guardrail matrix and quality gates. | The same controls become SDLC gates: contracts, replay, runtime governance, safety/eval, observability, docs. |
| 2:50-3:00 | Architecture or ADR index | Close on deliberate deferrals. | Phase 1 is narrow by design: real connectors, Scylla, production auth, and extra workflows are deferred so the core boundaries are credible. |

## Failure Fixtures to Keep Ready

- Low-confidence research routes to deeper research.
- Validator rejects a draft and loops back with structured reason.
- Local connector failure triggers retry then compensation or escalation.
- Forbidden write is blocked or downgraded to proposal mode.

## Fallback for Screencast Recording

If a live model call or local service is slow, use a committed trace fixture for the same workflow ID and say so plainly. The evidence point is repeatability: the recorded trace, audit rows, events, and eval assertions must still line up.
