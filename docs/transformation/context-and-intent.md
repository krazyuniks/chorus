---
type: project-doc
status: active
date: 2026-05-19
---

# Context And Intent

## Why This Reset Exists

Chorus has accumulated strong technical evidence:

- durable Temporal workflows;
- explicit Agent Runtime and Tool Gateway boundaries;
- contract-generated payloads;
- Postgres audit and projections;
- Redpanda event visibility;
- eval and replay gates;
- local connector sandboxes;
- read-only BFF inspection surfaces.

The problem is not absence of engineering. The problem is that the project's
engineering identity was too soft to defend. The codebase pointed at several
real ideas at once - durable orchestration, governed tool authority, audit
and replay, multi-agent workflow shape, optional LangGraph runtime, optional
deployment - without naming the architectural commitment that ties them
together. That made the project harder to write about, harder to extend
without drift, and harder to use as a reasoning tool.

The reset exists to settle that. Chorus must declare its architectural
thesis, hold to it, and let the surrounding decisions follow from it.

## Architectural Thesis

Chorus is a **hexagonal, ports-and-adapters exemplar for governed agentic
systems with data-contract-first design at every port**.

Two commitments sit underneath that sentence.

1. **Ports and adapters as the load-bearing structure.** The runtime exposes
   a small set of named ports. Adapters behind each port are pluggable. The
   domain core does not know which adapter is active. The workflow code, the
   agent runtime, and the tool authority layer all sit on the domain side
   of the hexagon. Providers, transports, sandboxes, audit stores, and
   observability backends sit on the adapter side.
2. **Contract-first at every port.** Every payload crossing a port is
   validated against an explicit schema. Contracts are the source of truth
   for shape, not the implementation. Adapters that violate the contract
   fail at the boundary, not deep in business logic.

The named ports are:

| Port | Role |
|---|---|
| Intake | Inbound business work entering the system. |
| LLM provider | Model invocations with route catalogue and provider neutrality. |
| Connector | External-action authority via the Tool Gateway. |
| Audit / transcript | Two streams: structured decision-trail and full-fidelity transcript. |
| Projection sink | Read-model derivation for inspection. |
| Observability sink | Traces, metrics, logs, optional LLM observability. |

The thesis is intentionally narrower than "governed multi-agent workflow
orchestration". A workflow happens to be the durability shape. Agents happen
to be the reasoning shape inside that workflow. The architecture being
proven is the hexagonal boundary discipline, not multi-agent collaboration
in itself.

## Audit As Eval Substrate

The audit trail is not only a compliance artefact. It is the project's eval
substrate.

The transcript port stores enough about every captured LLM invocation
(messages, tool calls, route record, parameters, full response) to replay
that invocation against an alternate provider or model. The structured
decision-trail port records what the agent decided, under which policy,
with which inputs and outputs. The same captured material that proves
accountability also enables cross-provider model comparison on real
production traffic.

This collapses two concerns that are normally separate:

- compliance ("who decided what under which policy, on which input, with
  which output");
- engineering ("would another provider or model have made a better call
  on this captured invocation").

Hallucination concerns about cheaper providers become structurally bounded.
Hallucinations are observable in the transcript, replayable against a
different model, and comparable as eval evidence. The same data structure
serves both reviewers.

## Target Intent

Chorus must read as a reference for ports-and-adapters architecture applied
to governed agentic systems. The body of evidence the project must produce:

- a named-port surface with explicit schemas at each port;
- an LLM provider port that is provider-agnostic by construction;
- two audit ports - one structured, one full-fidelity - with the
  replay-as-eval-substrate pattern wired through them;
- workflows that are replay-stable because every cross-port payload is
  captured and contract-validated;
- a small set of real domain use cases that exercise the adapter surface;
- eval evidence that is invariant-based, not path-enumerated, and that
  treats replay as a first-class eval mode.

The thesis comes first. Architecture controls serve the thesis. Use cases
exist to exercise the ports.

## Layering

| Layer | Meaning |
|---|---|
| Chorus | The overall ports-and-adapters exemplar and codebase. |
| Domain | A real operational problem space whose work shape exercises the ports. |
| Use case | A runnable business workflow inside that domain. |
| Ports | Intake, LLM provider, connector, audit / transcript, projection sink, observability sink. |
| Adapters | Concrete implementations behind each port. |

Deployment is out of scope for this codebase. It will live as a separate
RIT-level concern in vault, not inside the Chorus repo.

## Current Drift

The signals that triggered the reset:

- The continuation cadence became more work than the artefacts it produced.
- Phase 2E production-readiness work was being added before the
  architectural thesis was clear.
- Terms such as `support`, `ticket`, `case`, and `account` were technically
  implemented but not grounded in a chosen domain.
- The codebase carried a workflow plumbing duplication between Lighthouse
  and Support Triage that the framing of the project did not yet make
  uncomfortable.
- The Tool Gateway dispatched connector calls through a hardcoded match
  block instead of an adapter registry.
- Three large files (`projection.py`, `eval/run.py`, `doctor.py`)
  conflated multiple concerns.
- LangGraph had been adopted as an agent execution runtime without the
  ports-and-adapters argument that would have constrained it; that
  decision will be reversed in a later ADR pass.

## Reset Decisions

1. Architectural thesis becomes the gravity centre. All other decisions
   derive from it.
2. LangGraph leaves the agent execution path. Reasoning runs through the
   LLM provider port directly.
3. The LLM provider port is implemented with the OpenAI Python SDK
   pointed at any OpenAI-compatible endpoint. Dev route is
   DeepSeek V4-Flash with thinking-mode for reasoning steps. The canonical
   demo and eval route is OpenAI gpt-5.4-mini. The route catalogue records
   provider plus model per call.
4. Two audit ports replace the single decision-trail concept: a structured
   decision-trail port for the compliance shape and a full-fidelity
   transcript port for the replay-eval shape.
5. Cross-provider replay over captured transcripts is a first-class eval
   mode, not a research idea.
6. The domain story shifts to one fleshed-out UK-regulated use case plus
   two further use cases whose role is to demonstrate adapter reuse across
   different governance regimes. Use case 1 is UK insurance broking inbound
   quote qualification. Use cases 2 and 3 (currently proposed: UK legal
   intake and conflict check; UK wealth management / IFA inbound enquiry)
   are confirmed in R1.
7. Phase 2E production-readiness work is parked. Deployment leaves the
   Chorus repo and is reframed as a future RIT-level project.
8. Existing code is preserved as evidence and reframed against the
   ports-and-adapters thesis. Lighthouse and Support Triage are reviewed
   in that frame; they survive only if they demonstrate adapter reuse for
   one of the chosen UK-regulated use cases.

## Non-Goals Of This Reset Package

This package does not select use cases 2 and 3, rename code, remove existing
workflows, introduce deployment resources, or change runtime behaviour. It
codifies the architectural thesis and the decisions that follow, so the
runtime work in R1 onwards can be governed by them.
