"""Drift checks for the repo-local environment file."""

from __future__ import annotations

import sys
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from chorus.doctor._env import parse_env_assignment
from chorus.doctor._reporting import fail, ok, section
from chorus.doctor.scaffold import ROOT

SECRET_VALUE_ALLOWLIST = frozenset(
    {
        "CHORUS_PG_PASSWORD",
        "DEEPSEEK_API_KEY",
        "GRAFANA_ADMIN_PASSWORD",
        "OPENAI_API_KEY",
        "TEMPORAL_PG_PASSWORD",
    }
)


@dataclass(frozen=True)
class EnvFile:
    path: Path
    values: dict[str, str]
    duplicate_keys: tuple[str, ...]


@dataclass(frozen=True)
class EnvDriftReport:
    missing_files: tuple[Path, ...]
    keys_missing_from_env: tuple[str, ...]
    keys_missing_from_example: tuple[str, ...]
    value_mismatches: tuple[str, ...]
    duplicate_env_keys: tuple[str, ...]
    duplicate_example_keys: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failure_messages()

    def failure_messages(self) -> tuple[str, ...]:
        messages: list[str] = []
        for path in self.missing_files:
            messages.append(f"missing {path.name} - run 'just env' before linting")
        if self.duplicate_env_keys:
            messages.append(
                f".env declares duplicate keys: {_format_keys(self.duplicate_env_keys)}"
            )
        if self.duplicate_example_keys:
            messages.append(
                f".env.example declares duplicate keys: {_format_keys(self.duplicate_example_keys)}"
            )
        if self.keys_missing_from_env:
            messages.append(
                ".env is missing keys declared by .env.example: "
                f"{_format_keys(self.keys_missing_from_env)}"
            )
        if self.keys_missing_from_example:
            messages.append(
                ".env declares keys absent from .env.example: "
                f"{_format_keys(self.keys_missing_from_example)}"
            )
        if self.value_mismatches:
            messages.append(
                "non-secret .env values differ from .env.example: "
                f"{_format_keys(self.value_mismatches)}"
            )
        return tuple(messages)


def env_drift_report(
    env_path: Path = ROOT / ".env",
    example_path: Path = ROOT / ".env.example",
    *,
    secret_value_allowlist: Collection[str] = SECRET_VALUE_ALLOWLIST,
) -> EnvDriftReport:
    missing_files = tuple(path for path in (env_path, example_path) if not path.is_file())
    if missing_files:
        return EnvDriftReport(
            missing_files=missing_files,
            keys_missing_from_env=(),
            keys_missing_from_example=(),
            value_mismatches=(),
            duplicate_env_keys=(),
            duplicate_example_keys=(),
        )

    env_file = _read_env_file(env_path)
    example_file = _read_env_file(example_path)
    env_keys = set(env_file.values)
    example_keys = set(example_file.values)
    secret_keys = set(secret_value_allowlist)
    shared_non_secret_keys = (env_keys & example_keys) - secret_keys

    return EnvDriftReport(
        missing_files=(),
        keys_missing_from_env=tuple(sorted(example_keys - env_keys)),
        keys_missing_from_example=tuple(sorted(env_keys - example_keys)),
        value_mismatches=tuple(
            sorted(
                key
                for key in shared_non_secret_keys
                if env_file.values[key] != example_file.values[key]
            )
        ),
        duplicate_env_keys=env_file.duplicate_keys,
        duplicate_example_keys=example_file.duplicate_keys,
    )


def check_env_drift() -> int:
    section(".env drift")
    report = env_drift_report()
    messages = report.failure_messages()
    if not messages:
        ok(".env and .env.example declare matching non-secret values")
        return 0
    for message in messages:
        fail(message)
    return len(messages)


def main() -> int:
    return 1 if check_env_drift() else 0


def _read_env_file(path: Path) -> EnvFile:
    values: dict[str, str] = {}
    duplicate_keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_assignment(line)
        if parsed is None:
            continue
        key, value = parsed
        if key in values:
            duplicate_keys.add(key)
        values[key] = value
    return EnvFile(path=path, values=values, duplicate_keys=tuple(sorted(duplicate_keys)))


def _format_keys(keys: Collection[str]) -> str:
    return ", ".join(sorted(keys))


if __name__ == "__main__":
    sys.exit(main())
