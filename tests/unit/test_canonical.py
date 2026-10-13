import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backend.domain.canonical import CanonicalizationError, canonical_json, digest


def test_key_order_and_whitespace_do_not_change_digest():
    assert digest({"b": 1, "a": [1, 2]}) == digest({"a": [1, 2], "b": 1})


def test_decimal_normalisation():
    assert digest({"x": Decimal("1.50")}) == digest({"x": Decimal("1.5")})
    assert digest({"x": Decimal("-0.00")}) == digest({"x": Decimal("0")})


def test_ints_are_strings_to_survive_javascript():
    assert canonical_json({"amount": 2**60}) == b'{"amount":"1152921504606846976"}'


def test_list_order_matters():
    assert digest([1, 2]) != digest([2, 1])


def test_timestamps_normalised_to_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    a = datetime(2026, 10, 9, 15, 30, tzinfo=ist)
    b = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    assert digest({"t": a}) == digest({"t": b})


@pytest.mark.parametrize("bad", [{"f": 0.1}, {"t": datetime(2026, 1, 1)}, {1: "x"}])
def test_rejects_ambiguous_values(bad):
    with pytest.raises(CanonicalizationError):
        canonical_json(bad)


def test_uuid_supported():
    u = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert canonical_json({"id": u}) == b'{"id":"12345678-1234-5678-1234-567812345678"}'


@given(st.dictionaries(st.text(max_size=8), st.integers() | st.text(max_size=8), max_size=8))
def test_digest_is_deterministic(payload):
    shuffled = dict(reversed(list(payload.items())))
    assert digest(payload) == digest(shuffled)
    assert digest(payload).startswith("sha256:")
