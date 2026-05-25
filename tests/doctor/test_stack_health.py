from __future__ import annotations

from chorus.doctor.projection_port import migration_findings
from chorus.doctor.stack_health import (
    ComposeContainer,
    ComposeServiceSpec,
    compose_runtime_findings,
)


def _failure_messages(messages: list[str]) -> list[str]:
    return [message for message in messages if message.startswith("fail:")]


def test_compose_runtime_accepts_running_healthy_and_completed_one_shot() -> None:
    findings = compose_runtime_findings(
        {
            "chown-init": ComposeServiceSpec("chown-init", one_shot=True),
            "postgres": ComposeServiceSpec("postgres"),
        },
        [
            ComposeContainer(
                id="init123",
                name="chorus-chown-init-1",
                service="chown-init",
                state="exited",
                health="",
                exit_code=0,
            ),
            ComposeContainer(
                id="pg123",
                name="chorus-postgres-1",
                service="postgres",
                state="running",
                health="healthy",
                exit_code=0,
            ),
        ],
        {"init123": 0, "pg123": 0},
    )

    rendered = [f"{finding.level}:{finding.message}" for finding in findings]

    assert _failure_messages(rendered) == []
    assert "ok:chorus-chown-init-1 (chown-init) completed successfully" in rendered
    assert "ok:chorus-postgres-1 (postgres) is running and healthy" in rendered
    assert "ok:all compose containers have RestartCount=0 since boot" in rendered


def test_compose_runtime_fails_on_missing_unhealthy_and_restarted_container() -> None:
    findings = compose_runtime_findings(
        {
            "mailpit": ComposeServiceSpec("mailpit"),
            "postgres": ComposeServiceSpec("postgres"),
        },
        [
            ComposeContainer(
                id="pg123",
                name="chorus-postgres-1",
                service="postgres",
                state="running",
                health="unhealthy",
                exit_code=0,
            )
        ],
        {"pg123": 2},
    )

    messages = [finding.message for finding in findings if finding.level == "fail"]

    assert "compose service 'mailpit' has no container - run 'just up'" in messages
    assert "chorus-postgres-1 (postgres) health=unhealthy; expected healthy" in messages
    assert "chorus-postgres-1 (postgres) RestartCount=2 since boot" in messages


def test_migration_findings_fail_on_missing_or_checksum_drift() -> None:
    findings = migration_findings(
        {
            "001_current_state_baseline.sql": "expected-checksum",
            "002_next.sql": "expected-next",
        },
        {
            "001_current_state_baseline.sql": "stale-checksum",
        },
    )

    messages = [finding.message for finding in findings if finding.level == "fail"]

    assert (
        "migration checksum mismatch: 001_current_state_baseline.sql - create a new migration"
        in messages
    )
    assert "migration not applied: 002_next.sql - run 'just db-migrate'" in messages
