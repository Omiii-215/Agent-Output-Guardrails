"""Shared result vocabulary for rules and evaluations (LLD §2)."""

from __future__ import annotations

from enum import StrEnum


class RuleResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"  # missing required evidence is UNKNOWN, never PASS
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Outcome(StrEnum):
    """Overall decision. ``PASS`` never authorises an action by itself."""

    PASS = "PASS"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"
    INDETERMINATE = "INDETERMINATE"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
