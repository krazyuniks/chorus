"""Postgres persistence and projection helpers.

After the R3 F decomposition the persistence package exposes one module per
port-shaped read surface:

- :mod:`chorus.persistence.projection` - workflow + calendar projection
  (read surface + write side for the projection port).
- :mod:`chorus.persistence.audit_port` - decision-trail and tool-action
  audit read surface (audit ports).
- :mod:`chorus.persistence.runtime_policy` - runtime-policy snapshot.
- :mod:`chorus.persistence.provider_governance` - provider catalogue and
  route-version snapshot.

This package init re-exports the migration + outbox + projection-write
entry points, which are the common shared surface. Audit, policy, and
provider-governance read stores must be imported from their port-named
module directly; that keeps the F port boundaries visible at the
callsite.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chorus.persistence.migrate import (
        DEFAULT_DATABASE_URL,
        MIGRATIONS_DIR,
        SEEDS_DIR,
        apply_migrations,
    )
    from chorus.persistence.outbox import OutboxStore, OutboxWorkflowEvent
    from chorus.persistence.projection import (
        CalendarProjectionReadModel,
        ProjectionStore,
        WorkflowHistoryEventReadModel,
        WorkflowRunReadModel,
        WorkflowStatus,
    )

__all__ = [
    "DEFAULT_DATABASE_URL",
    "MIGRATIONS_DIR",
    "SEEDS_DIR",
    "CalendarProjectionReadModel",
    "OutboxStore",
    "OutboxWorkflowEvent",
    "ProjectionStore",
    "WorkflowHistoryEventReadModel",
    "WorkflowRunReadModel",
    "WorkflowStatus",
    "apply_migrations",
]


def __getattr__(name: str) -> Any:
    if name in {"DEFAULT_DATABASE_URL", "MIGRATIONS_DIR", "SEEDS_DIR", "apply_migrations"}:
        migrate = import_module("chorus.persistence.migrate")
        return getattr(migrate, name)

    if name in {"OutboxStore", "OutboxWorkflowEvent"}:
        outbox = import_module("chorus.persistence.outbox")
        return getattr(outbox, name)

    if name in {
        "CalendarProjectionReadModel",
        "ProjectionStore",
        "WorkflowHistoryEventReadModel",
        "WorkflowRunReadModel",
        "WorkflowStatus",
    }:
        projection = import_module("chorus.persistence.projection")
        return getattr(projection, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
