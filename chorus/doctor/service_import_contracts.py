"""Per-service dependency contracts for service-owned Chorus entrypoints."""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_TEMPLATE_DIR = Path("services/_template")


@dataclass(frozen=True)
class ServiceImportContract:
    """Static contract between a service pyproject and its Chorus entrypoint."""

    service_dir: Path
    entrypoint_modules: tuple[str, ...]
    dockerfile_entrypoint_refs: tuple[str, ...]

    @property
    def pyproject_path(self) -> Path:
        return self.service_dir / "pyproject.toml"

    @property
    def dockerfile_path(self) -> Path:
        return self.service_dir / "Dockerfile"


@dataclass(frozen=True)
class ImportRequirement:
    """A third-party import root and the dependency declaration that covers it."""

    import_root: str
    dependency_names: tuple[str, ...]


@dataclass(frozen=True)
class ServiceDependencyReport:
    service_dir: Path
    entrypoint_modules: tuple[str, ...]
    visited_modules: tuple[Path, ...]
    required_imports: Mapping[str, tuple[Path, ...]]
    missing: Mapping[str, tuple[Path, ...]]
    unknown_imports: Mapping[str, tuple[Path, ...]]
    mapping_errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.unknown_imports and not self.mapping_errors


SERVICE_IMPORT_CONTRACTS: tuple[ServiceImportContract, ...] = (
    ServiceImportContract(
        service_dir=Path("services/bff"),
        entrypoint_modules=("chorus.bff.app",),
        dockerfile_entrypoint_refs=("chorus.bff.app:app",),
    ),
    ServiceImportContract(
        service_dir=Path("services/intake-poller"),
        entrypoint_modules=("chorus.workflows.worker",),
        dockerfile_entrypoint_refs=("chorus.workflows.worker",),
    ),
)

IMPORT_REQUIREMENTS: Mapping[str, ImportRequirement] = {
    "confluent_kafka": ImportRequirement("confluent_kafka", ("confluent-kafka",)),
    "fastapi": ImportRequirement("fastapi", ("fastapi",)),
    "httpx": ImportRequirement("httpx", ("httpx",)),
    "jsonschema": ImportRequirement("jsonschema", ("jsonschema",)),
    "openai": ImportRequirement("openai", ("openai",)),
    "opentelemetry": ImportRequirement("opentelemetry", ("opentelemetry-distro",)),
    "psycopg": ImportRequirement("psycopg", ("psycopg",)),
    "pydantic": ImportRequirement("pydantic", ("pydantic",)),
    "temporalio": ImportRequirement("temporalio", ("temporalio",)),
    "uvicorn": ImportRequirement("uvicorn", ("uvicorn",)),
}


