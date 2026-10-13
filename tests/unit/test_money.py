from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backend.domain.money import (
    Money,
    MoneyError,
    line_amount,
    money_sum,
    parse_minor,
)


def test_inr_ten_thousand_is_one_million_minor_units():
    assert Money.from_major("10000", "INR").minor == 1_000_000


@pytest.mark.parametrize(
    ("currency", "major", "minor"),
    [("INR", "12.345", 1235), ("JPY", "1234.5", 1235), ("KWD", "1.2345", 1235)],
)
def test_exponents_per_currency(currency, major, minor):
    assert Money.from_major(major, currency).minor == minor


def test_half_even_rounding_is_explicit():
    assert Money.from_major("0.125", "INR", "HALF_EVEN").minor == 12
    assert Money.from_major("0.125", "INR", "HALF_UP").minor == 13


@pytest.mark.parametrize("bad", [1.5, True, "1.5", "", "abc", None])
def test_parse_minor_rejects_non_integers(bad):
    with pytest.raises(MoneyError):
        parse_minor(bad)


def test_floats_rejected_for_major_amounts():
    with pytest.raises(MoneyError):
        Money.from_major(0.1, "INR")


def test_cross_currency_arithmetic_is_rejected():
    with pytest.raises(MoneyError):
        Money(100, "INR") + Money(100, "USD")


def test_unknown_currency_rejected():
    with pytest.raises(MoneyError):
        Money(1, "XXX")


def test_line_amount_with_tax_quantises_once():
    # 3 × 33.33 × 1.18 = 117.9882 → 117.99
    assert line_amount("3", "33.33", "INR", tax_rate="0.18").minor == 11799


def test_fractional_quantities():
    assert line_amount("2.5", "19.99", "INR").minor == 4998  # 49.975 → 49.98


def test_large_amounts_stay_exact():
    big = Money.of("900000000000000000", "INR")
    assert (big + Money(1, "INR")).minor == 900000000000000001
    assert big.to_api() == {"amount_minor": "900000000000000000", "currency": "INR"}


def test_format():
    assert Money(123456789, "INR").format() == "INR 1,234,567.89"
    assert Money(1500, "JPY").format() == "JPY 1,500"


@given(st.lists(st.integers(min_value=-(10**12), max_value=10**12), max_size=50))
def test_sum_is_exact_integer_addition(values):
    total = money_sum([Money(v, "INR") for v in values], "INR")
    assert total.minor == sum(values)


@given(
    st.decimals(
        min_value=Decimal("-1000000"),
        max_value=Decimal("1000000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_two_place_majors_round_trip_without_drift(value):
    money = Money.from_major(value, "INR")
    assert money.to_major() == value
