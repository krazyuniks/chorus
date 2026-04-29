# Security policy

## Posture

Chorus is a sandbox-only reference implementation. It is not a deployable service. The repository carries no production credentials, no real customer data, and no third-party API keys. All runtime behaviour is exercised in sandbox or local mode per project policy (see `AGENTS.md` and `docs/architecture.md`).

The project's "no mocks for architecture evidence" rule means infrastructure and connectors run as real software inside the local Docker Compose substrate (Postgres, Redpanda, Temporal, Mailpit, the local CRM service, public sandbox APIs). Those services are throwaway: they bind to localhost, hold only synthetic fixture data, and are recreated by `just up` and `just down-volumes`. There is no shared environment, no remote endpoint, and no persistent storage of sensitive material.

The security boundary is therefore the developer's local machine. Secrets, where they exist at all, come from `.env` files derived from the committed `.env.example` template and remain local to the contributor's checkout.

## Phase 1 deferrals

Phase 1 explicitly does not include production authentication, SSO, secrets management, network-layer isolation, key rotation, or any deployable security posture. These items are listed under "Deferred After Phase 1" in [`docs/implementation-plan.md`](./docs/implementation-plan.md). Treat any request that depends on those capabilities as out of scope for the current design freeze.

## Reporting a problem

Because there is no production deployment surface and no user data at risk, security-relevant findings should be reported in the open:

1. Open a public GitHub issue against this repository.
2. Apply the `security` label.
3. Include reproduction steps, the affected component boundary (per `AGENTS.md`), and any relevant correlation IDs from local runs.

If a finding is sensitive enough that public disclosure would itself create harm (for example, a credential accidentally committed to history), contact the maintainer privately using the email recorded in this repository's package metadata (`pyproject.toml`) and the repository's GitHub profile, and do not open a public issue until it has been triaged.

## Scope of accepted reports

In scope:

- Accidental credential or secret material committed to the repository or its history.
- Vulnerabilities in code paths that could affect a contributor's local machine when running the documented setup.
- Supply-chain concerns about declared dependencies in `pyproject.toml` or `frontend/package.json`.

Out of scope:

- Findings that depend on production deployment, multi-tenant isolation in a hosted environment, or network exposure of services beyond `localhost`. None of those exist in Phase 1.
- Findings that depend on real third-party connector access. Phase 1 uses sandbox or local connector services only.
