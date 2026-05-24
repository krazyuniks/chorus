---
type: project-doc
status: active
date: 2026-05-24
---

# Chorus Design Control

This directory holds current design-control documents for Chorus. Keep these
documents declarative and prescriptive. Do not add retrospective folders,
superseded forwarding stubs, or retrospective phase ledgers; git history is the
history.

## Design Decision

Chorus is a ports-and-adapters exemplar for governed agentic systems with
contract-first boundaries at every port. The six named ports are: intake,
LLM provider, connector, audit / transcript, projection sink, observability
sink.

The LLM provider port uses the OpenAI Python SDK against any
OpenAI-compatible endpoint. The route catalogue records provider and model
metadata per call.

The audit surface splits into two ports: a structured decision-trail port
and a full-fidelity transcript port. The transcript port stores enough to
replay any captured invocation against an alternate provider; cross-provider
replay is a first-class eval mode.

UC1 is UK insurance broking inbound quote qualification. UC2 is UK legal
services intake and conflict check. UC3 is UK IFA inbound enquiry and
suitability. Their role is to demonstrate adapter reuse across different UK
regulatory regimes.

Production deployment is out of scope for the local POC.

## Documents

- [domain-refocus-plan.md](domain-refocus-plan.md) defines the UK-regulated
  use-case set and the adapter-reuse shape.
- [engineering-thesis.md](engineering-thesis.md) is the thesis statement
  in long form: named ports, LLM provider port design, two audit ports,
  and the replay-as-eval-substrate pattern.
- [r4-design-decisions.md](r4-design-decisions.md) records the accepted R4
  sequencing, runnable-channel, replay-comparison, approval-package, and
  route-alignment decisions.
- [code-refactor-directions.md](code-refactor-directions.md) names the code
  direction required to keep the implementation aligned with the thesis.
- [eval-reshape-directions.md](eval-reshape-directions.md) shifts eval from
  path enumeration to invariant-based shape and adds replay-as-comparison
  as a first-class mode.
- [r4-implementation-backlog.md](r4-implementation-backlog.md) is the active
  R4 strategy, backlog, evidence log, and continuation handoff.

## Operating Rule

Use `r4-implementation-backlog.md` as the single durable work tracker during
R4. At the end of each R4 session, update that file and print the next
continuation prompt from it.
