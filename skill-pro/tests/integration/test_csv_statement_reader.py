from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from subskrypcje.adapters.outbound.csv_statement_reader import CsvStatementReader
from subskrypcje.application.errors import StatementNotFoundError
from subskrypcje.application.ports import SkippedRow, SkipReason
from subskrypcje.domain.detection import (
    group_expenses,
    has_enough_payments,
    has_monthly_intervals,
    has_stable_amounts,
)
from subskrypcje.domain.models import Transaction


def test_read_valid_rows_parses_date_counterparty_and_amount(
    make_statement: Callable[..., Path],
) -> None:
    path = make_statement(
        "2026-09-05;Netflix.com 4829;Płatność kartą;-49,99",
        "2026-09-10;ACME SP. Z O.O.;Wynagrodzenie;8500,00",
    )

    statement = CsvStatementReader().read(path)

    assert statement.transactions == (
        Transaction(date(2026, 9, 5), "Netflix.com 4829", Decimal("-49.99")),
        Transaction(date(2026, 9, 10), "ACME SP. Z O.O.", Decimal("8500.00")),
    )
    assert statement.skipped_rows == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [("-1 299,00", Decimal("-1299.00")), ("- 1 299,5", Decimal("-1299.5")), ("12", Decimal(12))],
)
def test_read_amount_with_spaces_or_without_decimals_is_parsed(
    make_statement: Callable[..., Path], text: str, expected: Decimal
) -> None:
    path = make_statement(f"2026-06-15;MEDIA EXPERT;Telewizor;{text}")

    (transaction,) = CsvStatementReader().read(path).transactions

    assert transaction.amount == expected


@pytest.mark.parametrize("amount", ["abc", "-4O,15", "-4.99", "", "-49,999", "NaN", "1e3"])
def test_read_invalid_amount_row_is_skipped_with_line_number(
    make_statement: Callable[..., Path], amount: str
) -> None:
    path = make_statement(
        "2026-09-05;NETFLIX.COM;Płatność kartą;-49,00",
        f"2026-08-14;ZABKA Z1234 KRAKOW;Zakupy;{amount}",
    )

    statement = CsvStatementReader().read(path)

    assert len(statement.transactions) == 1
    assert statement.skipped_rows == (SkippedRow(line=3, reason=SkipReason.INVALID_AMOUNT),)


@pytest.mark.parametrize(
    "day", ["2026-06-31", "27.06.2026", "2026-6-1", "20260601", "2026-W24-1", ""]
)
def test_read_invalid_date_row_is_skipped_with_line_number(
    make_statement: Callable[..., Path], day: str
) -> None:
    path = make_statement(f"{day};ZABKA Z1234 KRAKOW;Zakupy;-12,50")

    statement = CsvStatementReader().read(path)

    assert statement.transactions == ()
    assert statement.skipped_rows == (SkippedRow(line=2, reason=SkipReason.INVALID_DATE),)


def test_read_row_with_invalid_date_and_amount_reports_invalid_date(
    make_statement: Callable[..., Path],
) -> None:
    path = make_statement("2026-13-01;ZABKA;Zakupy;abc")

    statement = CsvStatementReader().read(path)

    assert statement.skipped_rows == (SkippedRow(line=2, reason=SkipReason.INVALID_DATE),)


def test_read_row_without_amount_column_is_skipped_as_invalid_amount(
    make_statement: Callable[..., Path],
) -> None:
    path = make_statement("2026-09-05;NETFLIX.COM")

    statement = CsvStatementReader().read(path)

    assert statement.skipped_rows == (SkippedRow(line=2, reason=SkipReason.INVALID_AMOUNT),)


def test_read_blank_line_is_ignored_and_keeps_file_line_numbers(
    make_statement: Callable[..., Path],
) -> None:
    path = make_statement("2026-09-05;NETFLIX.COM;Płatność;-49,00", "", "2026-09-06;X;Y;abc")

    statement = CsvStatementReader().read(path)

    assert len(statement.transactions) == 1
    assert statement.skipped_rows == (SkippedRow(line=4, reason=SkipReason.INVALID_AMOUNT),)


def test_read_missing_file_raises_statement_not_found_with_path(tmp_path: Path) -> None:
    path = tmp_path / "brak.csv"

    with pytest.raises(StatementNotFoundError) as error:
        CsvStatementReader().read(path)

    assert error.value.path == path


def test_read_sample_statement_loads_55_rows_and_skips_lines_14_and_30(
    sample_statement: Path,
) -> None:
    statement = CsvStatementReader().read(sample_statement)

    assert len(statement.transactions) == 55
    assert statement.skipped_rows == (
        SkippedRow(line=14, reason=SkipReason.INVALID_AMOUNT),
        SkippedRow(line=30, reason=SkipReason.INVALID_DATE),
    )


def test_sample_statement_income_is_not_grouped_as_expense(sample_statement: Path) -> None:
    transactions = CsvStatementReader().read(sample_statement).transactions

    assert "ACME SOFTWARE SP. Z O.O." not in group_expenses(transactions)
    assert [t.amount for t in transactions if t.counterparty.startswith("ACME")] == [
        Decimal("8500.00")
    ] * 6


@pytest.mark.parametrize(
    ("name", "enough_payments", "monthly_intervals", "stable_amounts"),
    [
        ("ORLEN STACJA NR", True, True, False),
        ("BIEDRONKA KRAKOW", True, False, False),
        ("ALLEGRO.PL", False, False, False),
        ("MEDIA EXPERT", False, True, True),
        ("TAURON SPRZEDAZ", True, False, True),
    ],
)
def test_sample_statement_rejected_group_fails_only_expected_rules(
    sample_statement: Path,
    name: str,
    enough_payments: bool,
    monthly_intervals: bool,
    stable_amounts: bool,
) -> None:
    groups = group_expenses(CsvStatementReader().read(sample_statement).transactions)
    payments = groups[name]

    assert (
        has_enough_payments(payments),
        has_monthly_intervals(payments),
        has_stable_amounts(payments),
    ) == (enough_payments, monthly_intervals, stable_amounts)
