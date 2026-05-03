---
type: project-doc
status: phase-1c
date: 2026-05-01
---

# Chorus - Governance Evidence

## Purpose

This page packages the Phase 1B governance and failure evidence for reviewers.
It complements the happy-path walkthrough in [`demo-script.md`](demo-script.md)
by showing how Chorus proves that failure handling and authority controls are
implemented paths, not architecture-diagram claims.

## Review Order

1. Run `just eval` to execute the deterministic happy-path and governance
   fixtures.
2. Run `just test-replay` to prove the recorded Temporal histories replay
   deterministically.
3. Open [`evidence-map.md`](evidence-map.md) for claim-to-artefact links.
4. Use the fixture rows below to inspect the specific workflow branch, eval
   file, replay history, and audit evidence.

The fixtures are intentionally narrow. Each one exercises one governance
question end-to-end: what signal caused the branch, who owned the decision,
which durable evidence was written, and which release gate catches regression.

## Governance Fixture Matrix

| Fixture | Governance question | Trigger | Durable evidence | Gate |
|---|---|---|---|---|
| Low-confidence research | Does weak research loop into deeper research before qualification? | Researcher returns `recommended_next_step="deeper_research"` or sub-threshold confidence. | Workflow history shows a second `research_qualification` pass; decision trail shows two researcher invocations, including enriched second-pass input. | `just eval`; `just test-replay` |
| Validator redraft | Can unsafe or weak output be rejected before customer-facing proposal? | Validator returns `recommended_next_step="redraft"` with a structured reason. | Workflow history loops `draft -> validation -> draft -> validation`; drafter input receives `validator_reason`; eval asserts final proposal only after validation passes. | `just eval`; `just test-replay` |
| Forbidden write | Are agents prevented from exercising authority they do not hold? | `tenant_demo_alt` has an explicit denied `email.send_response/write` grant. | Tool Gateway records a `block` verdict and redacted `tool_action_audit`; workflow escalates rather than sending. | `just eval`; `just test-replay`; `just test-persistence` |
| Connector failure | Are connector faults classified, retried, and made visible? | Fixture email causes the Mailpit connector path to raise `ConnectorTransientError`. | Gateway audits transient failures without caching idempotency; workflow records `connector.failure.compensated` audit evidence and escalates after retry. | `just eval`; `just test-replay` |
| Retry exhaustion DLQ | Is retry exhaustion visible outside logs? | Fixture email causes persistent Agent Runtime activity failure during research. | Workflow writes `workflow.failed`; activity writes a terminal outbox row with status `dlq` and `workflow.retry_exhausted.dlq_recorded` audit evidence; workflow escalates. | `just eval`; `just test-replay`; `just test-persistence` |

## Artefact Index

| Fixture | Eval fixture | Replay history | Fixture email |
|---|---|---|---|
| Low-confidence research | [`../chorus/eval/fixtures/lighthouse_low_confidence.json`](../chorus/eval/fixtures/lighthouse_low_confidence.json) | [`../tests/workflows/fixtures/lighthouse_low_confidence_history.json`](../tests/workflows/fixtures/lighthouse_low_confidence_history.json) | [`fixtures/lead-low-confidence.eml`](fixtures/lead-low-confidence.eml) |
| Validator redraft | [`../chorus/eval/fixtures/lighthouse_validator_redraft.json`](../chorus/eval/fixtures/lighthouse_validator_redraft.json) | [`../tests/workflows/fixtures/lighthouse_validator_redraft_history.json`](../tests/workflows/fixtures/lighthouse_validator_redraft_history.json) | [`fixtures/lead-validator-redraft.eml`](fixtures/lead-validator-redraft.eml) |
| Forbidden write | [`../chorus/eval/fixtures/lighthouse_forbidden_write.json`](../chorus/eval/fixtures/lighthouse_forbidden_write.json) | [`../tests/workflows/fixtures/lighthouse_forbidden_write_history.json`](../tests/workflows/fixtures/lighthouse_forbidden_write_history.json) | [`fixtures/lead-acme.eml`](fixtures/lead-acme.eml) with `tenant_demo_alt` |
| Connector failure | [`../chorus/eval/fixtures/lighthouse_connector_failure.json`](../chorus/eval/fixtures/lighthouse_connector_failure.json) | [`../tests/workflows/fixtures/lighthouse_connector_failure_history.json`](../tests/workflows/fixtures/lighthouse_connector_failure_history.json) | [`fixtures/lead-connector-failure.eml`](fixtures/lead-connector-failure.eml) |
| Retry exhaustion DLQ | [`../chorus/eval/fixtures/lighthouse_retry_exhaustion.json`](../chorus/eval/fixtures/lighthouse_retry_exhaustion.json) | [`../tests/workflows/fixtures/lighthouse_retry_exhaustion_history.json`](../tests/workflows/fixtures/lighthouse_retry_exhaustion_history.json) | [`fixtures/lead-retry-exhaustion.eml`](fixtures/lead-retry-exhaustion.eml) |

## What This Proves

- Temporal remains the owner of long-running state, retries, deterministic
  replay, and branch history.
- Agent outputs are advisory signals; workflow logic decides bounded loops and
  escalation.
- Tool authority is enforced by the Tool Gateway using grants and generated
  schemas, outside prompt text.
- Failure evidence is durable in Postgres audit, outbox, replay histories, and
  eval fixtures.
- Release control covers both success and failure behaviours through `just
  eval`, replay tests, contract checks, and persistence tests.

## What This Does Not Claim

These fixtures do not imply production identity, real third-party writes,
provider incident handling, or a general workflow DSL. Those remain explicit
Phase 1 deferrals in [`architecture.md`](architecture.md).
