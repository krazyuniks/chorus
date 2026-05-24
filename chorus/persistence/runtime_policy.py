"""Read access to the runtime-policy snapshot (agents + routing + grants).

The runtime-policy snapshot composes three governance tables - agent registry,
model routing policies, tool grants - into a single tenant-scoped view used by
the BFF policy inspection routes and the docs/governance evidence pages.

The provider catalogue and route-version surfaces are a separate port; they
live in `chorus/persistence/provider_governance.py`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field

from chorus.persistence._query import (
    clear_tenant_context,
    fetch_models,
    set_tenant_context,
)


class AgentRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agent_id: str
    role: str
    version: str
    lifecycle_state: str
    owner: str
    prompt_reference: str
    prompt_hash: str
    capability_tags: list[str]
    updated_at: datetime


class ModelRoutingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: UUID
    tenant_id: str
    agent_role: str
    task_kind: str
    tenant_tier: str
    runtime_route_id: str
    provider: str
    model: str
    parameters: dict[str, Any]
    budget_cap_usd: Decimal = Field(ge=0)
    fallback_policy: dict[str, Any]
    lifecycle_state: str


class ToolGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: UUID
    tenant_id: str
    agent_id: str
    agent_version: str
    tool_name: str
    mode: str
    allowed: bool
    approval_required: bool
    redaction_policy: dict[str, Any]


class PolicySnapshotEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    policy_snapshot_ref: str
    workflow_type: str
    snapshot_version: str
    lifecycle_state: str
    effective_from: datetime
    policy_bundle: dict[str, Any]
    source_refs: dict[str, Any]
    content_hash: str
    metadata: dict[str, Any]
    created_at: datetime


class RuntimePolicySnapshot(BaseModel):
    """Read-only governance policy state for later BFF/admin inspection."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agents: list[AgentRegistryEntry]
    model_routes: list[ModelRoutingPolicy]
    tool_grants: list[ToolGrant]
    policy_snapshots: list[PolicySnapshotEntry]


class PolicySnapshotStore:
    """Read surface for the runtime-policy snapshot composition."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        set_tenant_context(self._conn, tenant_id)

    def clear_tenant_context(self) -> None:
        clear_tenant_context(self._conn)

    def snapshot(self, tenant_id: str) -> RuntimePolicySnapshot:
        agents = fetch_models(
            self._conn,
            AgentRegistryEntry,
            """
            SELECT
                tenant_id,
                agent_id,
                role,
                version,
                lifecycle_state,
                owner,
                prompt_reference,
                prompt_hash,
                capability_tags,
                updated_at
            FROM agent_registry
            WHERE tenant_id = %s
            ORDER BY role, agent_id, version
            """,
            (tenant_id,),
        )
        model_routes = fetch_models(
            self._conn,
            ModelRoutingPolicy,
            """
            SELECT
                policy_id,
                tenant_id,
                agent_role,
                task_kind,
                tenant_tier,
                runtime_route_id,
                provider,
                model,
                parameters,
                budget_cap_usd,
                fallback_policy,
                lifecycle_state
            FROM model_routing_policies
            WHERE tenant_id = %s
            ORDER BY agent_role, task_kind
            """,
            (tenant_id,),
        )
        tool_grants = fetch_models(
            self._conn,
            ToolGrant,
            """
            SELECT
                grant_id,
                tenant_id,
                agent_id,
                agent_version,
                tool_name,
                mode,
                allowed,
                approval_required,
                redaction_policy
            FROM tool_grants
            WHERE tenant_id = %s
            ORDER BY agent_id, tool_name, mode
            """,
            (tenant_id,),
        )
        policy_snapshots = fetch_models(
            self._conn,
            PolicySnapshotEntry,
            """
            SELECT
                tenant_id,
                policy_snapshot_ref,
                workflow_type,
                snapshot_version,
                lifecycle_state,
                effective_from,
                policy_bundle,
                source_refs,
                content_hash,
                metadata,
                created_at
            FROM policy_snapshots
            WHERE tenant_id = %s
            ORDER BY workflow_type, effective_from DESC, policy_snapshot_ref
            """,
            (tenant_id,),
        )
        return RuntimePolicySnapshot(
            tenant_id=tenant_id,
            agents=agents,
            model_routes=model_routes,
            tool_grants=tool_grants,
            policy_snapshots=policy_snapshots,
        )

    def get_policy_snapshot(
        self,
        tenant_id: str,
        policy_snapshot_ref: str,
    ) -> PolicySnapshotEntry | None:
        rows = fetch_models(
            self._conn,
            PolicySnapshotEntry,
            """
            SELECT
                tenant_id,
                policy_snapshot_ref,
                workflow_type,
                snapshot_version,
                lifecycle_state,
                effective_from,
                policy_bundle,
                source_refs,
                content_hash,
                metadata,
                created_at
            FROM policy_snapshots
            WHERE tenant_id = %s
              AND policy_snapshot_ref = %s
            LIMIT 1
            """,
            (tenant_id, policy_snapshot_ref),
        )
        return rows[0] if rows else None
