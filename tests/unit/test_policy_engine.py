import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.domain.outcomes import Outcome, RuleResult
from backend.policies import engine
from backend.policies.engine import RuleOutput, rule
from backend.policies.schema import ApprovalConfig, PolicyDocument


class ToleranceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tolerance_minor: int = Field(ge=0)


@rule("test.amount_within", version=1, module="*", title="Amount within", params=ToleranceParams)
def _amount_within(inputs, params):
    diff = abs(int(inputs["a"]) - int(inputs["b"]))
    if diff <= params.tolerance_minor:
        return RuleOutput(RuleResult.PASS, "OK", "ok")
    return RuleOutput(RuleResult.FAIL, "DIFF", "too far", observed={"diff": diff})


@rule("test.needs_x", version=1, module="*", title="Needs x")
def _needs_x(inputs, params):
    if "x" not in inputs:
        return RuleOutput(RuleResult.UNKNOWN, "X_MISSING", "x missing")
    return RuleOutput(RuleResult.PASS, "X_OK", "ok")


@rule("test.crashes", version=1, module="*", title="Crashes")
def _crashes(inputs, params):
    raise ZeroDivisionError


def doc(rules, **extra):
    return PolicyDocument.model_validate(
        {"policy_code": "test-policy", "module": "invoices", "rules": rules, **extra}
    )


AMOUNT = {"code": "test.amount_within", "version": 1, "parameters": {"tolerance_minor": 0}}


def test_aggregation_precedence():
    assert engine.aggregate([None, "REVIEW"]) == Outcome.REVIEW
    assert engine.aggregate(["REVIEW", "INDETERMINATE"]) == Outcome.INDETERMINATE
    assert engine.aggregate(["INDETERMINATE", "BLOCK", "REVIEW"]) == Outcome.BLOCK
    assert engine.aggregate([None, None]) == Outcome.PASS


def test_fail_and_unknown_effects():
    policy = doc(
        [
            {**AMOUNT, "on_fail": "REVIEW"},
            {"code": "test.needs_x", "version": 1, "on_fail": "BLOCK"},
        ]
    )
    result = engine.evaluate(policy, {"a": "100", "b": "101"})
    assert result.outcome == Outcome.INDETERMINATE  # missing evidence beats review
    assert [f.effect for f in result.findings] == ["REVIEW", "INDETERMINATE"]
    assert result.coverage["fail"] == 1 and result.coverage["unknown"] == 1


def test_a_crashing_rule_is_never_a_pass():
    result = engine.evaluate(doc([{"code": "test.crashes", "version": 1, "on_fail": "REVIEW"}]), {})
    finding = result.findings[0]
    assert finding.result == RuleResult.UNKNOWN and finding.reason_code == "RULE_ERROR"
    assert result.outcome == Outcome.INDETERMINATE


def test_validation_rejects_unknown_rules_and_bad_parameters():
    policy = doc(
        [
            {"code": "test.missing", "version": 9, "on_fail": "BLOCK"},
            {**AMOUNT, "parameters": {"tolerance_minor": -5}, "on_fail": "BLOCK"},
        ]
    )
    errors = engine.validate_document(policy)
    assert any("Unknown rule test.missing" in e for e in errors)
    assert any("tolerance_minor" in e for e in errors)


def test_schema_rejects_unknown_fields_and_duplicate_rules():
    with pytest.raises(ValidationError):
        doc([{**AMOUNT, "on_fail": "BLOCK", "python": "os.system('x')"}])
    with pytest.raises(ValidationError):
        doc([{**AMOUNT, "on_fail": "BLOCK"}, {**AMOUNT, "on_fail": "REVIEW"}])
    with pytest.raises(ValidationError):
        doc([{**AMOUNT, "on_fail": "BLOCK"}], spend_limits=[{"currency": "XXX", "limit_minor": 1}])


def test_regression_scenarios():
    policy = doc(
        [{**AMOUNT, "on_fail": "BLOCK"}],
        scenarios=[
            {"name": "equal", "inputs": {"a": "5", "b": "5"}, "expected_outcome": "PASS"},
            {"name": "wrong", "inputs": {"a": "5", "b": "6"}, "expected_outcome": "PASS"},
        ],
    )
    assert engine.run_scenarios(policy) == ["wrong: expected PASS, got BLOCK"]


def test_approval_tiers():
    cfg = ApprovalConfig(count=1, tiers=[{"above_minor": 100_000_00, "count": 2}])
    assert cfg.approvals_required(50_000_00) == 1
    assert cfg.approvals_required(100_000_01) == 2
