import pytest

from subskrypcje.domain.detection import counterparty_key


def test_counterparty_key_spec_example_removes_digits_and_uppercases() -> None:
    assert counterparty_key("Netflix.com 4829") == "NETFLIX.COM"


def test_counterparty_key_digits_inside_name_leave_single_space() -> None:
    assert counterparty_key("BIEDRONKA 3021 KRAKOW") == "BIEDRONKA KRAKOW"


@pytest.mark.parametrize(
    "counterparty",
    ["CITYFIT  SP. Z O.O.", "CITYFIT\tSP.  Z\N{NO-BREAK SPACE}O.O.", "  cityfit sp. z o.o.  "],
)
def test_counterparty_key_any_whitespace_collapses_and_trims(counterparty: str) -> None:
    assert counterparty_key(counterparty) == "CITYFIT SP. Z O.O."


def test_counterparty_key_letters_with_digits_keep_letters() -> None:
    assert counterparty_key("ZABKA Z1234 KRAKOW") == "ZABKA Z KRAKOW"
