from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from subskrypcje.application.detect_subscriptions import DetectSubscriptions
from subskrypcje.application.errors import StatementNotFoundError
from subskrypcje.application.ports import SkippedRow, SkipReason, Statement
from subskrypcje.domain.models import Subscription, Transaction


class InMemoryStatementReader:
    def __init__(self, statement: Statement) -> None:
        self._statement = statement
        self.paths: list[Path] = []

    def read(self, path: Path) -> Statement:
        self.paths.append(path)
        return self._statement


class MissingStatementReader:
    def read(self, path: Path) -> Statement:
        raise StatementNotFoundError(path)


def netflix(day: str) -> Transaction:
    return Transaction(date.fromisoformat(day), "Netflix.com 4829", Decimal("-49.00"))


STATEMENT = Statement(
    transactions=(
        netflix("2026-06-05"),
        netflix("2026-05-05"),
        netflix("2026-04-05"),
        Transaction(date(2026, 4, 10), "ACME", Decimal("8500.00")),
    ),
    skipped_rows=(
        SkippedRow(line=14, reason=SkipReason.INVALID_AMOUNT),
        SkippedRow(line=30, reason=SkipReason.INVALID_DATE),
    ),
)


def test_execute_statement_from_reader_returns_detected_subscriptions() -> None:
    reader = InMemoryStatementReader(STATEMENT)

    report = DetectSubscriptions(reader).execute(Path("wyciag.csv"))

    assert reader.paths == [Path("wyciag.csv")]
    assert report.subscriptions == (
        Subscription("NETFLIX.COM", Decimal("49.00"), Decimal("49.00")),
    )


def test_execute_statement_logs_skipped_rows_and_counters_only() -> None:
    with capture_logs() as logs:
        DetectSubscriptions(InMemoryStatementReader(STATEMENT)).execute(Path("wyciag.csv"))

    assert logs == [
        {"event": "row_skipped", "log_level": "warning", "line": 14, "reason": "invalid_amount"},
        {"event": "row_skipped", "log_level": "warning", "line": 30, "reason": "invalid_date"},
        {"event": "statement_loaded", "log_level": "info", "rows_loaded": 4, "rows_skipped": 2},
        {"event": "subscriptions_detected", "log_level": "info", "count": 1},
    ]


def test_execute_missing_statement_raises_statement_not_found() -> None:
    use_case = DetectSubscriptions(MissingStatementReader())

    with pytest.raises(StatementNotFoundError) as error:
        use_case.execute(Path("brak.csv"))

    assert error.value.path == Path("brak.csv")
