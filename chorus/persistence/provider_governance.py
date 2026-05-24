"""Read access to the provider catalogue and model-route version surfaces."""

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


class ProviderCatalogueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_id: str
    schema_version: str
    effective_from: datetime
    created_at: datetime


class ProviderCatalogueProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_id: str
    provider_id: str
    display_name: str
    provider_kind: str
    lifecycle_state: str
    credential_required: bool
    secret_ref_names: list[str]
    missing_credentials_behaviour: str
    data_boundary: dict[str, Any]
    operational_limits: dict[str, Any]
    audit: dict[str, Any]


class ProviderCatalogueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_id: str
    provider_id: str
    model_id: str
    display_name: str
    lifecycle_state: str
    supported_task_kinds: list[str]
    supports_structured_output: bool
    context_window_tokens: int | None
    cost_policy: dict[str, Any]


class ModelRouteVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: UUID
    route_version: int
    lifecycle_state: str
    tenant_id: str
    agent_role: str
    task_kind: str
    tenant_tier: str
    provider_catalogue_id: str
    provider_id: str
    model_id: str
    parameters: dict[str, Any]
    budget_cap_usd: Decimal = Field(ge=0)
    max_latency_ms: int = Field(ge=1)
    fallback_policy: dict[str, Any]
    eval_required: bool
    eval_fixture_refs: list[str]
    promotion: dict[str, Any]
    created_at: datetime


class ProviderGovernanceSnapshot(BaseModel):
    """Read-only provider catalogue and route-version state."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    catalogues: list[ProviderCatalogueEntry]
    providers: list[ProviderCatalogueProvider]
    provider_models: list[ProviderCatalogueModel]
    route_versions: list[ModelRouteVersion]


class ProviderGovernanceStore:
    """Read surface for the provider catalogue and route-version composition."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        set_tenant_context(self._conn, tenant_id)

    def clear_tenant_context(self) -> None:
        clear_tenant_context(self._conn)

    def snapshot(self, tenant_id: str) -> ProviderGovernanceSnapshot:
        catalogues = fetch_models(
            self._conn,
            ProviderCatalogueEntry,
            """
            SELECT
                catalogue_id,
                schema_version,
                effective_from,
                created_at
            FROM provider_catalogues
            ORDER BY effective_from DESC, catalogue_id
            """,
            (),
        )
        providers = fetch_models(
            self._conn,
            ProviderCatalogueProvider,
            """
            SELECT
                catalogue_id,
                provider_id,
                display_name,
                provider_kind,
                lifecycle_state,
                credential_required,
                secret_ref_names,
                missing_credentials_behaviour,
                data_boundary,
                operational_limits,
                audit
            FROM provider_catalogue_providers
            ORDER BY catalogue_id, provider_id
            """,
            (),
        )
        provider_models = fetch_models(
            self._conn,
            ProviderCatalogueModel,
            """
            SELECT
                catalogue_id,
                provider_id,
                model_id,
                display_name,
                lifecycle_state,
                supported_task_kinds,
                supports_structured_output,
                context_window_tokens,
                cost_policy
            FROM provider_catalogue_models
            ORDER BY catalogue_id, provider_id, model_id
            """,
            (),
        )
        route_versions = fetch_models(
            self._conn,
            ModelRouteVersion,
            """
            SELECT
                route_id,
                route_version,
                lifecycle_state,
                tenant_id,
                agent_role,
                task_kind,
                tenant_tier,
                provider_catalogue_id,
                provider_id,
                model_id,
                parameters,
                budget_cap_usd,
                max_latency_ms,
                fallback_policy,
                eval_required,
                eval_fixture_refs,
                promotion,
                created_at
            FROM model_route_versions
            WHERE tenant_id = %s
            ORDER BY agent_role, task_kind, route_version
            """,
            (tenant_id,),
        )
        return ProviderGovernanceSnapshot(
            tenant_id=tenant_id,
            catalogues=catalogues,
            providers=providers,
            provider_models=provider_models,
            route_versions=route_versions,
        )
