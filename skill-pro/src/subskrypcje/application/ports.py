from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from subskrypcje.domain.models import Transaction


class SkipReason(StrEnum):
    INVALID_DATE = "invalid_date"
    INVALID_AMOUNT = "invalid_amount"


@dataclass(frozen=True, slots=True)
class SkippedRow:
    line: int
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class Statement:
    transactions: tuple[Transaction, ...]
    skipped_rows: tuple[SkippedRow, ...]


class StatementReader(Protocol):
    def read(self, path: Path) -> Statement:
        """Raises StatementNotFoundError when the statement does not exist."""
        ...
