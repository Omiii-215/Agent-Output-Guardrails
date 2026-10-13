"""Exact money handling.

Payable amounts are signed integers in minor units plus an ISO 4217 currency
code (ADR 0002). Quantities, unit prices and tax rates are ``Decimal`` and are
quantised exactly once into minor units with an explicit rounding mode.
Binary floating point is rejected everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

# Exponents for currencies the platform accepts. Extend deliberately; an unknown
# currency is an input error, not a default of 2.
CURRENCY_EXPONENTS: dict[str, int] = {
    "INR": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "SGD": 2,
    "AED": 2,
    "JPY": 0,
    "KWD": 3,
    "BHD": 3,
}

RoundingName = Literal["HALF_UP", "HALF_EVEN"]
_ROUNDING = {"HALF_UP": ROUND_HALF_UP, "HALF_EVEN": ROUND_HALF_EVEN}

# Postgres BIGINT bounds.
_MAX_MINOR = 2**63 - 1


class MoneyError(ValueError):
    """Invalid currency, amount or arithmetic between currencies."""


def exponent_for(currency: str) -> int:
    try:
        return CURRENCY_EXPONENTS[currency]
    except KeyError:
        raise MoneyError(f"Unsupported currency '{currency}'") from None


def parse_minor(value: object) -> int:
    """Parse a minor-unit amount from an int or an integer string.

    Floats and booleans are rejected; API payloads carry amounts as strings.
    """
    if isinstance(value, bool | float):
        raise MoneyError("Amounts must be integer minor units, not floats or booleans")
    if isinstance(value, int):
        minor = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or not text.lstrip("-").isdigit():
            raise MoneyError(f"'{value}' is not an integer minor-unit amount")
        minor = int(text)
    else:
        raise MoneyError(f"Unsupported amount type {type(value).__name__}")
    if abs(minor) > _MAX_MINOR:
        raise MoneyError("Amount exceeds the supported range")
    return minor


def to_decimal(value: object) -> Decimal:
    """Convert an exact input (str, int, Decimal) to Decimal. Floats are rejected."""
    if isinstance(value, bool | float):
        raise MoneyError("Use strings or Decimal for quantities and rates, never floats")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int | str):
        try:
            result = Decimal(str(value).strip())
        except InvalidOperation:
            raise MoneyError(f"'{value}' is not a decimal number") from None
    else:
        raise MoneyError(f"Unsupported decimal type {type(value).__name__}")
    if not result.is_finite():
        raise MoneyError("Decimal values must be finite")
    return result


@dataclass(frozen=True, slots=True)
class Money:
    minor: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.minor, bool) or not isinstance(self.minor, int):
            raise MoneyError("Money.minor must be an int")
        exponent_for(self.currency)
        if abs(self.minor) > _MAX_MINOR:
            raise MoneyError("Amount exceeds the supported range")

    # -- construction -------------------------------------------------------

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(0, currency)

    @classmethod
    def of(cls, minor: object, currency: str) -> Money:
        return cls(parse_minor(minor), currency)

    @classmethod
    def from_major(cls, amount: object, currency: str, rounding: RoundingName = "HALF_UP") -> Money:
        """Quantise a major-unit decimal (e.g. ``"10000.50"`` rupees) once."""
        exp = exponent_for(currency)
        scaled = to_decimal(amount).scaleb(exp)
        return cls(int(scaled.quantize(Decimal(1), rounding=_ROUNDING[rounding])), currency)

    # -- arithmetic ---------------------------------------------------------

    def _same(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise MoneyError("Can only combine Money with Money")
        if other.currency != self.currency:
            raise MoneyError(
                f"Cannot combine {self.currency} with {other.currency}; convert explicitly"
            )

    def __add__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.minor + other.minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.minor - other.minor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.minor, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._same(other)
        return self.minor < other.minor

    def __le__(self, other: Money) -> bool:
        self._same(other)
        return self.minor <= other.minor

    def abs_diff(self, other: Money) -> int:
        self._same(other)
        return abs(self.minor - other.minor)

    # -- presentation -------------------------------------------------------

    def to_major(self) -> Decimal:
        return Decimal(self.minor).scaleb(-exponent_for(self.currency))

    def format(self) -> str:
        exp = exponent_for(self.currency)
        return f"{self.currency} {self.to_major():,.{exp}f}"

    def to_api(self) -> dict[str, str]:
        return {"amount_minor": str(self.minor), "currency": self.currency}


def money_sum(values: list[Money], currency: str) -> Money:
    total = Money.zero(currency)
    for value in values:
        total = total + value
    return total


def line_amount(
    quantity: object,
    unit_price_major: object,
    currency: str,
    *,
    tax_rate: object | None = None,
    rounding: RoundingName = "HALF_UP",
) -> Money:
    """Compute a line amount exactly and quantise once.

    ``tax_rate`` is a fraction (``"0.18"`` for 18%).
    """
    gross = to_decimal(quantity) * to_decimal(unit_price_major)
    if tax_rate is not None:
        gross = gross * (Decimal(1) + to_decimal(tax_rate))
    return Money.from_major(gross, currency, rounding)
