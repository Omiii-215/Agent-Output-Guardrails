"""Deterministic rule registry and evaluator.

Rules are reviewed Python functions registered under ``code`` + ``version``.
They are pure: they read the frozen snapshot inputs and return a result, a
reason code and the values they compared. A crashing rule produces UNKNOWN
(an evaluation error), never PASS.

Aggregation (LLD §5): any BLOCK → BLOCK; otherwise any unresolved required
evidence → INDETERMINATE; otherwise any review finding → REVIEW; else PASS.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.domain.outcomes import Outcome, RuleResult, Severity
from backend.policies.schema import PolicyDocument, RuleConfig

log = logging.getLogger("finguard.policies")

ENGINE_VERSION = "rules-1.0.0"


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class RuleOutput:
    result: RuleResult
    reason_code: str
    message: str
    observed: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


RuleFn = Callable[[dict[str, Any], Any], RuleOutput]


@dataclass(frozen=True)
class RuleSpec:
    code: str
    version: int
    module: str
    title: str
    params: type[BaseModel]
    severity: Severity
    fn: RuleFn


_RULES: dict[tuple[str, int], RuleSpec] = {}


def rule(
    code: str,
    *,
    version: int,
    module: str,
    title: str,
    params: type[BaseModel] = NoParams,
    severity: Severity = Severity.WARNING,
) -> Callable[[RuleFn], RuleFn]:
    def register(fn: RuleFn) -> RuleFn:
        _RULES[(code, version)] = RuleSpec(code, version, module, title, params, severity, fn)
        return fn

    return register


def catalog(module: str | None = None) -> list[RuleSpec]:
    specs = sorted(_RULES.values(), key=lambda s: (s.module, s.code, s.version))
    return [s for s in specs if module is None or s.module in (module, "*")]


def get_rule(code: str, version: int) -> RuleSpec | None:
    return _RULES.get((code, version))


# -- validation -------------------------------------------------------------


def validate_document(doc: PolicyDocument) -> list[str]:
    """Return human-readable errors; empty when the policy can be validated."""
    errors: list[str] = []
    for cfg in doc.rules:
        spec = get_rule(cfg.code, cfg.version)
        if spec is None:
            errors.append(f"Unknown rule {cfg.code} v{cfg.version}")
            continue
        if spec.module not in (doc.module, "*"):
            errors.append(f"Rule {cfg.code} does not apply to module {doc.module}")
        try:
            spec.params.model_validate(cfg.parameters)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                errors.append(f"{cfg.code}.{loc}: {err['msg']}")
    return errors


# -- evaluation ---------------------------------------------------------------


@dataclass(frozen=True)
class FindingResult:
    rule_code: str
    rule_version: int
    title: str
    result: RuleResult
    effect: str | None  # BLOCK | REVIEW | INDETERMINATE | None
    severity: Severity
    reason_code: str
    message: str
    observed: dict[str, Any]
    expected: dict[str, Any]
    evidence_refs: tuple[str, ...]

    @property
    def requires_review(self) -> bool:
        return self.effect is not None


@dataclass(frozen=True)
class EvaluationResult:
    outcome: Outcome
    findings: tuple[FindingResult, ...]
    coverage: dict[str, int]


def _effect(cfg: RuleConfig, result: RuleResult) -> str | None:
    if result == RuleResult.FAIL:
        return cfg.on_fail
    if result == RuleResult.UNKNOWN:
        return cfg.on_unknown
    return None


def _run_rule(cfg: RuleConfig, inputs: dict[str, Any]) -> tuple[RuleSpec | None, RuleOutput]:
    spec = get_rule(cfg.code, cfg.version)
    if spec is None:
        return None, RuleOutput(
            RuleResult.UNKNOWN, "RULE_UNAVAILABLE", f"Rule {cfg.code} v{cfg.version} is missing"
        )
    try:
        params = spec.params.model_validate(cfg.parameters)
        output = spec.fn(inputs, params)
        if not isinstance(output, RuleOutput):
            raise TypeError("rule returned an invalid result")
        return spec, output
    except Exception as exc:  # an evaluation error is never a pass
        log.warning("rule %s failed: %s", cfg.code, type(exc).__name__)
        return spec, RuleOutput(
            RuleResult.UNKNOWN,
            "RULE_ERROR",
            f"The rule could not be evaluated ({type(exc).__name__}).",
        )


def aggregate(effects: list[str | None]) -> Outcome:
    if "BLOCK" in effects:
        return Outcome.BLOCK
    if "INDETERMINATE" in effects:
        return Outcome.INDETERMINATE
    if "REVIEW" in effects:
        return Outcome.REVIEW
    return Outcome.PASS


def evaluate(doc: PolicyDocument, inputs: dict[str, Any]) -> EvaluationResult:
    findings: list[FindingResult] = []
    for cfg in doc.rules:
        spec, out = _run_rule(cfg, inputs)
        findings.append(
            FindingResult(
                rule_code=cfg.code,
                rule_version=cfg.version,
                title=spec.title if spec else cfg.code,
                result=out.result,
                effect=_effect(cfg, out.result),
                severity=(spec.severity if spec else Severity.CRITICAL),
                reason_code=out.reason_code,
                message=out.message,
                observed=out.observed,
                expected=out.expected,
                evidence_refs=tuple(out.evidence_refs),
            )
        )
    coverage = {
        "rules_total": len(findings),
        **{r.value.lower(): sum(f.result == r for f in findings) for r in RuleResult},
    }
    return EvaluationResult(aggregate([f.effect for f in findings]), tuple(findings), coverage)


def run_scenarios(doc: PolicyDocument) -> list[str]:
    """Run regression scenarios; return failures."""
    failures = []
    for scenario in doc.scenarios:
        outcome = evaluate(doc, scenario.inputs).outcome
        if outcome != scenario.expected_outcome:
            failures.append(f"{scenario.name}: expected {scenario.expected_outcome}, got {outcome}")
    return failures
