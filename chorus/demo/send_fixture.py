"""Send a fixture email to the local Mailpit SMTP port."""

from __future__ import annotations

import argparse
import smtplib
import sys
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Path to an RFC 5322 email fixture.")
    parser.add_argument("--host", default="localhost", help="SMTP host. Defaults to localhost.")
    parser.add_argument("--port", default=1025, type=int, help="SMTP port. Defaults to 1025.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    fixture = args.fixture

    if not fixture.exists():
        print(f"fixture not found: {fixture}", file=sys.stderr)
        return 1

    message = BytesParser(policy=policy.default).parsebytes(fixture.read_bytes())
    sender = message.get("From")
    recipients = [address for _, address in getaddresses(message.get_all("To", []))]

    if not sender:
        print(f"fixture has no From header: {fixture}", file=sys.stderr)
        return 1
    if not recipients:
        print(f"fixture has no To recipients: {fixture}", file=sys.stderr)
        return 1

    try:
        with smtplib.SMTP(args.host, args.port, timeout=10) as smtp:
            smtp.send_message(message, from_addr=sender, to_addrs=recipients)
    except OSError as exc:
        print(f"failed to send fixture to {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1

    print(f"sent {fixture} to {', '.join(recipients)} via {args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
