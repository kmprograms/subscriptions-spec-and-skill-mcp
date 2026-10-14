import re
from pathlib import Path

from subskrypcje.adapters.outbound.csv_statement_reader import CsvStatementReader
from subskrypcje.application.detect_subscriptions import DetectSubscriptions
from subskrypcje.domain.models import SubscriptionReport

STATEMENT_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\.csv")
MAX_STATEMENT_BYTES = 5 * 1024 * 1024


class StatementAccessError(Exception):
    """The statement name is invalid or the file is not available in the data directory."""


class StatementStore:
    """Read-only access to bank statements stored in one data directory."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir.resolve(strict=True)
        self._detect = DetectSubscriptions(CsvStatementReader())

    def names(self) -> list[str]:
        return sorted(p.name for p in self._data_dir.glob("*.csv") if p.is_file())

    def report(self, name: str) -> SubscriptionReport:
        return self._detect.execute(self._resolve(name))

    def _resolve(self, name: str) -> Path:
        if not STATEMENT_NAME.fullmatch(name):
            raise StatementAccessError("Nazwa wyciagu musi mieć postać nazwa.csv, bez ścieżki")

        path = (self._data_dir / name).resolve()
        if not path.is_relative_to(self._data_dir):
            raise StatementAccessError("Wyciąg musi leżeć w katalogu danych")
        if not path.is_file():
            available = ", ".join(self.names()) or "brak"
            raise StatementAccessError(f"Nie ma wyciągu {name}. Dostępne: {available}")
        if path.stat().st_size > MAX_STATEMENT_BYTES:
            raise StatementAccessError("Plik wyciągu jest za duży")
        return path