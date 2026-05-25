"""Test bootstrap.

Loads `chorus/.env` so test runs use the same host-mapped service ports
(Postgres on 55432, Redpanda on 19092, etc.) as the Compose stack. The
hardcoded URL fallbacks in individual test modules are safety nets only;
the authoritative configuration is `.env`.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

if not ENV_FILE.is_file():
    raise RuntimeError(
        f"tests/conftest.py expected {ENV_FILE} to exist. "
        "Copy .env.example to .env or set the required environment variables "
        "before running the test suite."
    )

load_dotenv(ENV_FILE, override=False)
