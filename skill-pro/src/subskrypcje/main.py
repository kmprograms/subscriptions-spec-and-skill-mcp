import uuid

import structlog

from subskrypcje.adapters.inbound import cli
from subskrypcje.adapters.outbound.csv_statement_reader import CsvStatementReader
from subskrypcje.application.detect_subscriptions import DetectSubscriptions
from subskrypcje.logging_config import configure_logging


def main(argv: list[str] | None = None) -> int:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=uuid.uuid4().hex)

    args = cli.parse_args(argv)
    configure_logging(args.log_level, args.log_format)

    use_case = DetectSubscriptions(CsvStatementReader())
    return cli.run(args, use_case)
