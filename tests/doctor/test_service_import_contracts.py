from __future__ import annotations

from pathlib import Path

from chorus.doctor.service_import_contracts import (
    ServiceImportContract,
    analyse_service_imports,
    check_service_import_contracts,
    service_mapping_errors,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_transitive_chorus_import_requires_service_dependency(tmp_path: Path) -> None:
    _write(tmp_path / "chorus/service/app.py", "from chorus.shared.client import fetch\n")
    _write(tmp_path / "chorus/shared/client.py", "import httpx\n")
    _write(
        tmp_path / "services/example/pyproject.toml",
        """
[project]
name = "example"
version = "0.0.0"
dependencies = []
""".lstrip(),
    )
    _write(
        tmp_path / "services/example/Dockerfile",
        'CMD ["python", "-m", "chorus.service.app"]\n',
    )

    report = analyse_service_imports(
        tmp_path,
        ServiceImportContract(
            service_dir=Path("services/example"),
            entrypoint_modules=("chorus.service.app",),
            dockerfile_entrypoint_refs=("chorus.service.app",),
        ),
    )

    assert report.missing == {"httpx": (Path("chorus/shared/client.py"),)}


def test_type_checking_imports_do_not_create_runtime_dependencies(tmp_path: Path) -> None:
    _write(
        tmp_path / "chorus/service/app.py",
        """
from typing import TYPE_CHECKING

import pydantic

if TYPE_CHECKING:
    import openai
""".lstrip(),
    )
    _write(
        tmp_path / "services/example/pyproject.toml",
        """
[project]
name = "example"
version = "0.0.0"
dependencies = ["pydantic>=2"]
""".lstrip(),
    )
    _write(
        tmp_path / "services/example/Dockerfile",
        'CMD ["python", "-m", "chorus.service.app"]\n',
    )

    report = analyse_service_imports(
        tmp_path,
        ServiceImportContract(
            service_dir=Path("services/example"),
            entrypoint_modules=("chorus.service.app",),
            dockerfile_entrypoint_refs=("chorus.service.app",),
        ),
    )

    assert report.ok
    assert "openai" not in report.required_imports


def test_service_mapping_requires_every_runtime_pyproject_to_be_configured(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "services/example/pyproject.toml",
        """
[project]
name = "example"
version = "0.0.0"
dependencies = []
""".lstrip(),
    )
    _write(
        tmp_path / "services/_template/pyproject.toml",
        """
[project]
name = "template"
version = "0.0.0"
dependencies = []
""".lstrip(),
    )

    assert service_mapping_errors(tmp_path, contracts=()) == (
        "services/example has a pyproject.toml but no service import contract",
    )


def test_current_service_import_contracts_are_clean() -> None:
    mapping_errors = service_mapping_errors()
    reports = check_service_import_contracts()

    assert mapping_errors == ()
    assert {report.service_dir for report in reports} == {
        Path("services/bff"),
        Path("services/intake-poller"),
    }
    assert all(report.ok for report in reports)

    required_by_service = {report.service_dir: set(report.required_imports) for report in reports}
    assert required_by_service[Path("services/bff")] >= {
        "fastapi",
        "opentelemetry",
        "psycopg",
        "pydantic",
    }
    assert required_by_service[Path("services/intake-poller")] >= {
        "httpx",
        "jsonschema",
        "openai",
        "opentelemetry",
        "psycopg",
        "pydantic",
        "temporalio",
    }
