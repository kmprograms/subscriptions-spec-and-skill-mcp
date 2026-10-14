import csv
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from subskrypcje.application.errors import StatementNotFoundError
from subskrypcje.application.ports import SkippedRow, SkipReason, Statement
from subskrypcje.domain.models import Transaction

DELIMITER = ";"
DATE_COLUMN = 0
COUNTERPARTY_COLUMN = 1
AMOUNT_COLUMN = 3

_DATE_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_AMOUNT_FORMAT = re.compile(r"-?[0-9]+(?:,[0-9]{1,2})?")


class CsvStatementReader:
    def read(self, path: Path) -> Statement:
        try:
            with path.open(encoding="utf-8", newline="") as file:
                return _parse(file)
        except FileNotFoundError as error:
            raise StatementNotFoundError(path) from error


def _parse(file: TextIO) -> Statement:
    transactions: list[Transaction] = []
    skipped_rows: list[SkippedRow] = []
    reader = csv.reader(file, delimiter=DELIMITER)
    next(reader, None)  # header, line 1
    for fields in reader:
        if not fields:
            continue
        result = _parse_row(fields)
        if isinstance(result, SkipReason):
            skipped_rows.append(SkippedRow(line=reader.line_num, reason=result))
        else:
            transactions.append(result)
    return Statement(transactions=tuple(transactions), skipped_rows=tuple(skipped_rows))


def _parse_row(fields: list[str]) -> Transaction | SkipReason:
    booked_on = _parse_date(_field(fields, DATE_COLUMN))
    if booked_on is None:
        return SkipReason.INVALID_DATE
    amount = _parse_amount(_field(fields, AMOUNT_COLUMN))
    if amount is None:
        return SkipReason.INVALID_AMOUNT
    return Transaction(
        booked_on=booked_on,
        counterparty=_field(fields, COUNTERPARTY_COLUMN),
        amount=amount,
    )


def _field(fields: list[str], index: int) -> str:
    return fields[index] if index < len(fields) else ""


def _parse_date(text: str) -> date | None:
    text = text.strip()
    if not _DATE_FORMAT.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_amount(text: str) -> Decimal | None:
    compact = "".join(text.split())
    if not _AMOUNT_FORMAT.fullmatch(compact):
        return None
    return Decimal(compact.replace(",", "."))
