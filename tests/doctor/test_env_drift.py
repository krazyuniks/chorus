from __future__ import annotations

from pathlib import Path

from chorus.doctor.env_drift import env_drift_report


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_env_drift_accepts_matching_files_and_secret_value_differences(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    _write(
        env_path,
        """
PORT=1234
OPENAI_API_KEY=local-secret
CHORUS_PG_PASSWORD=local-password
""".lstrip(),
    )
    _write(
        example_path,
        """
PORT=1234
OPENAI_API_KEY=
CHORUS_PG_PASSWORD=example-password
""".lstrip(),
    )

    report = env_drift_report(env_path, example_path)

    assert report.ok
    assert report.failure_messages() == ()


def test_env_drift_reports_key_value_and_duplicate_failures(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    _write(
        env_path,
        """
PORT=4321
ONLY_ENV=true
DUPLICATE=first
DUPLICATE=second
""".lstrip(),
    )
    _write(
        example_path,
        """
PORT=1234
ONLY_EXAMPLE=true
""".lstrip(),
    )

    report = env_drift_report(env_path, example_path)

    assert not report.ok
    assert report.duplicate_env_keys == ("DUPLICATE",)
    assert report.keys_missing_from_env == ("ONLY_EXAMPLE",)
    assert report.keys_missing_from_example == ("DUPLICATE", "ONLY_ENV")
    assert report.value_mismatches == ("PORT",)
    assert report.failure_messages() == (
        ".env declares duplicate keys: DUPLICATE",
        ".env is missing keys declared by .env.example: ONLY_EXAMPLE",
        ".env declares keys absent from .env.example: DUPLICATE, ONLY_ENV",
        "non-secret .env values differ from .env.example: PORT",
    )


def test_env_drift_reports_missing_files(tmp_path: Path) -> None:
    report = env_drift_report(tmp_path / ".env", tmp_path / ".env.example")

    assert not report.ok
    assert report.failure_messages() == (
        "missing .env - run 'just env' before linting",
        "missing .env.example - run 'just env' before linting",
    )
