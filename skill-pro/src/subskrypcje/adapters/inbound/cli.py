import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

import structlog

from subskrypcje.application.detect_subscriptions import DetectSubscriptions
from subskrypcje.application.errors import StatementNotFoundError
from subskrypcje.domain.models import SubscriptionReport

EXIT_OK = 0
EXIT_STATEMENT_NOT_FOUND = 1
COLUMN_GAP = "   "

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class CliArgs:
    statement: Path
    log_format: Literal["console", "json"]
    log_level: str


def parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    parser = argparse.ArgumentParser(
        prog="subskrypcje",
        description="Wykrywa subskrypcje na wyciągu bankowym w CSV.",
    )
    parser.add_argument("statement", type=Path, metavar="plik.csv", help="wyciąg bankowy w CSV")
    parser.add_argument(
        "--log-format",
        choices=("console", "json"),
        default="console",
        help="format logów na stderr (domyślnie: console)",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING"),
        default="INFO",
        help="minimalny poziom logów (domyślnie: INFO)",
    )
    namespace = parser.parse_args(argv)
    return CliArgs(
        statement=namespace.statement,
        log_format=namespace.log_format,
        log_level=namespace.log_level,
    )


def run(args: CliArgs, use_case: DetectSubscriptions) -> int:
    try:
        report = use_case.execute(args.statement)
    except StatementNotFoundError as error:
        log.error("statement_not_found", path=str(error.path))
        return EXIT_STATEMENT_NOT_FOUND
    _use_utf8_stdout()
    print(format_report(report))
    return EXIT_OK


def _use_utf8_stdout() -> None:
    """Redirected stdout on Windows defaults to the ANSI code page, which may lack "ł".

    With colored logs structlog lets colorama wrap sys.stdout. The wrapper forwards
    unknown attributes, so reconfigure still reaches the real stream.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


def format_report(report: SubscriptionReport) -> str:
    subscriptions = report.subscriptions
    if not subscriptions:
        return "Nie wykryto subskrypcji."

    monthly = [format_amount(s.monthly_cost) for s in subscriptions]
    yearly = [format_amount(s.yearly_cost) for s in subscriptions]
    name_width = max(len(s.name) for s in subscriptions)
    monthly_width = max(map(len, monthly))
    yearly_width = max(map(len, yearly))

    lines = [f"Wykryte subskrypcje: {len(subscriptions)}"]
    for subscription, monthly_cost, yearly_cost in zip(subscriptions, monthly, yearly, strict=True):
        line = (
            f"{subscription.name:<{name_width}}{COLUMN_GAP}"
            f"{monthly_cost:>{monthly_width}} zł/mies.{COLUMN_GAP}"
            f"{yearly_cost:>{yearly_width}} zł/rok"
        )
        if subscription.has_price_change:
            line += (
                f"{COLUMN_GAP}zmiana ceny: {format_amount(subscription.earliest_amount)}"
                f" -> {format_amount(subscription.latest_amount)}"
            )
        lines.append(line)
    lines.append(
        f"Razem: {format_amount(report.monthly_total)} zł/mies., "
        f"{format_amount(report.yearly_total)} zł/rok"
    )
    return "\n".join(lines)


def format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}".replace(".", ",")
