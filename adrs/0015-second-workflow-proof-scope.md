---
type: adr
status: accepted
date: 2026-05-18
---

# ADR 0015 - Phase 2D Second Workflow Proof Scope

## Context

Phase 1 proved one evidence-grade workflow, Lighthouse. Phase 2A added
LangGraph inside Agent Runtime, Phase 2B made identity/authority/observability
boundaries explicit, and Phase 2C proved a local CalDAV connector and
approval-hardening path behind the Tool Gateway.

Phase 2D now needs to prove that Chorus can support a second business workflow
without turning into a generic workflow DSL, replacing Temporal, or weakening
the Lighthouse baseline. The second workflow should be close enough to reuse
the existing local stack, but different enough to test workflow-specific
contracts, eval, replay, projections, and tool authority.

## Decision

Phase 2D will use a local **Support Desk Triage** workflow as the second
business workflow proof.

The workflow is an adjacent operational process:

```text
support request intake
  -> classification and severity triage
  -> account or case context lookup
  -> resolution plan
  -> response and case-update draft
  -> validation
  -> propose response / propose case update
  -> complete or escalate
```

The workflow type should be represented as `support_triage` in contracts,
workflow events, telemetry, projections, eval fixtures, and replay artefacts
when those are later implemented.

The intended local connector shape is a Postgres-backed local ticket desk
sandbox behind the Tool Gateway. Initial runtime work should prefer `read` and
`propose` modes: case lookup, duplicate-case lookup, and proposed case update.
Any local write action, such as case creation or status mutation, must start as
approval-required and remain local-only until a later ADR explicitly changes
the boundary.

## Non-Goals

This decision does not add:

- second-workflow runtime code;
- contracts, generated models, samples, migrations, seeds, eval fixtures, or
  replay histories;
- BFF routes, UI routes, reviewer decision UI, or a mutating admin surface;
- production ticketing, CRM, mailbox, calendar, identity-provider, or cloud
  integrations;
- credential entry, credential mutation, OAuth, production SSO, or AWS;
- production provider calls or production connector writes;
- hosted observability dependencies or a sidecar exporter;
- a generic workflow DSL, workflow builder, or top-level agent framework
  replacing Temporal.

## Reuse Boundaries

Support Desk Triage must reuse the existing Chorus boundaries:

| Boundary | Reuse expectation |
|---|---|
| Temporal | Owns durable `support_triage` workflow state, retries, timers, branches, compensation, and replay. The workflow is code-defined, not DSL-defined. |
| Agent Runtime | Resolves support-specific agent versions, prompt refs, model routes, budget caps, invocation IDs, graph execution metadata, provider fallback, and decision-trail records. |
| LangGraph | Remains inside Agent Runtime as the per-invocation execution graph. It does not own support workflow state or connector authority. |
| Tool Gateway | Owns support-ticket and email tool grants, argument validation, mode enforcement, approval hooks, idempotency, redaction, connector invocation, verdicts, and audit. |
| Postgres | Stores workflow projections, decision trail, tool audit, local ticket desk state if later promoted, and outbox rows. |
| Redpanda | Carries schema-governed workflow events for projection and visibility, not critical workflow state. |
| BFF/UI | Exposes read-only support workflow inspection when implemented. It does not mutate workflow state, grant tools, or call connectors. |
| Eval/replay | Gates support behaviour with workflow-specific fixtures while keeping existing Lighthouse gates intact. |
| Observability | Uses existing OTel/Grafana field placement with `chorus.workflow.type=support_triage` and safe join IDs. |

Pure helper code may be shared where it reduces duplication, but the support
workflow must stay a code-defined Temporal workflow with its own contracts,
replay histories, and eval fixtures. Reuse is proven through shared platform
boundaries, not through a generic workflow interpreter.

## Required Contracts

Future 2D implementation must add contract changes before runtime behaviour.
The expected contract set is:

| Contract area | Expected shape |
|---|---|
| Support intake | A support request intake event or workflow input containing stable refs, bounded categories, request source refs, and redacted summary refs. Samples must not include raw request bodies, names, email addresses, account secrets, or PII. |
| Support agent IO | Agent input/output for classification, severity, resolution planning, drafting, and validation. Outputs use bounded decisions such as `continue`, `redraft`, `escalate`, or `propose_only`. |
| Ticket tool arguments | Tool args for local case lookup, duplicate lookup, proposed case update, and any later approval-required local write. Arguments use `case_ref`, `account_ref`, `request_ref`, `product_ref`, `severity_category`, `case_status_category`, and idempotency refs only. |
| Workflow events | Existing workflow-event schema must represent `workflow_type=support_triage`, support-specific step names, and safe metadata categories. |
| Eval fixtures | Fixture contracts must allow support workflow IDs, expected path, expected outcome, required decision-trail/tool-audit evidence, cost/latency bounds, and safe failure categories. |

