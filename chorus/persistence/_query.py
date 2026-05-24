"""Shared query helpers for the per-port persistence read stores.

The R3 F decomposition split the projection / audit / policy-snapshot /
provider-governance read surfaces into one module per port. The Pydantic-row
fetch helper and the tenant-context setter are the only pieces with no port
identity, so they live here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, LiteralString

from psycopg import Connection
from psycopg.rows import dict_row
from pydantic import BaseModel


def set_tenant_context(conn: Connection[Any], tenant_id: str) -> None:
    conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))


def clear_tenant_context(conn: Connection[Any]) -> None:
    conn.execute("SELECT set_config('app.tenant_id', '', false)")


def fetch_models[TModel: BaseModel](
    conn: Connection[Any],
    model_type: type[TModel],
    query: LiteralString,
    params: Sequence[object],
) -> list[TModel]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [model_type.model_validate(row) for row in rows]