class RuntimeImportVisitor(ast.NodeVisitor):
    """Collect runtime imports, skipping imports guarded by TYPE_CHECKING."""

    def __init__(self, current_module: str, is_package: bool) -> None:
        self.current_module = current_module
        self.is_package = is_package
        self.chorus_imports: set[str] = set()
        self.third_party_imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record_import(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = self._resolve_from_module(node)
        if not module:
            return
        self._record_import(module)
        if module.startswith("chorus."):
            for alias in node.names:
                if alias.name != "*":
                    self.chorus_imports.add(f"{module}.{alias.name}")

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_guard(node.test):
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if _is_import_module_call(node) and node.args:
            module_name = node.args[0]
            if isinstance(module_name, ast.Constant) and isinstance(module_name.value, str):
                self._record_import(module_name.value)
        self.generic_visit(node)

    def _record_import(self, module: str) -> None:
        if module == "chorus" or module.startswith("chorus."):
            self.chorus_imports.add(module)
            return

        import_root = module.split(".", maxsplit=1)[0]
        if _is_third_party_import(import_root):
            self.third_party_imports.add(import_root)

    def _resolve_from_module(self, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""

        package = self.current_module if self.is_package else self.current_module.rsplit(".", 1)[0]
        parts = package.split(".")
        if node.level > 1:
            parts = parts[: -(node.level - 1)]
        if node.module:
            parts.extend(node.module.split("."))
        return ".".join(part for part in parts if part)


def analyse_service_imports(
    root: Path,
    contract: ServiceImportContract,
    *,
    import_requirements: Mapping[str, ImportRequirement] = IMPORT_REQUIREMENTS,
) -> ServiceDependencyReport:
    """Return the service dependency report for one configured service."""

    root = root.resolve()
    mapping_errors = (
        *_contract_mapping_errors(root, contract),
        *_entrypoint_mapping_errors(root, contract.entrypoint_modules),
    )
    pyproject_path = root / contract.pyproject_path
    declared_dependencies = (
        _declared_dependency_names(pyproject_path) if pyproject_path.is_file() else set[str]()
    )
    visited_modules, import_sources = _runtime_import_sources(root, contract.entrypoint_modules)

    missing: dict[str, tuple[Path, ...]] = {}
    unknown_imports: dict[str, tuple[Path, ...]] = {}
    required_imports: dict[str, tuple[Path, ...]] = {}

    for import_root, sources in sorted(import_sources.items()):
        sorted_sources = tuple(sorted(sources))
        requirement = import_requirements.get(import_root)
        if requirement is None:
            unknown_imports[import_root] = sorted_sources
            continue

        required_imports[import_root] = sorted_sources
        acceptable_dependencies = {
            _normalise_dependency_name(name) for name in requirement.dependency_names
        }
        if declared_dependencies.isdisjoint(acceptable_dependencies):
            missing[requirement.dependency_names[0]] = sorted_sources

    return ServiceDependencyReport(
        service_dir=contract.service_dir,
        entrypoint_modules=contract.entrypoint_modules,
        visited_modules=tuple(sorted(visited_modules)),
        required_imports=required_imports,
        missing=missing,
        unknown_imports=unknown_imports,
        mapping_errors=mapping_errors,
    )


def check_service_import_contracts(
    root: Path = REPO_ROOT,
    *,
    contracts: Sequence[ServiceImportContract] = SERVICE_IMPORT_CONTRACTS,
    import_requirements: Mapping[str, ImportRequirement] = IMPORT_REQUIREMENTS,
) -> tuple[ServiceDependencyReport, ...]:
    """Analyse every configured service dependency contract."""

    return tuple(
        analyse_service_imports(root, contract, import_requirements=import_requirements)
        for contract in contracts
    )


def service_mapping_errors(
    root: Path = REPO_ROOT,
    *,
    contracts: Sequence[ServiceImportContract] = SERVICE_IMPORT_CONTRACTS,
) -> tuple[str, ...]:
    """Return repository-level service mapping errors."""

    root = root.resolve()
    configured = {contract.service_dir for contract in contracts}
    pyproject_services = {
        path.parent.relative_to(root)
        for path in sorted((root / "services").glob("*/pyproject.toml"))
        if path.parent.relative_to(root) != SERVICE_TEMPLATE_DIR
    }

    errors: list[str] = []
    for service_dir in sorted(pyproject_services - configured):
        errors.append(f"{service_dir} has a pyproject.toml but no service import contract")
    for service_dir in sorted(configured - pyproject_services):
        errors.append(f"{service_dir} has a service import contract but no pyproject.toml")
    return tuple(errors)


def render_reports(
    reports: Sequence[ServiceDependencyReport],
    mapping_errors: Sequence[str],
) -> str:
    """Render a deterministic human-readable report."""

    lines: list[str] = ["Chorus service import contracts"]
    for error in mapping_errors:
        lines.append(f"fail: {error}")

    for report in sorted(reports, key=lambda item: item.service_dir.as_posix()):
        if report.ok:
            required = ", ".join(sorted(report.required_imports)) or "no third-party imports"
            lines.append(
                "ok: "
                f"{report.service_dir.as_posix()} declares dependencies for "
                f"{required} across {len(report.visited_modules)} Chorus module(s)"
            )
            continue

        for error in report.mapping_errors:
            lines.append(f"fail: {report.service_dir.as_posix()}: {error}")
        for import_root, sources in sorted(report.unknown_imports.items()):
            lines.append(
                "fail: "
                f"{report.service_dir.as_posix()} imports {import_root!r}, "
                "but the dependency mapping has no entry"
            )
            lines.extend(_source_lines(sources))
        for dependency_name, sources in sorted(report.missing.items()):
            lines.append(
                "fail: "
                f"{report.service_dir.as_posix()} missing dependency "
                f"{dependency_name!r} in pyproject.toml"
            )
            lines.extend(_source_lines(sources))

    return "\n".join(lines)


def check_service_import_contracts_command(root: Path = REPO_ROOT) -> int:
    """Doctor-style check function used by `python -m chorus.doctor`."""

    reports = check_service_import_contracts(root)
    mapping_errors = service_mapping_errors(root)
    print(render_reports(reports, mapping_errors))
    failure_count = sum(not report.ok for report in reports) + len(mapping_errors)
    return 1 if failure_count else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when service pyprojects do not declare dependencies required "
            "by their service-owned Chorus entrypoints."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to check. Defaults to the current Chorus checkout.",
    )
    args = parser.parse_args(argv)
    return check_service_import_contracts_command(args.root)


def _runtime_import_sources(
    root: Path,
    entrypoint_modules: Iterable[str],
) -> tuple[set[Path], dict[str, set[Path]]]:
    visited: set[str] = set()
    visited_paths: set[Path] = set()
    third_party_sources: dict[str, set[Path]] = defaultdict(set)
    pending = list(entrypoint_modules)

    while pending:
        module_name = pending.pop()
        resolved = _resolve_chorus_module(root, module_name)
        if resolved is None:
            continue

        resolved_module, module_path = resolved
        if resolved_module in visited:
            continue

        visited.add(resolved_module)
        relative_module_path = module_path.relative_to(root)
        visited_paths.add(relative_module_path)
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=module_path.as_posix())
        visitor = RuntimeImportVisitor(
            current_module=resolved_module,
            is_package=module_path.name == "__init__.py",
        )
        visitor.visit(tree)
        for import_root in visitor.third_party_imports:
            third_party_sources[import_root].add(relative_module_path)
        pending.extend(visitor.chorus_imports)

    return visited_paths, third_party_sources


