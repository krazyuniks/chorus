"""Local environment helpers for doctor probes."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from chorus.doctor.scaffold import ROOT

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_local_env(path: Path | None = None) -> None:
    """Load repo-local ``.env`` values without overriding process env."""

    env_path = path or ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_assignment(line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def parse_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    key, separator, raw_value = stripped.partition("=")
    key = key.strip()
    if separator != "=" or not _ENV_KEY_RE.match(key):
        return None
    return key, _parse_env_value(raw_value)


def _parse_env_value(raw_value: str) -> str:
    lexer = shlex.shlex(raw_value, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    tokens = list(lexer)
    if not tokens:
        return ""
    return tokens[0]


def required_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value


def redacted_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid-url>"
    netloc = parts.netloc
    if parts.password is not None and "@" in netloc:
        auth, host = netloc.rsplit("@", 1)
        username = auth.split(":", 1)[0]
        netloc = f"{username}:***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
