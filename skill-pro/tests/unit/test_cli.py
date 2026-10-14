from decimal import Decimal
from pathlib import Path

import pytest

from subskrypcje.adapters.inbound.cli import CliArgs, format_amount, format_report, parse_args
from subskrypcje.domain.models import Subscription, SubscriptionReport


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("4.99"), "4,99"),
        (Decimal("139"), "139,00"),
        (Decimal("2639.76"), "2639,76"),
        (Decimal("1234567.5"), "1234567,50"),
    ],
)
def test_format_amount_any_value_has_two_decimals_comma_and_no_thousands_separator(
    amount: Decimal, expected: str
) -> None:
    assert format_amount(amount) == expected


def test_format_report_without_subscriptions_returns_message() -> None:
    assert format_report(SubscriptionReport(())) == "Nie wykryto subskrypcji."


def test_format_report_with_subscriptions_lists_rows_price_change_and_total() -> None:
    report = SubscriptionReport(
        (
            Subscription("CITYFIT SP. Z O.O.", Decimal("139.00"), Decimal("139.00")),
            Subscription("SPOTIFY AB STOCKHOLM", Decimal("23.99"), Decimal("26.99")),
        )
    )

    assert format_report(report).splitlines() == [
        "Wykryte subskrypcje: 2",
        "CITYFIT SP. Z O.O.     139,00 zł/mies.   1668,00 zł/rok",
        "SPOTIFY AB STOCKHOLM    26,99 zł/mies.    323,88 zł/rok   zmiana ceny: 23,99 -> 26,99",
        "Razem: 165,99 zł/mies., 1991,88 zł/rok",
    ]


def test_parse_args_only_statement_uses_console_format_and_info_level() -> None:
    assert parse_args(["wyciag.csv"]) == CliArgs(
        statement=Path("wyciag.csv"), log_format="console", log_level="INFO"
    )


def test_parse_args_log_options_are_read() -> None:
    args = parse_args(["wyciag.csv", "--log-format", "json", "--log-level", "WARNING"])

    assert (args.log_format, args.log_level) == ("json", "WARNING")


@pytest.mark.parametrize(
    "argv",
    [[], ["wyciag.csv", "--log-format", "xml"], ["wyciag.csv", "--log-level", "ERROR"]],
)
def test_parse_args_invalid_arguments_exit_with_code_2(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        parse_args(argv)

    assert error.value.code == 2
