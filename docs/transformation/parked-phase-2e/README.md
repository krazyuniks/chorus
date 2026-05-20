---
type: project-doc
status: parked
date: 2026-05-20
---

# Parked - Phase 2E Production-Readiness Pack

The five documents in this folder are the Phase 2E production-readiness
architecture pack. They were written before the 2026-05-19 transformation
reset, while deployment was still treated as a Chorus repository phase.

The reset removed deployment from the Chorus repository. Hosting,
production identity and IAM, secrets handling, deployment topology, backup
and restore, disaster recovery, and retention are reframed as a future
vault-level Radian IT project delivered against a real client engagement.
They are not scope inside the Chorus repository, which is meant to stay
runnable locally as a ports-and-adapters reference.

These documents are parked, not deleted. They are input material for that
future project.

## Contents

| Document | Subject |
|---|---|
| [`production-identity-iam-mapping.md`](production-identity-iam-mapping.md) | Production identity and IAM mapping. |
| [`secrets-credential-handling.md`](secrets-credential-handling.md) | Secrets and credential handling. |
| [`deployment-topology-architecture.md`](deployment-topology-architecture.md) | Deployment topology. |
| [`backup-restore-dr-architecture.md`](backup-restore-dr-architecture.md) | Backup, restore, and disaster recovery. |
| [`retention-audit-storage-architecture.md`](retention-audit-storage-architecture.md) | Retention and audit storage. |

## Relative links

These documents were written for the `docs/` directory. From this parked
location, ADR links resolve under `../../../adrs/` and sibling-document
links resolve under `../../`. The documents are frozen; their internal
links were not repointed.
