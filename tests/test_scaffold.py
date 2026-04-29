from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase_0_scaffold_paths_exist() -> None:
    for relative in [
        "README.md",
        "docs/overview.md",
        "docs/architecture.md",
        "docs/evidence-map.md",
        "adrs/README.md",
        "compose.yml",
        "justfile",
        "contracts/events",
        "services/intake-poller",
        "services/connectors-local",
    ]:
        assert (ROOT / relative).exists(), relative


def test_fixture_email_has_intake_headers() -> None:
    fixture = ROOT / "docs/fixtures/lead-acme.eml"
    message = BytesParser(policy=policy.default).parsebytes(fixture.read_bytes())

    assert message["To"] == "leads@chorus.local"
    assert message["Message-ID"]
    assert message.get_content().strip()
