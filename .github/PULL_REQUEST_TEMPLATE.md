<!-- Conventional commit subject required: type(scope): description -->

## Summary

<!-- What changed and why. Cite the relevant component boundary, ADR, or implementation-plan workstream. -->

## Checklist

- [ ] Conventional-commit subject (`type(scope): description`)
- [ ] Contracts in `contracts/` updated if a cross-boundary payload changed; samples and generated models regenerated
- [ ] ADR added under `adrs/` if architecture, boundaries, or governance posture changed
- [ ] Docs (`docs/architecture.md`, `docs/governance-guardrails.md`, `docs/implementation-plan.md`, `docs/evidence-map.md`, `README.md`, `AGENTS.md`) updated alongside code
- [ ] Tests, replay coverage, or eval fixtures updated where relevant
- [ ] Relevant gates run locally (`just doctor`, `just contracts-check`, `just lint`, `just test`, `just test-replay`, `just eval`)
- [ ] No secrets, real customer data, or production credentials committed

## Notes for review

<!-- Anything that would help an asynchronous reviewer answer the evidence-map questions. -->
