---
type: adr
status: proposed
date: 2026-04-29
---

# ADR 0009 — Local-only operating model for Phase 1

## Status

Proposed — 2026-04-29. Awaiting architect review.

## Context

Phase 1 of Chorus is a public reference implementation, not a deployable product. The implementation plan already lists production cloud deployment, real third-party connectors, production auth/SSO, Scylla storage, and backup/disaster-recovery automation as deferrals. ADRs 0001–0008 cover the architectural shape (evidence-first scope, durable orchestration, event visibility, agent runtime + tool gateway, Postgres-first storage, JSON Schema contracts, trace/eval harness, Mailpit intake), but no ADR makes the **operating model** itself an explicit decision.

Without that decision the project drifts in a recurring direction every time a workstream considers an external integration: "should this also work against the real provider", "should we ship a Helm chart", "should we add a deploy target". Each individual ask is reasonable in isolation; the cumulative effect is scope creep that erodes the evidence-first claim.

The project has also accumulated infrastructure that only makes sense in a local context:

- `compose.yml` is the single runtime substrate; there is no Kubernetes manifest, no Terraform, no IaC tree.
- `chown-init` exists because bind-mounted host directories are part of the model.
- `scripts/dc`, `scripts/first-time-setup.sh`, and the prek hooks all assume a developer workstation, not a CI-driven deploy.
- `chorus.doctor` probes `localhost:*` ports.
- The runbook covers terminate/reset, audit forensics, contract regeneration, and stack reset — all developer-loop concerns.
- ADR 0008 explicitly chose Mailpit (a local SMTP capture tool) over a real provider.

Codifying this as a deliberate decision lets reviewers, contributors, and future workstreams consume a single statement of what Chorus commits to and what is out of scope, instead of inferring it from absent files.

## Decision

Phase 1 adopts a **local-only operating model**. Specifically:

1. **The runtime substrate is `compose.yml` on a developer workstation or a CI runner.** No cloud deployment, no orchestrator manifests, no IaC.
2. **Connectors run real software in sandbox/local mode.** Mailpit for SMTP, public Companies House APIs for research, a Postgres-backed local CRM service implementing the connector contract end-to-end. No production third-party credentials enter the repository or the runtime.
3. **Authentication is local development convenience only.** Default Postgres/Grafana credentials are documented in `.env.example`; tenants are seeded fixtures. No SSO, no OAuth, no production token handling.
4. **Persistence is local volumes.** No managed database, no replication, no backup automation. `down -v` is destructive by design.
5. **Observability terminates at a local Grafana stack.** OpenTelemetry collector exports to a containerised Grafana, Tempo, Loki, and Prometheus. No managed observability backends.
6. **Doctor and CI gates probe `localhost`.** Readiness checks assume the canonical compose stack; CI uses `--quick` to avoid runtime probes against absent services.
7. **The exemplar is the artefact.** Engineering discipline (contracts gate, replay tests, eval fixtures, pre-commit, runbook, ADRs, evidence map) is the deliverable for an architecture review, not a deployable system.

The decision is bounded by the Phase 1 design freeze. Phase 2 (or any subsequent phase the architect opens) is free to revisit; until then, "is this in scope" reduces to "does it run on a single laptop or a CI runner against `compose.yml`".

## Alternatives considered

- **Local-plus-staging.** Add a thin staging deployment so the slice is also exercised against managed infrastructure. Rejected: doubles the surface area, introduces secrets management, fights the no-mocks policy by either standing up shared real-third-party accounts or reintroducing fakes for staging. The marginal evidence is small relative to the cost.
- **Local-or-cloud-pluggable.** Make every component swap-friendly between local and cloud (Compose vs Helm; local CRM vs Salesforce; Mailpit vs SES). Rejected: the abstraction work is itself out of Phase 1 scope, and the local mode is the one that produces the evidence the architecture review needs.
- **No explicit decision.** Continue inferring the model from absent files. Rejected: each new workstream re-litigates it. An ADR pre-empts that.

## Consequences

### Positive

- Workstream sessions have an unambiguous reference for "is this in scope". The default answer to deployment, auth, secrets, or production-grade integration questions is "deferred per ADR 0009".
- The exemplar's claim — engineering discipline as the artefact — is reinforced rather than diluted.
- Evidence reviewers know exactly what to expect on first clone: one bootstrap script, `just up`, `just demo`, `just doctor`. No cloud account, no credentials, no infrastructure setup.

### Negative

- The model is not a deployable system. A reviewer asking "how would this run in production" gets an architectural answer (the deferral list and the design boundaries), not a working artefact. Mitigated by the evidence map being explicit about which capabilities are demonstrated vs deferred.
- Some patterns that production systems handle (secrets rotation, blue/green, shared observability) cannot be exercised end-to-end. Mitigated by the Tool Gateway, agent runtime, and contracts giving production patterns a clear extension point.

### Operational

- `chorus.doctor` has a `--quick` mode for CI and a default mode that probes the local stack; the same binary covers both consumers without configuration drift.
- The runbook covers stuck workflows, denied tool calls, contract regeneration, and stack reset — all valid in the local context. Production runbook concerns (incident response, on-call, change management) are explicitly out of scope.
- CI runs `just doctor-quick`, `just lint` (ruff + pyright), `just contracts-check`, `just test`, and the frontend gates. None of these require a running stack; all of them require a fresh workstation to be reproducible.

## Compliance with existing ADRs

This decision is consistent with ADR 0001 (evidence-first scope), ADR 0007 (trace/eval harness), and ADR 0008 (Mailpit intake). It makes explicit what those decisions imply.
