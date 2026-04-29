# Contributing

Chorus is design-frozen for Phase 1 and is currently in the Phase 0 / 1A scaffold window. The repository is open for review and inspection, but external contributions are not actively sought during the bootstrap phase. Issues and small corrective PRs (typos, tightened docs, reproducible bug reports) are welcome.

If you do open a change, the following guidance applies.

## Authority order

Project conventions, component boundaries, scope rules, and the testing-gate hierarchy live in [`AGENTS.md`](./AGENTS.md). That file lists the authority order for architectural and runtime questions and points at `docs/architecture.md`, the ADR set, the governance guardrails, and the implementation plan. Read those before proposing changes that cross a component boundary.

## First-time setup

```zsh
./scripts/first-time-setup.sh
```

That script provisions the local toolchain. Once it completes, bring the local stack up and verify scaffold readiness:

```zsh
just up
just doctor
```

## Running the gates

Use `just` for everything. Discover available recipes:

```zsh
just --list
```

The minimum loop before opening a PR:

```zsh
just doctor
just contracts-check
just lint
just test
```

If your change touches Temporal workflows, also run `just test-replay`. If it touches eval-relevant agent, prompt, model-route, workflow, or governance behaviour, also run `just eval`. `AGENTS.md` records which gate proves which kind of change.

## Pre-commit hooks

```zsh
just install-hooks
just hooks
```

`just install-hooks` registers the configured hooks; `just hooks` runs them across the working tree. Keep them green before pushing.

## Commits

- Conventional commits are required: `type(scope): description`.
- Do not add `Co-Authored-By`, generated-by, or any AI attribution to commits, PRs, issues, or other artefacts.
- Keep commits focused. Prefer multiple small commits to one omnibus commit when changes cross component boundaries.
- **Stage paths explicitly** — `git add path/one path/two`, never `git add -A` and never `git add .`. Phase 1A is parallelised across six workstreams (A persistence, B temporal, C agent runtime, D tool gateway, E BFF/UI, F observability/ops) which may run as concurrent sessions against the same working tree and the same git index. A blanket `git add -A` from one session sweeps another session's in-flight files into a commit titled for the wrong concern; this has happened in earlier passes and the resulting commit history is hard to untangle. Stage by path so each workstream's commit carries only its own artefacts.

## Documentation moves with code

Per `AGENTS.md`: "Architecture and docs move with code. If behaviour, boundaries, contracts, commands, or evidence surfaces change, update the matching docs in the same work." That rule is binding. A PR that changes runtime behaviour without updating the matching docs is not ready to merge.

## Scope

If a change extends Phase 1 scope (a new workflow, a real third-party connector, production auth, cloud deployment, a runtime DSL, the Scylla path), open an issue first and expect it to be deferred. The "Deferred After Phase 1" list in [`docs/implementation-plan.md`](./docs/implementation-plan.md) is the authoritative scope boundary for this phase.
