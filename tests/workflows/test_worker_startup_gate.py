from __future__ import annotations

import psycopg
import pytest

from chorus.workflows.worker import (
    WorkerStartupConfigurationError,
    validate_live_provider_route_credentials,
)

TEST_DATABASE_PREFIX = "chorus_worker_startup_test"


def test_worker_startup_allows_recorded_replay_without_live_credentials(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    validate_live_provider_route_credentials(migrated_database_url)


def test_worker_startup_fails_when_live_route_credential_is_missing(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute(
            """
            UPDATE model_routing_policies
            SET
                runtime_route_id = 'demo-eval-canonical',
                provider = 'openai',
                model = 'gpt-5.4-mini-2026-03-17'
            WHERE tenant_id = 'tenant_demo'
              AND agent_role = 'classifier'
              AND task_kind = 'enquiry_classification'
            """
        )
        conn.commit()

    with pytest.raises(WorkerStartupConfigurationError) as exc_info:
        validate_live_provider_route_credentials(migrated_database_url)

    assert str(exc_info.value) == (
        "Live provider route credential gate failed: "
        "route 'demo-eval-canonical' missing credential 'OPENAI_API_KEY'."
    )


def test_worker_startup_fails_when_deepseek_route_credential_is_missing(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute(
            """
            UPDATE model_routing_policies
            SET
                runtime_route_id = 'dev',
                provider = 'deepseek',
                model = 'deepseek-v4-flash'
            WHERE tenant_id = 'tenant_demo'
              AND agent_role = 'classifier'
              AND task_kind = 'enquiry_classification'
            """
        )
        conn.commit()

    with pytest.raises(WorkerStartupConfigurationError) as exc_info:
        validate_live_provider_route_credentials(migrated_database_url)

    assert str(exc_info.value) == (
        "Live provider route credential gate failed: "
        "route 'dev' missing credential 'DEEPSEEK_API_KEY'."
    )
