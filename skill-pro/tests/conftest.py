from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import structlog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEADER = "data;kontrahent;tytul;kwota"

type StatementFactory = Callable[..., Path]


@pytest.fixture(autouse=True)
def reset_structlog() -> Iterator[None]:
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


@pytest.fixture
def sample_statement() -> Path:
    return PROJECT_ROOT / "data" / "wyciag-przyklad.csv"


@pytest.fixture
def make_statement(tmp_path: Path) -> StatementFactory:
    """Writes a CSV statement with the header and the given data rows."""

    def make(*rows: str) -> Path:
        path = tmp_path / "wyciag.csv"
        path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
        return path

    return make
