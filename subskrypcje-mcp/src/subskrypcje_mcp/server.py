import os
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from subskrypcje.domain.models import SubscriptionReport
from subskrypcje.logging_config import configure_logging
from subskrypcje_mcp.schemas import PriceIncrease, PriceIncreases, SpendingSummary
from subskrypcje_mcp.statements import StatementAccessError, StatementStore

DEFAULT_STATEMENT = "wyciag-przyklad.csv"
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

StatementName = Annotated[
    str,
    Field(
        description="Nazwa pliku CSV z katalogu danych, bez ścieżki, np. wyciag-przyklad.csv.",
        pattern=r"^[A-Za-z0-9_-]{1,64}\.csv$",
    ),
]


def create_server(store: StatementStore) -> MCPServer:
    mcp = MCPServer(
        name="subskrypcje",
        instructions=(
            "Serwer tylko do odczytu. Udostępnia subskrypcje wykryte na wyciągu bankowym. "
            "Kwoty są w PLN."
        ),
    )

    def load_report(statement: str) -> SubscriptionReport:
        try:
            return store.report(statement)
        except StatementAccessError as error:
            raise ToolError(str(error)) from error

    @mcp.tool(annotations=READ_ONLY)
    def monthly_subscription_cost(statement: StatementName = DEFAULT_STATEMENT) -> SpendingSummary:
        """Zwraca sumę wydatków na subskrypcje w miesiącu i w roku oraz koszt każdej subskrypcji.

        Użyj, gdy użytkownik pyta, ile wydaje na subskrypcje.
        """
        return SpendingSummary.from_domain(statement, load_report(statement))

    @mcp.tool(annotations=READ_ONLY)
    def price_increases(
        statement: StatementName = DEFAULT_STATEMENT,
        min_increase_percent: Annotated[
            int, Field(ge=0, le=100, description="Minimalny wzrost ceny w procentach.")
        ] = 0,
    ) -> PriceIncreases:
        """Zwraca subskrypcje, które podrożały: starą i nową cenę oraz wzrost w zł i w %."""
        increases = [
            PriceIncrease.from_domain(s)
            for s in load_report(statement).subscriptions
            if s.latest_amount > s.earliest_amount
        ]
        return PriceIncreases(
            statement=statement,
            min_increase_percent=min_increase_percent,
            subscriptions=[i for i in increases if i.increase_percent >= min_increase_percent],
        )

    @mcp.resource("subskrypcje://raport", mime_type="application/json")
    def report() -> str:
        """Pełny raport subskrypcji z domyślnego wyciągu w formacie JSON."""
        summary = SpendingSummary.from_domain(DEFAULT_STATEMENT, store.report(DEFAULT_STATEMENT))
        return summary.model_dump_json(indent=2)

    return mcp


def main() -> None:
    configure_logging("INFO", "json")
    data_dir = Path(os.environ.get("SUBSKRYPCJE_DATA_DIR", "data"))
    create_server(StatementStore(data_dir)).run()