from datetime import date
from decimal import Decimal

from subskrypcje.domain.detection import detect_subscriptions, group_expenses
from subskrypcje.domain.models import Subscription, SubscriptionReport, Transaction


def payment(day: str, amount: str, counterparty: str = "NETFLIX.COM") -> Transaction:
    return Transaction(
        booked_on=date.fromisoformat(day),
        counterparty=counterparty,
        amount=Decimal(amount),
    )


def names(subscriptions: tuple[Subscription, ...]) -> list[str]:
    return [subscription.name for subscription in subscriptions]


# R1


def test_detect_income_paid_monthly_is_not_subscription() -> None:
    income = [payment(day, "8500.00", "ACME") for day in ("2026-04-10", "2026-05-10", "2026-06-10")]

    assert detect_subscriptions(income) == ()


def test_group_expenses_zero_and_positive_amounts_are_excluded() -> None:
    transactions = [
        payment("2026-04-01", "0.00", "ZERO"),
        payment("2026-04-02", "10.00", "INCOME"),
        payment("2026-04-03", "-10.00", "EXPENSE"),
    ]

    assert list(group_expenses(transactions)) == ["EXPENSE"]


# R2, R3


def test_detect_payments_with_same_key_form_one_subscription() -> None:
    transactions = [
        payment("2026-04-05", "-49.00", "Netflix.com 4829"),
        payment("2026-05-05", "-49.00", "NETFLIX.COM 5531"),
        payment("2026-06-05", "-49.00", "Netflix.com"),
    ]

    assert names(detect_subscriptions(transactions)) == ["NETFLIX.COM"]


def test_detect_payments_with_different_keys_are_not_merged() -> None:
    transactions = [
        payment("2026-04-05", "-49.00", "NETFLIX.COM"),
        payment("2026-05-05", "-49.00", "NETFLIX.COM"),
        payment("2026-06-05", "-49.00", "NETFLIX.PL"),
    ]

    assert detect_subscriptions(transactions) == ()


# R4a


def test_detect_two_monthly_payments_are_not_subscription() -> None:
    transactions = [payment("2026-04-05", "-49.00"), payment("2026-05-05", "-49.00")]

    assert detect_subscriptions(transactions) == ()


def test_detect_three_monthly_payments_are_subscription() -> None:
    transactions = [payment(day, "-49.00") for day in ("2026-04-05", "2026-05-05", "2026-06-05")]

    assert names(detect_subscriptions(transactions)) == ["NETFLIX.COM"]


# R4b


def test_detect_gaps_of_25_and_35_days_are_subscription() -> None:
    transactions = [payment(day, "-49.00") for day in ("2026-04-01", "2026-04-26", "2026-05-31")]

    assert names(detect_subscriptions(transactions)) == ["NETFLIX.COM"]


def test_detect_gap_of_24_days_is_not_subscription() -> None:
    transactions = [payment(day, "-49.00") for day in ("2026-04-01", "2026-04-25", "2026-05-25")]

    assert detect_subscriptions(transactions) == ()


def test_detect_gap_of_36_days_is_not_subscription() -> None:
    transactions = [payment(day, "-49.00") for day in ("2026-04-01", "2026-05-07", "2026-06-06")]

    assert detect_subscriptions(transactions) == ()


def test_detect_two_payments_on_same_day_are_not_subscription() -> None:
    transactions = [
        payment("2026-04-01", "-49.00"),
        payment("2026-05-01", "-49.00"),
        payment("2026-05-01", "-49.00"),
        payment("2026-06-01", "-49.00"),
    ]

    assert detect_subscriptions(transactions) == ()


def test_detect_rows_newest_first_are_sorted_by_date_before_gap_check() -> None:
    transactions = [payment(day, "-49.00") for day in ("2026-06-05", "2026-04-05", "2026-05-05")]

    assert names(detect_subscriptions(transactions)) == ["NETFLIX.COM"]


# R4c


