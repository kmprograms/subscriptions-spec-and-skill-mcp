import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from decimal import Decimal
from itertools import pairwise
from statistics import median

from subskrypcje.domain.models import Subscription, Transaction

MIN_PAYMENTS = 3
MIN_INTERVAL_DAYS = 25
MAX_INTERVAL_DAYS = 35
AMOUNT_TOLERANCE = Decimal("0.20")

_DIGITS = re.compile(r"\d")


def counterparty_key(counterparty: str) -> str:
    """R2: digits removed, whitespace collapsed and trimmed, upper case."""
    without_digits = _DIGITS.sub("", counterparty)
    return " ".join(without_digits.split()).upper()


def group_expenses(transactions: Iterable[Transaction]) -> dict[str, list[Transaction]]:
    """R1 and R3: only expenses, grouped by counterparty key."""
    groups: defaultdict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.amount < 0:
            groups[counterparty_key(transaction.counterparty)].append(transaction)
    return dict(groups)


def has_enough_payments(payments: Sequence[Transaction]) -> bool:
    """R4a."""
    return len(payments) >= MIN_PAYMENTS


def has_monthly_intervals(payments: Sequence[Transaction]) -> bool:
    """R4b: every gap between consecutive payments sorted by date."""
    dates = sorted(payment.booked_on for payment in payments)
    return all(
        MIN_INTERVAL_DAYS <= (later - earlier).days <= MAX_INTERVAL_DAYS
        for earlier, later in pairwise(dates)
    )


def has_stable_amounts(payments: Sequence[Transaction]) -> bool:
    """R4c: every absolute amount within the median +/- tolerance, bounds inclusive."""
    amounts = [abs(payment.amount) for payment in payments]
    center = median(amounts)
    lower = center * (1 - AMOUNT_TOLERANCE)
    upper = center * (1 + AMOUNT_TOLERANCE)
    return all(lower <= amount <= upper for amount in amounts)


def is_subscription(payments: Sequence[Transaction]) -> bool:
    """R4."""
    return (
        has_enough_payments(payments)
        and has_monthly_intervals(payments)
        and has_stable_amounts(payments)
    )


def detect_subscriptions(transactions: Iterable[Transaction]) -> tuple[Subscription, ...]:
    """R1-R7: subscriptions sorted by yearly cost descending, then by name."""
    subscriptions = [
        _to_subscription(name, payments)
        for name, payments in group_expenses(transactions).items()
        if is_subscription(payments)
    ]
    return tuple(sorted(subscriptions, key=lambda s: (-s.yearly_cost, s.name)))


def _to_subscription(name: str, payments: Sequence[Transaction]) -> Subscription:
    ordered = sorted(payments, key=lambda payment: payment.booked_on)
    return Subscription(
        name=name,
        earliest_amount=abs(ordered[0].amount),
        latest_amount=abs(ordered[-1].amount),
    )
