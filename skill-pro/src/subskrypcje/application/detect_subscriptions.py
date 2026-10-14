from pathlib import Path

import structlog

from subskrypcje.application.ports import StatementReader
from subskrypcje.domain.detection import detect_subscriptions
from subskrypcje.domain.models import SubscriptionReport

log = structlog.get_logger()


class DetectSubscriptions:
    def __init__(self, reader: StatementReader) -> None:
        self._reader = reader

    def execute(self, path: Path) -> SubscriptionReport:
        statement = self._reader.read(path)
        for row in statement.skipped_rows:
            log.warning("row_skipped", line=row.line, reason=row.reason.value)
        log.info(
            "statement_loaded",
            rows_loaded=len(statement.transactions),
            rows_skipped=len(statement.skipped_rows),
        )

        report = SubscriptionReport(detect_subscriptions(statement.transactions))
        log.info("subscriptions_detected", count=len(report.subscriptions))
        return report
