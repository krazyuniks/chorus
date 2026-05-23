"""Generate Pydantic models from Chorus JSON Schema contracts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"
GENERATED_ROOT = ROOT / "chorus" / "contracts" / "generated"

PACKAGE_INIT = '"""Generated Pydantic models for Chorus contract schemas."""\n'
PORT_INIT = '"""Generated Pydantic models for this contract port."""\n'


def schema_files() -> list[Path]:
    """Return canonical JSON Schema files in deterministic order."""
    return sorted(CONTRACT_ROOT.rglob("*.schema.json"))


def model_output_path(schema: Path) -> Path:
    """Map a contract schema path to its generated Python module path."""
    rel = schema.relative_to(CONTRACT_ROOT)
    name = rel.name.removesuffix(".schema.json")
    return GENERATED_ROOT / rel.parent / f"{name}.py"


def _expected_package_files(schemas: list[Path]) -> dict[Path, str]:
    """Collect every __init__.py path required to host the generated tree."""
    expected: dict[Path, str] = {GENERATED_ROOT / "__init__.py": PACKAGE_INIT}
    for schema in schemas:
        module = model_output_path(schema)
        directory = module.parent
        while directory != GENERATED_ROOT:
            expected.setdefault(directory / "__init__.py", PORT_INIT)
            directory = directory.parent
    return expected


def _codegen_command(schema: Path, output: Path, *, check: bool) -> list[str]:
    command = [
        "datamodel-codegen",
        "--input",
        str(schema),
        "--input-file-type",
        "jsonschema",
        "--schema-version",
        "2020-12",
        "--output",
        str(output),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-pydantic-version",
        "2.11",
        "--target-python-version",
        "3.14",
        "--formatters",
        "isort",
        "ruff-format",
        "--extra-fields",
        "forbid",
        "--field-constraints",
        "--use-annotated",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-title-as-name",
        "--capitalise-enum-members",
        "--disable-timestamp",
        "--no-allow-remote-refs",
    ]
    if check:
        command.append("--check")
    return command


def _ensure_package_files(schemas: list[Path], *, check: bool) -> list[str]:
    expected = _expected_package_files(schemas)
    failures: list[str] = []
    for path, content in expected.items():
        if check:
            if not path.exists():
                failures.append(f"missing generated package file: {path.relative_to(ROOT)}")
            elif path.read_text() != content:
                failures.append(f"generated package file is stale: {path.relative_to(ROOT)}")
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    return failures


def generate_all(*, check: bool = False) -> int:
    """Generate or drift-check all contract-derived model modules."""
    schemas = schema_files()
    if not schemas:
        print("no JSON Schema files found; generated models are a no-op")
        return 0

    package_failures = _ensure_package_files(schemas, check=check)
    if package_failures:
        for failure in package_failures:
            print(f"fail - {failure}")
        return 1

    failures = 0
    for schema in schemas:
        output = model_output_path(schema)
        if not check:
            output.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            _codegen_command(schema, output, check=check),
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            action = "checked" if check else "generated"
            print(f"ok - {action} {output.relative_to(ROOT)}")
            continue

        failures += 1
        print(f"fail - {schema.relative_to(ROOT)}")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())

    return 1 if failures else 0


def main() -> int:
    return generate_all(check=False)


if __name__ == "__main__":
    sys.exit(main())
