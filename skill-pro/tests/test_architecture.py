import ast
from pathlib import Path

PACKAGE = "subskrypcje"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / PACKAGE

IO_MODULES = ("os", "sys", "io", "pathlib", "csv", "json", "logging")
FORBIDDEN_IN_DOMAIN = (
    f"{PACKAGE}.application",
    f"{PACKAGE}.adapters",
    f"{PACKAGE}.main",
    "structlog",
    *IO_MODULES,
)
FORBIDDEN_IN_APPLICATION = (f"{PACKAGE}.adapters", f"{PACKAGE}.main")
OUTBOUND_ADAPTERS = f"{PACKAGE}.adapters.outbound"


def module_name(path: Path) -> str:
    parts = path.relative_to(PACKAGE_DIR.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imported_modules(source: str, module: str, is_package: bool) -> set[str]:
    """Absolute names of all imported modules, relative imports resolved."""
    package = module.split(".") if is_package else module.split(".")[:-1]
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            target = ".".join([*base, *([node.module] if node.module else [])])
            found.add(target)
            found.update(f"{target}.{alias.name}" for alias in node.names)
    return found


def imports_of(path: Path) -> set[str]:
    return imported_modules(
        path.read_text(encoding="utf-8"), module_name(path), path.name == "__init__.py"
    )


def violations(layer: str, forbidden: tuple[str, ...]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in sorted((PACKAGE_DIR / layer).rglob("*.py")):
        bad = sorted(
            name for name in imports_of(path) for prefix in forbidden if _within(name, prefix)
        )
        if bad:
            result[module_name(path)] = bad
    return result


def _within(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(f"{prefix}.")


def test_import_parser_relative_imports_resolve_to_absolute_names() -> None:
    source = (
        "from ..adapters import cli\nfrom . import models\nfrom .models import X\nimport os.path\n"
    )

    found = imported_modules(source, f"{PACKAGE}.domain.detection", is_package=False)

    assert found == {
        f"{PACKAGE}.adapters",
        f"{PACKAGE}.adapters.cli",
        f"{PACKAGE}.domain",
        f"{PACKAGE}.domain.models",
        f"{PACKAGE}.domain.models.X",
        "os.path",
    }


def test_import_parser_relative_import_in_package_init_resolves_from_package() -> None:
    found = imported_modules("from .models import X\n", f"{PACKAGE}.domain", is_package=True)

    assert f"{PACKAGE}.domain.models" in found


def test_layers_scanned_contain_expected_modules() -> None:
    domain = {p.name for p in (PACKAGE_DIR / "domain").rglob("*.py")}
    application = {p.name for p in (PACKAGE_DIR / "application").rglob("*.py")}

    assert {"models.py", "detection.py"} <= domain
    assert {"ports.py", "errors.py", "detect_subscriptions.py"} <= application


def test_domain_imports_no_outer_layers_logging_or_io() -> None:
    assert violations("domain", FORBIDDEN_IN_DOMAIN) == {}


def test_application_imports_no_adapters_or_main() -> None:
    assert violations("application", FORBIDDEN_IN_APPLICATION) == {}


def test_only_main_imports_outbound_adapters() -> None:
    importers = sorted(
        module_name(path)
        for path in PACKAGE_DIR.rglob("*.py")
        if not _within(module_name(path), OUTBOUND_ADAPTERS)
        and any(_within(name, OUTBOUND_ADAPTERS) for name in imports_of(path))
    )

    assert importers == [f"{PACKAGE}.main"]
