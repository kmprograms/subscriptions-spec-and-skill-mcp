from decimal import Decimal
from pydantic import BaseModel
from subskrypcje.domain.models import Subscription, SubscriptionReport

PERCENT = Decimal(100)


class SubscriptionCost(BaseModel):
    """Koszt jednej subskrypcji: kwota miesięczna i roczna."""

    name: str
    monthly_cost: Decimal
    yearly_cost: Decimal

    @classmethod
    def from_domain(cls, subscription: Subscription) -> SubscriptionCost:
        return cls(
            name=subscription.name,
            monthly_cost=subscription.monthly_cost,
            yearly_cost=subscription.yearly_cost,
        )


class SpendingSummary(BaseModel):
    """Wynik narzędzia monthly_subscription_cost: suma kosztów i koszt każdej subskrypcji."""

    statement: str
    currency: str = "PLN"
    subscription_count: int
    monthly_total: Decimal
    yearly_total: Decimal
    subscriptions: list[SubscriptionCost]

    @classmethod
    def from_domain(cls, statement: str, report: SubscriptionReport) -> SpendingSummary:
        return cls(
            statement=statement,
            subscription_count=len(report.subscriptions),
            monthly_total=report.monthly_total,
            yearly_total=report.yearly_total,
            subscriptions=[SubscriptionCost.from_domain(s) for s in report.subscriptions],
        )


class PriceIncrease(BaseModel):
    """Podwyżka ceny jednej subskrypcji i jej dodatkowy koszt w skali roku."""

    name: str
    old_price: Decimal
    new_price: Decimal
    increase: Decimal
    increase_percent: Decimal
    extra_yearly_cost: Decimal

    @classmethod
    def from_domain(cls, subscription: Subscription) -> PriceIncrease:
        old, new = subscription.earliest_amount, subscription.latest_amount
        increase = new - old
        return cls(
            name=subscription.name,
            old_price=old,
            new_price=new,
            increase=increase,
            increase_percent=(increase / old * PERCENT).quantize(Decimal("0.1")),
            extra_yearly_cost=increase * 12,
        )


class PriceIncreases(BaseModel):
    """Wynik narzędzia price_increases: subskrypcje, które podrożały co najmniej o podany próg."""

    statement: str
    currency: str = "PLN"
    min_increase_percent: int
    subscriptions: list[PriceIncrease]