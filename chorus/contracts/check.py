"""Validate the Phase 0 contract scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"
REQUIRED_DIRS = ["events", "agents", "tools", "eval"]


def main() -> int:
    missing = [name for name in REQUIRED_DIRS if not (CONTRACT_ROOT / name).is_dir()]
    if missing:
        for name in missing:
            print(f"fail - missing contracts/{name}")
        return 1

    schemas = sorted(CONTRACT_ROOT.glob("**/*.schema.json"))
    print("ok - contract directories present")
    if schemas:
        print(f"found {len(schemas)} schema file(s)")
    else:
        print("no JSON Schema files found yet; Phase 0 contract drafts will populate contracts/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
