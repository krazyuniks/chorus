---
type: adr
status: accepted
date: 2026-05-14
---

# ADR 0013 - Identity, Authority, and Observability Boundaries

## Context

Phase 1 and Phase 2A proved the governed execution spine: Temporal owns
durable workflow state, Agent Runtime resolves invocation identity and model
route policy, LangGraph runs inside that runtime boundary, Tool Gateway owns
external action authority, and Postgres plus eval fixtures provide evidence.

Phase 2B opens runtime change control and human approval work. That cannot
start with a generic "admin" model or a vague observability bucket. Chorus
needs separate concepts for identity, authority, infrastructure telemetry,
application journey evidence, and audit accountability. The local reference
implementation also needs to preserve a clean future mapping to AWS IAM without
implementing AWS, production SSO, or hosted observability in the local path.

## Decision

Define the Phase 2B boundary model before adding mutating runtime controls.

### Identity Model

Chorus distinguishes six principal types:

| Principal | Meaning | Local evidence | Future production mapping |
|---|---|---|---|
| Human principal | A person using the BFF/UI, approving actions, or proposing policy changes. | Deferred in local Phase 1/2A; planned as local subject/session metadata, not production SSO. | OIDC/SAML subject, AWS IAM Identity Center user/group, RBAC role. |
| Workload principal | A running Chorus service or worker. | Compose service name, service namespace, deployment environment, OTel resource attributes. | ECS task role, EKS pod identity, Lambda execution role, EC2 instance profile, IAM Roles Anywhere, or SPIFFE/SPIRE identity. |
| Agent principal | A governed logical agent version selected for a tenant and task. | `agent_registry` rows with tenant, role, version, lifecycle, prompt reference/hash, owner, and capability tags. | Application-level principal, optionally expressed as IAM session tags or policy attributes. |
| Invocation principal | One authorised agent invocation inside a workflow context. | `invocation_id`, `workflow_id`, `correlation_id`, agent version, prompt hash, route, budget, graph metadata, and decision trail. | Short-lived authority token or STS session context with tenant, workflow, agent, task, route, budget, and expiry tags. |
| Approval actor | A human or system deciding an approval-required action. | Currently only represented by `approval_required` gateway verdicts. | Signed approval package with reviewer subject, role, decision, expiry, and audit row. |
| Policy actor | A human or automation proposing, approving, applying, or rolling back runtime policy changes. | Direct seeded/config mutation in local evidence. | Change-control workflow with proposer, approver, reason, rollback, eval evidence, and immutable audit. |

The local identity model remains provider-neutral. It must not require AWS,
production SSO, production tenant administration, or long-lived provider
credentials.

### Authority Model

Authentication and business authority are separate.

Workload authentication proves which service called another service. Chorus
business authority decides whether a specific tenant, agent version, invocation,
tool, mode, route, budget, approval state, and policy version allow the action.

Tool Gateway remains the enforcement point for external actions. Agent Runtime
remains the enforcement point for agent version, prompt, model route, graph,
provider, and budget selection. Temporal remains the durable owner of workflow
state. No identity mechanism may give agents ambient connector authority.

Future Phase 2B implementation should bind authority context to stable domain
identifiers:

- `tenant_id`
- `correlation_id`
- `workflow_id`
- `invocation_id`
- `agent_id`
- `agent_version`
- `task_kind`
- `provider`
- `model`
- `route_id`
- `route_version`
- `budget_cap_usd`
- `tool_name`
- `mode`
- `approval_id`
- `policy_change_id`
- expiry and parent-invocation metadata where applicable

### AWS Mapping

AWS IAM is a future mapping target, not a local dependency.

In an AWS deployment, workload principals can map to IAM roles attached to ECS
tasks, EKS pods, Lambda functions, EC2 instances, or IAM Roles Anywhere role
sessions. Human principals can federate through an identity provider into IAM
Identity Center or application RBAC. Invocation and agent authority should
remain Chorus application policy and may be reflected into role session names,
session tags, external IDs, or signed local authority tokens.

IAM constrains cloud-resource access. It does not replace Tool Gateway grants,
Agent Runtime route governance, approval audit, policy mutation audit, or eval
release gates.

### Observability Planes

Chorus separates three default planes plus one optional sidecar plane:

| Plane | Answers | Canonical local surface | Boundary |
|---|---|---|---|
| Infrastructure telemetry | Is the platform healthy? | OpenTelemetry, Grafana, Tempo, Loki, Prometheus, service logs, health checks. | Non-authoritative; traces can be sampled, expired, or exported. |
| Application and user journey evidence | Which workflow, reviewer, fixture, or UI path was followed? | Workflow projections, BFF/UI read models, fixture replay context, future actor/session records. | Safe projection data only; no secrets, credentials, raw sensitive content, or enforcement decisions. |
| Audit/accountability | Who or what was authorised to do which authority-sensitive action under which policy? | Postgres decision trail, tool action audit, future approval audit, future policy mutation audit. | Canonical accountability store; not replaced by traces or hosted observability. |
| Optional LLM observability sidecar | How did prompt/model/graph behaviour compare across runs? | Future export to LangSmith, Langfuse, or similar tools if explicitly approved. | Optional derived data only; not a release gate or audit store. |

All planes share `correlation_id` and relevant domain IDs. Telemetry also
records `trace_id` and `span_id`, but audit must remain queryable without
trace retention.

### Context Hygiene

Propagated trace context must be conservative. `traceparent` and `tracestate`
may cross trusted service boundaries. Baggage or equivalent propagated context
must not carry secrets, API keys, access tokens, credentials, raw customer
content, or PII. Connector boundaries should filter outgoing trace headers and
baggage according to the connector trust policy.

## Consequences

- Phase 2B starts with identity, authority, and observability boundary design
  before mutating admin flows.
- The local implementation stays self-contained: no AWS dependency, production
  SSO, hosted observability, credential entry, or production provider calls are
  introduced by this ADR.
- Future approval, policy mutation, and provider governance work has a stable
  vocabulary for human, workload, agent, invocation, approval, and policy
  actors.
- The architecture keeps Postgres audit and eval gates authoritative even if
  LLM observability sidecars are evaluated later.
- AWS IAM can be mapped later without moving business grants into cloud IAM or
  prompts.

## Alternatives Considered

### Use AWS IAM as the Primary Local Identity Model

Rejected. It would make the local reference implementation depend on cloud
accounts, production-shaped secrets, and deployment mechanics before Chorus has
proved the application-level authority model.

### Treat Observability as a Single Data Plane

Rejected. Service health, user journey reconstruction, and accountability have
different retention, sensitivity, and authority semantics. Combining them would
make traces look more authoritative than they are or make audit tables carry
operational noise.

### Use an LLM Observability Tool as the Accountability Store

Rejected. LangSmith, Langfuse, and similar tools can be useful derived
inspection surfaces, but they must not replace Postgres audit, Tool Gateway
verdicts, Temporal replay, or `just eval`.

### Give Agents Cloud or Connector Identity Directly

Rejected. Agents are governed logical principals. They do not receive ambient
cloud credentials or connector authority. Tool Gateway and Agent Runtime remain
the enforcement boundaries.
