"""Validate Chorus contract schemas, samples, and generated model drift."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from chorus.contracts.gen import generate_all, schema_files

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = ROOT / "contracts"
REQUIRED_DIRS = ["events", "agents", "tools", "eval", "governance"]


def _contract_name(schema: Path) -> str:
    return schema.name.removesuffix(".schema.json")


def _sample_path(schema: Path) -> Path:
    return schema.parent / "samples" / f"{_contract_name(schema)}.sample.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _format_error(error: ValidationError) -> str:
    location = error.json_path if error.json_path != "$" else "document"
    return f"{location}: {error.message}"


def _validate_schema(schema_path: Path) -> int:
    try:
        schema = _load_json(schema_path)
        Draft202012Validator.check_schema(schema)
    except json.JSONDecodeError as exc:
        print(f"fail - invalid JSON in {schema_path.relative_to(ROOT)}: {exc}")
        return 1
    except SchemaError as exc:
        print(f"fail - invalid JSON Schema in {schema_path.relative_to(ROOT)}: {exc.message}")
        return 1

    print(f"ok - schema {schema_path.relative_to(ROOT)}")
    return 0


def _validate_event_subject(schema_path: Path) -> int:
    if schema_path.parent.name != "events":
        return 0

    try:
        schema = _load_json(schema_path)
    except json.JSONDecodeError as exc:
        print(f"fail - invalid JSON in {schema_path.relative_to(ROOT)}: {exc}")
        return 1

    subject = schema.get("x-subject")
    if isinstance(subject, str) and subject:
        print(f"ok - event subject {schema_path.relative_to(ROOT)} -> {subject}")
        return 0

    print(f"fail - event schema {schema_path.relative_to(ROOT)} missing x-subject")
    return 1


def _validate_sample(schema_path: Path) -> int:
    sample_path = _sample_path(schema_path)
    if not sample_path.exists():
        print(f"fail - missing sample for {schema_path.relative_to(ROOT)}")
        return 1

    try:
        schema = _load_json(schema_path)
        sample = _load_json(sample_path)
    except json.JSONDecodeError as exc:
        print(f"fail - invalid JSON for {sample_path.relative_to(ROOT)}: {exc}")
        return 1

    validator: Any = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        cast(Iterable[ValidationError], validator.iter_errors(sample)),
        key=lambda error: error.json_path,
    )
    if errors:
        print(f"fail - sample {sample_path.relative_to(ROOT)}")
        for error in errors:
            print(f"  {_format_error(error)}")
        return 1

    print(f"ok - sample {sample_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    failures = 0

    missing = [name for name in REQUIRED_DIRS if not (CONTRACT_ROOT / name).is_dir()]
    if missing:
        for name in missing:
            print(f"fail - missing contracts/{name}")
        failures += len(missing)

    if not failures:
        print("ok - contract directories present")

    schemas = schema_files()
    if not schemas:
        print("fail - no JSON Schema files found")
        return 1

    print(f"found {len(schemas)} schema file(s)")

    for schema in schemas:
        failures += _validate_schema(schema)
        failures += _validate_event_subject(schema)
        failures += _validate_sample(schema)

    failures += generate_all(check=True)

    if failures:
        print(f"\n{failures} contract check(s) failed")
        return 1

    print("\nContract schemas, samples, and generated models are current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
