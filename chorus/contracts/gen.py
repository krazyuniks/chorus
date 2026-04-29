"""Generate contract-derived models when schemas exist."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"


def main() -> int:
    schemas = sorted(CONTRACT_ROOT.glob("**/*.schema.json"))
    if not schemas:
        print("no JSON Schema files found; generated models are a no-op for the Phase 0 scaffold")
        return 0

    print("model generation is not wired yet; Phase 0 only declares the contract scaffold")
    print("schemas:")
    for schema in schemas:
        print(f"- {schema.relative_to(ROOT)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