def test_detect_amounts_on_20_percent_bounds_are_subscription() -> None:
    transactions = [
        payment("2026-04-01", "-80.00"),
        payment("2026-05-01", "-100.00"),
        payment("2026-06-01", "-120.00"),
    ]

    assert names(detect_subscriptions(transactions)) == ["NETFLIX.COM"]


def test_detect_amount_below_lower_bound_is_not_subscription() -> None:
    transactions = [
        payment("2026-04-01", "-79.99"),
        payment("2026-05-01", "-100.00"),
        payment("2026-06-01", "-120.00"),
    ]

    assert detect_subscriptions(transactions) == ()


def test_detect_amount_above_upper_bound_is_not_subscription() -> None:
    transactions = [
        payment("2026-04-01", "-100.00"),
        payment("2026-05-01", "-100.00"),
        payment("2026-06-01", "-120.01"),
    ]

    assert detect_subscriptions(transactions) == ()


def test_detect_even_count_uses_mean_of_middle_amounts_as_median() -> None:
    # median = (50 + 50) / 2 = 50, bounds 40..60
    within = [
        payment("2026-04-01", "-40.00"),
        payment("2026-05-01", "-50.00"),
        payment("2026-06-01", "-50.00"),
        payment("2026-07-01", "-60.00"),
    ]
    # median = (50 + 60) / 2 = 55, bounds 44..66, 40 is outside
    outside = [
        payment("2026-04-01", "-40.00"),
        payment("2026-05-01", "-50.00"),
        payment("2026-06-01", "-60.00"),
        payment("2026-07-01", "-60.00"),
    ]

    assert names(detect_subscriptions(within)) == ["NETFLIX.COM"]
    assert detect_subscriptions(outside) == ()


# R5, R6


def test_detect_monthly_cost_is_latest_payment_regardless_of_row_order() -> None:
    transactions = [
        payment("2026-05-12", "-23.99", "SPOTIFY"),
        payment("2026-07-12", "-26.99", "SPOTIFY"),
        payment("2026-04-12", "-23.99", "SPOTIFY"),
        payment("2026-06-12", "-26.99", "SPOTIFY"),
    ]

    (subscription,) = detect_subscriptions(transactions)

    assert subscription == Subscription(
        name="SPOTIFY", earliest_amount=Decimal("23.99"), latest_amount=Decimal("26.99")
    )
    assert subscription.monthly_cost == Decimal("26.99")
    assert subscription.yearly_cost == Decimal("323.88")


def test_subscription_different_earliest_and_latest_amount_has_price_change() -> None:
    subscription = Subscription("SPOTIFY", Decimal("23.99"), Decimal("26.99"))

    assert subscription.has_price_change is True


def test_detect_same_earliest_and_latest_amount_has_no_price_change() -> None:
    transactions = [
        payment("2026-04-01", "-10.00"),
        payment("2026-05-01", "-11.00"),
        payment("2026-06-01", "-10.00"),
    ]

    (subscription,) = detect_subscriptions(transactions)

    assert subscription.has_price_change is False


# R7


def test_detect_orders_by_yearly_cost_descending_then_name_ascending() -> None:
    days = ("2026-04-01", "2026-05-01", "2026-06-01")
    transactions = [
        payment(day, amount, name)
        for name, amount in (("CHEAP", "-4.99"), ("BETA", "-49.00"), ("ALFA", "-49.00"))
        for day in days
    ] + [payment(day, "-139.00", "GYM") for day in days]

    assert names(detect_subscriptions(transactions)) == ["GYM", "ALFA", "BETA", "CHEAP"]


# Totals


def test_report_totals_sum_monthly_and_yearly_costs() -> None:
    report = SubscriptionReport(
        (
            Subscription("A", Decimal("139.00"), Decimal("139.00")),
            Subscription("B", Decimal("23.99"), Decimal("26.99")),
        )
    )

    assert report.monthly_total == Decimal("165.99")
    assert report.yearly_total == Decimal("1991.88")


def test_report_without_subscriptions_has_zero_totals() -> None:
    report = SubscriptionReport(())

    assert (report.monthly_total, report.yearly_total) == (Decimal(0), Decimal(0))
