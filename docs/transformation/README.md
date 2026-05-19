---
type: project-doc
status: active
date: 2026-05-19
---

# Chorus Transformation Reset

This directory is the control point for the Chorus reset.

Development is paused until the reset work has produced a settled
architectural thesis, a chosen use-case set, a tightened roadmap, and the
design notes that will govern the runtime refactor. The project has useful
runtime evidence, but its engineering identity was too soft to defend.
The reset declares the thesis - hexagonal, ports-and-adapters, with
data-contract-first design at every port - and orders the rest of the work
around it.

## Reset Decision

Chorus is a ports-and-adapters exemplar for governed agentic systems with
contract-first boundaries at every port. The six named ports are: intake,
LLM provider, connector, audit / transcript, projection sink, observability
sink.

LangGraph leaves the agent execution path. The LLM provider port uses the
OpenAI Python SDK against any OpenAI-compatible endpoint; dev route is
DeepSeek V4-Flash with thinking-mode, demo / eval route is OpenAI
gpt-5.4-mini, route catalogue records provider plus model per call.

The audit surface splits into two ports: a structured decision-trail port
and a full-fidelity transcript port. The transcript port stores enough to
replay any captured invocation against an alternate provider; cross-provider
replay is a first-class eval mode.

Lighthouse retires as the named exemplar. Use case 1 becomes UK insurance
broking inbound quote qualification. Two further use cases (proposed: UK
legal services intake / conflict check, UK wealth management / IFA inbound
enquiry) are confirmed in R1; their role is to demonstrate adapter reuse
across different UK regulatory regimes.

Deployment leaves the Chorus repo. It is reframed as a future vault-level
Radian IT project against a future client engagement.

## Bundle

- [context-and-intent.md](context-and-intent.md) records the architectural
  thesis, why the reset exists, the audit-as-eval-substrate angle, and the
  reset decisions.
- [domain-refocus-plan.md](domain-refocus-plan.md) defines the UK-regulated
  use-case set and the adapter-reuse shape.
- [engineering-reset-roadmap.md](engineering-reset-roadmap.md) lays out the
  reset phases from checkpoint through local POC readiness. Deployment
  has been removed from this roadmap.
- [current-state-inventory.md](current-state-inventory.md) captures the
  reset baseline and reframes existing implementation against the named
  ports.
- [engineering-thesis.md](engineering-thesis.md) is the thesis statement
  in long form: named ports, LLM provider port design, two audit ports,
  and the replay-as-eval-substrate pattern.
- [code-refactor-directions.md](code-refactor-directions.md) names the
  four engineering smells identified on 2026-05-19 and the direction of
  resolution under the thesis.
- [eval-reshape-directions.md](eval-reshape-directions.md) shifts eval from
  path enumeration to invariant-based shape and adds replay-as-comparison
  as a first-class mode.

## Operating Rule

Do not resume feature development by copying the old continuation prompt.
The next session should work from this reset bundle and proceed through
R1.

Use checkpoint-based work, not one prompt per artefact. Each checkpoint
defines outcome, files likely to change, gates, not-done boundaries, and
a short next-step note. Do not generate another long-lived prompt chain
where every artefact requires a new copied prompt.

ADRs are intentionally deferred until the bundle has settled. The ADR
writing pass after R2 will cover the LangGraph reversal, the LLM provider
port, the audit ports plus replay-eval, and the domain refocus.
