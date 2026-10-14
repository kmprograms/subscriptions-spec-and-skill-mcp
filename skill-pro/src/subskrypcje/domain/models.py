from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MONTHS_PER_YEAR = 12


@dataclass(frozen=True, slots=True)
class Transaction:
    booked_on: date
    counterparty: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class Subscription:
    name: str
    earliest_amount: Decimal
    latest_amount: Decimal

    @property
    def monthly_cost(self) -> Decimal:
        return self.latest_amount

    @property
    def yearly_cost(self) -> Decimal:
        return self.monthly_cost * MONTHS_PER_YEAR

    @property
    def has_price_change(self) -> bool:
        return self.earliest_amount != self.latest_amount


@dataclass(frozen=True, slots=True)
class SubscriptionReport:
    subscriptions: tuple[Subscription, ...]

    @property
    def monthly_total(self) -> Decimal:
        return sum((s.monthly_cost for s in self.subscriptions), start=Decimal(0))

    @property
    def yearly_total(self) -> Decimal:
        return sum((s.yearly_cost for s in self.subscriptions), start=Decimal(0))
