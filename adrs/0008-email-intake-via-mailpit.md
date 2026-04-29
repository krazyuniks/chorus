---
type: adr
status: accepted
date: 2026-04-29
---

# ADR 0008 — Email intake via Mailpit

## Status

Accepted — 2026-04-29.

## Context

The Phase 1A vertical slice needs a concrete demo trigger that:

- Demonstrates the integration boundary (external event → governed workflow), not only internal workflow execution.
- Aligns with the project no-mocks policy (real software, sandbox boundary).
- Drives implementation toward a credible end-to-end demo without expanding scope.

Two alternatives were considered before this decision:

- **UI form-submit input.** Cheap to build but bypasses the integration boundary; the intake is effectively a hand-fed form pretending to be an inbox.
- **No real intake mechanism, narrative-only.** The architecture description said "lead email arrives" without describing a receive mechanism.

Neither matched the architectural credential the evidence is meant to demonstrate.

## Decision

The Phase 1A demo trigger is real SMTP intake via Mailpit:

1. A real email sent via SMTP to `leads@chorus.local:1025` is captured by Mailpit.
2. A Temporal poller activity reads new Mailpit messages via its HTTP API, deduplicates by Message-ID, and starts a Lighthouse workflow per new lead.
3. UI form-submit remains as a secondary intake path for quick fixture replay during development, but the demo path leads with the SMTP-receive flow.

Mailpit serves dual duty: SMTP receive + HTTP API for inbound (lead intake) and SMTP capture for outbound (email-send connector). One operational footprint covers both intake and outbound surfaces.

## Primary evidence remains the documentation set

The Chorus evidence claim rests on the documentation set — `architecture.md`, `technical-architecture.md`, `governance-guardrails.md`, `sdlc-operating-model.md`, the ADRs, and the public evidence map. These artefacts stand alone as evidence of architectural thinking; the working application is the demonstration that backs them, not the primary evidence asset.

## Screencast deferred to backlog

A polished 3-minute screencast that captures the email-input → workflow → outbound-email round-trip is a backlog item, not a Phase 1A deliverable. It only makes sense once the application is in a holistic working state where a 3-minute recording would represent the system fairly. Reassess promotion to a later phase once 1A is implemented and stable.

## Consequences

- **Workstream B (Temporal workflows + activities)** gains an SMTP-poll activity reading Mailpit's HTTP API. Dedupes by Message-ID. Starts a Lighthouse workflow per new lead. ~150 LOC.
- **Workstream D (Tool Gateway + local connectors)** Mailpit ownership is unchanged in scope but spans both intake and outbound surfaces.
- **Workstream F (Observability + ops)** takes ownership of the `just demo` CLI sequence (sends fixture lead via `swaks`, opens consoles for live observation).
- A new lead-intake JSON Schema entry covers the parsed email payload (From, Subject, Body, Headers, Attachments-summary, Message-ID).
- `demo-script.md` is updated during 1A doc closeout to describe the SMTP-receive demo path.
- README leads with the documentation set as the primary review modality; live demo is the secondary path.

## Alternatives considered

- **Dedicated SMTP listener (aiosmtpd or smtpd).** More direct than Mailpit + poll but adds a service the rest of the stack does not already need. Mailpit's dual role is cleaner.
- **IMAP poll against a real mailbox.** Introduces external dependency, OAuth setup, and quotas. Wrong scope for a self-contained reference implementation.
- **HTTP webhook intake (SendGrid inbound parse, Postmark, etc).** Introduces a third-party dependency. Rejected for the same reason.
- **UI form-submit only.** Bypasses the integration boundary; not architecturally honest for the evidence story.

## Related

- ADR 0001 — evidence-first scope and Lighthouse.
- ADR 0004 — Agent Runtime and Tool Gateway.
- ADR 0006 — JSON Schema contracts (lead-intake schema covers parsed email payload).
