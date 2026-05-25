"""Required local Compose stack health checks for ``just doctor``."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from chorus.doctor._reporting import fail, ok, section
from chorus.doctor.scaffold import ROOT

FindingLevel = Literal["ok", "fail"]


@dataclass(frozen=True)
class Finding:
    level: FindingLevel
    message: str


@dataclass(frozen=True)
class ComposeServiceSpec:
    name: str
    one_shot: bool = False


@dataclass(frozen=True)
class ComposeContainer:
    id: str
    name: str
    service: str
    state: str
    health: str
    exit_code: int | None


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )


def _dc_command(*args: str) -> list[str]:
    return [str(ROOT / "scripts/dc"), *args]


def _json_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        mapping = cast(Mapping[object, object], value)
        return {str(key): cast(Any, item) for key, item in mapping.items()}
    return {}


def _json_string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _json_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _compose_service_specs(config_json: str) -> dict[str, ComposeServiceSpec]:
    config = _json_mapping(json.loads(config_json))
    services = _json_mapping(config.get("services"))
    specs: dict[str, ComposeServiceSpec] = {}
    for name, raw_service in services.items():
        service_config = _json_mapping(raw_service)
        specs[name] = ComposeServiceSpec(
            name=name,
            one_shot=service_config.get("restart") == "no",
        )
    return specs


def _compose_containers(ps_json: str) -> list[ComposeContainer]:
    stripped = ps_json.strip()
    if not stripped:
        return []
    raw_rows: list[object]
    if stripped.startswith("["):
        parsed = cast(object, json.loads(stripped))
        raw_rows = cast(list[object], parsed) if isinstance(parsed, list) else []
    else:
        raw_rows = [
            cast(object, json.loads(line)) for line in stripped.splitlines() if line.strip()
        ]

    containers: list[ComposeContainer] = []
    for row in raw_rows:
        data = _json_mapping(row)
        containers.append(
            ComposeContainer(
                id=_json_string(data.get("ID")),
                name=_json_string(data.get("Name")) or _json_string(data.get("Names")),
                service=_json_string(data.get("Service")),
                state=_json_string(data.get("State")).lower(),
                health=_json_string(data.get("Health")).lower(),
                exit_code=_json_int(data.get("ExitCode")),
            )
        )
    return containers


def _restart_counts(inspect_json: str) -> dict[str, int]:
    raw = cast(object, json.loads(inspect_json))
    if not isinstance(raw, list):
        return {}
    counts: dict[str, int] = {}
    for item in cast(list[object], raw):
        data = _json_mapping(item)
        container_id = _json_string(data.get("Id"))
        restart_count = _json_int(data.get("RestartCount")) or 0
        if container_id:
            counts[container_id] = restart_count
    return counts


def compose_runtime_findings(
    service_specs: Mapping[str, ComposeServiceSpec],
    containers: Sequence[ComposeContainer],
    restart_counts: Mapping[str, int],
) -> list[Finding]:
    findings: list[Finding] = []
    containers_by_service: dict[str, list[ComposeContainer]] = {}
    for container in containers:
        containers_by_service.setdefault(container.service, []).append(container)

    for service_name in sorted(service_specs):
        spec = service_specs[service_name]
        service_containers = containers_by_service.get(service_name, [])
        if not service_containers:
            findings.append(
                Finding(
                    "fail",
                    f"compose service '{service_name}' has no container - run 'just up'",
                )
            )
            continue
        for container in sorted(service_containers, key=lambda item: item.name):
            findings.extend(_container_state_findings(spec, container))

    restarted = False
    for container in sorted(containers, key=lambda item: item.name):
        restart_count = _restart_count_for_container(container, restart_counts)
        if restart_count > 0:
            restarted = True
            findings.append(
                Finding(
                    "fail",
                    f"{container.name} ({container.service}) "
                    f"RestartCount={restart_count} since boot",
                )
            )
    if not restarted and containers:
        findings.append(Finding("ok", "all compose containers have RestartCount=0 since boot"))

    return findings


def _container_state_findings(
    spec: ComposeServiceSpec,
    container: ComposeContainer,
) -> list[Finding]:
    if spec.one_shot:
        if container.state == "exited" and container.exit_code == 0:
            return [
                Finding(
                    "ok",
                    f"{container.name} ({spec.name}) completed successfully",
                )
            ]
        if container.state == "running" and container.health in {"", "healthy"}:
            return [Finding("ok", f"{container.name} ({spec.name}) is running")]
        return [
            Finding(
                "fail",
                f"{container.name} ({spec.name}) expected completed exit 0; "
                f"state={container.state or '<unknown>'} exit={container.exit_code}",
            )
        ]

    if container.state != "running":
        return [
            Finding(
                "fail",
                f"{container.name} ({spec.name}) is "
                f"{container.state or '<unknown>'}; expected running",
            )
        ]
    if container.health and container.health != "healthy":
        return [
            Finding(
                "fail",
                f"{container.name} ({spec.name}) health={container.health}; expected healthy",
            )
        ]
    suffix = " and healthy" if container.health == "healthy" else ""
    return [Finding("ok", f"{container.name} ({spec.name}) is running{suffix}")]


def _restart_count_for_container(
    container: ComposeContainer,
    restart_counts: Mapping[str, int],
) -> int:
    if container.id in restart_counts:
        return restart_counts[container.id]
    for inspected_id, restart_count in restart_counts.items():
        if inspected_id.startswith(container.id):
            return restart_count
    return 0


def check_compose_runtime() -> int:
    section("compose runtime")
    config_result = _run(_dc_command("config", "--format", "json"))
    if config_result.returncode != 0:
        fail("compose config could not be rendered through scripts/dc")
        if config_result.stderr.strip():
            print(config_result.stderr.strip())
        return 1
    try:
        service_specs = _compose_service_specs(config_result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"compose config returned invalid JSON: {exc}")
        return 1

    ps_result = _run(_dc_command("ps", "-a", "--format", "json"))
    if ps_result.returncode != 0:
        fail("compose service state could not be read through scripts/dc")
        if ps_result.stderr.strip():
            print(ps_result.stderr.strip())
        return 1
    try:
        containers = _compose_containers(ps_result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"compose ps returned invalid JSON: {exc}")
        return 1
    if not containers:
        fail("no Compose containers found - run 'just up'")
        return max(1, len(service_specs))

    inspect_result = _run(["docker", "inspect", *[container.id for container in containers]])
    if inspect_result.returncode != 0:
        fail("docker inspect failed while reading container restart counts")
        if inspect_result.stderr.strip():
            print(inspect_result.stderr.strip())
        return 1
    try:
        restart_counts = _restart_counts(inspect_result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"docker inspect returned invalid JSON: {exc}")
        return 1

    failures = 0
    for finding in compose_runtime_findings(service_specs, containers, restart_counts):
        if finding.level == "ok":
            ok(finding.message)
        else:
            fail(finding.message)
            failures += 1
    return failures