Contract samples must use only safe refs and bounded categories. They must not
carry secrets, credentials, API keys, access tokens, raw sensitive content, raw
prompts/outputs, raw tool arguments, raw connector payloads, raw approval or
policy rationale, identity-provider claims, attendee names, email addresses, or
PII.

## Replay and Eval Expectations

Support workflow runtime work is not delivered until it has its own evidence:

- a happy-path replay history for a deterministic `support_triage` run;
- focused replay coverage for any support-specific branches introduced by the
  workflow implementation;
- an eval fixture that proves the support request path, final outcome,
  decision-trail completeness, Tool Gateway verdicts, cost/latency bounds, and
  correlation joins;
- at least one governance or failure fixture, such as low-confidence triage,
  validator redraft, denied ticket write, transient local ticket connector
  failure, or retry exhaustion, once the corresponding branch exists;
- no regression to existing Lighthouse eval and replay gates.

Replay and eval evidence should be added only when runtime behaviour changes.
This ADR adds no replay histories or eval fixtures.

## Projection, Audit, and Observability Surfaces

The support workflow needs read-only inspection surfaces comparable to
Lighthouse, but not a mutating admin product.

Projection categories should be bounded, for example:

```text
support_request_received
support_triage_classified
support_context_lookup_completed
support_response_proposed
support_case_update_proposed
support_validation_failed
support_escalated
support_completed
```

Audit and projection data may expose safe refs such as `request_ref`,
`case_ref`, `account_ref`, `product_ref`, `workflow_id`, `correlation_id`,
`invocation_id`, `tool_name`, requested/enforced mode, verdict, grant/policy
refs, idempotency key refs, retry/failure categories, and trace joins.

They must not expose raw request content, raw prompts/outputs, raw tool
arguments, raw connector payloads, raw approval or policy rationale,
identity-provider claims, personal names, email addresses, credentials, access
tokens, API keys, or PII.

OpenTelemetry may carry the existing safe join and bounded category fields:
tenant, correlation, workflow ID, workflow type, workflow step, invocation ID,
agent ID/version, route/provider/model IDs, graph version, tool name, mode,
gateway verdict, fallback state/reason, fixture ID, and bounded failure
category. Propagated baggage remains limited to the 2B-01 allow-list.

## Runbook and Evidence Map Expectations

Before Support Desk Triage runtime work is called complete, the runbook must
document:

- how to run or inspect the support workflow through local-only fixtures;
- how to prove that Lighthouse remains the default demo baseline;
- how to inspect support workflow projections, decision trail, tool audit,
  provider/graph evidence, and safe trace joins;
- how to verify that no production ticketing provider, credential entry,
  production connector write, hosted sidecar, or workflow DSL was added;
- which contract, replay, eval, runtime, BFF/UI, and docs gates apply.

The evidence map must point from the second-workflow claim to this ADR, the
future contracts, workflow code, replay histories, eval fixtures, projection
paths, BFF/UI read-only inspection paths, and runbook procedures as they are
implemented. Until runtime work lands, the evidence map should state that only
scope selection is complete.

## Lighthouse Baseline

Lighthouse remains the stable Phase 1 demo and regression baseline.

Support Desk Triage must not rename or weaken existing Lighthouse activity
boundaries, eval fixtures, replay histories, BFF routes, UI routes, runbook
procedures, or demo scripts. If a shared helper or generic activity wrapper is
introduced later, the change must keep Lighthouse replay-compatible or include
explicit replay coverage and migration notes.

The normal review path continues to start with Lighthouse. Support Desk Triage
becomes additional reuse evidence only after it has its own contracts, replay,
eval, projections, audit, observability, and read-only inspection path.

## Consequences

- Phase 2D has a concrete adjacent workflow scope before code.
- The next implementation item can start with contract-only support workflow
  schemas and safe samples instead of debating the workflow candidate.
- The selected workflow tests a different operational lifecycle from
  Lighthouse while reusing the same governance spine.
- Ticketing remains local-only and gateway-mediated. Production ticketing,
  credential entry, reviewer decisions, mutating admin UI, and cloud deployment
  remain deferred.
- A workflow DSL remains rejected until at least two code-defined workflows
  show which duplication is real and worth abstracting.

## Alternatives Considered

### Extend Lighthouse with a calendar branch

Rejected for the second workflow proof. It would exercise the 2C calendar
connector, but it would still be Lighthouse and would not prove a second
workflow boundary.

### Add a sales renewal or onboarding workflow

Deferred. These are adjacent to Lighthouse but risk reusing the same lead
qualification and drafting shape too closely. Support triage adds a different
case lifecycle, severity classification, duplicate-case check, and escalation
surface.

### Add a production ticketing connector first

Rejected. A production connector would force credentials, tenancy, identity,
and production write questions before the second workflow has proved local
contracts, replay, eval, and audit.

### Build a generic workflow DSL first

Rejected. ADR 0002 and ADR 0011 keep Temporal as the durable orchestration
owner. The second workflow should be code-defined so the project can learn from
real duplication before introducing an abstraction.
