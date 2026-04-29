"""Postgres persistence and projection helpers for the Phase 1A storage slice."""

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
    from chorus.persistence.projection import (
        AgentRegistryEntry,
        ModelRoutingPolicy,
        ProjectionStore,
        RuntimePolicySnapshot,
        ToolGrant,
        WorkflowRunReadModel,
    )

__all__ = [
    "DEFAULT_DATABASE_URL",
    "MIGRATIONS_DIR",
    "SEEDS_DIR",
    "AgentRegistryEntry",
    "ModelRoutingPolicy",
    "ProjectionStore",
    "RuntimePolicySnapshot",
    "ToolGrant",
    "WorkflowRunReadModel",
    "apply_migrations",
]


def __getattr__(name: str) -> Any:
    if name in {"DEFAULT_DATABASE_URL", "MIGRATIONS_DIR", "SEEDS_DIR", "apply_migrations"}:
        migrate = import_module("chorus.persistence.migrate")
        return getattr(migrate, name)

    if name in {
        "AgentRegistryEntry",
        "ModelRoutingPolicy",
        "ProjectionStore",
        "RuntimePolicySnapshot",
        "ToolGrant",
        "WorkflowRunReadModel",
    }:
        projection = import_module("chorus.persistence.projection")
        return getattr(projection, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