def _resolve_chorus_module(root: Path, module_name: str) -> tuple[str, Path] | None:
    if module_name != "chorus" and not module_name.startswith("chorus."):
        return None

    parts = module_name.split(".")
    while parts:
        relative_path = Path(*parts)
        module_path = root / relative_path.with_suffix(".py")
        if module_path.is_file():
            return ".".join(parts), module_path

        package_path = root / relative_path / "__init__.py"
        if package_path.is_file():
            return ".".join(parts), package_path

        parts = parts[:-1]
    return None


def _declared_dependency_names(pyproject_path: Path) -> set[str]:
    with pyproject_path.open("rb") as pyproject_file:
        pyproject: dict[str, object] = tomllib.load(pyproject_file)
    project_obj = pyproject.get("project", {})
    if not isinstance(project_obj, dict):
        raise TypeError(f"{pyproject_path} [project] must be a table")
    project = cast(dict[str, object], project_obj)
    dependencies_obj = project.get("dependencies", [])
    if not isinstance(dependencies_obj, list):
        raise TypeError(f"{pyproject_path} [project].dependencies must be a list")
    dependencies = cast(list[object], dependencies_obj)
    dependency_names: set[str] = set()
    for dependency in dependencies:
        if not isinstance(dependency, str):
            raise TypeError(f"{pyproject_path} [project].dependencies entries must be strings")
        dependency_names.add(_normalise_dependency_name(dependency))
    return dependency_names


def _normalise_dependency_name(requirement: str) -> str:
    name_chars: list[str] = []
    for char in requirement:
        if char.isalnum() or char in {"-", "_", "."}:
            name_chars.append(char)
            continue
        break
    name = "".join(name_chars).lower()
    return name.replace("_", "-").replace(".", "-")


def _contract_mapping_errors(root: Path, contract: ServiceImportContract) -> Iterable[str]:
    pyproject_path = root / contract.pyproject_path
    dockerfile_path = root / contract.dockerfile_path
    if not pyproject_path.is_file():
        yield f"{contract.pyproject_path.as_posix()} is missing"
    if not dockerfile_path.is_file():
        yield f"{contract.dockerfile_path.as_posix()} is missing"
        return

    dockerfile_text = dockerfile_path.read_text(encoding="utf-8")
    for ref in contract.dockerfile_entrypoint_refs:
        if ref not in dockerfile_text:
            yield (
                f"{contract.dockerfile_path.as_posix()} does not reference configured "
                f"entrypoint {ref!r}"
            )


def _entrypoint_mapping_errors(root: Path, entrypoint_modules: Iterable[str]) -> Iterable[str]:
    for module_name in entrypoint_modules:
        if _resolve_chorus_module(root, module_name) is None:
            yield f"entrypoint module {module_name!r} does not resolve under chorus/"


def _source_lines(sources: Sequence[Path]) -> list[str]:
    return [f"      from {source.as_posix()}" for source in sources]


def _is_type_checking_guard(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    return False


def _is_import_module_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id == "import_module"
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "import_module"
    return False


def _is_third_party_import(import_root: str) -> bool:
    return (
        import_root != "__future__"
        and import_root != "chorus"
        and import_root not in sys.stdlib_module_names
    )


if __name__ == "__main__":
    sys.exit(main())
