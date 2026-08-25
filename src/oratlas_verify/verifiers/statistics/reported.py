"""Deterministic offline p-value recomputation using SciPy."""

from __future__ import annotations

import math
from typing import Any

import scipy
from pydantic import ValidationError
from scipy import stats

from oratlas_verify.core.contracts import (
    FindingStatus,
    ProtocolRef,
    VerificationFinding,
    VerificationInput,
)
from oratlas_verify.core.findings import make_finding
from oratlas_verify.verifiers.statistics.models import Sidedness, StatisticAssertion, TestType


def _incomplete(assertion: StatisticAssertion) -> str | None:
    missing: list[str] = []
    for field in ("test_type", "statistic", "degrees_of_freedom", "reported_p", "sidedness"):
        if getattr(assertion, field) is None:
            missing.append(field)
    if missing:
        return f"Missing required fields: {', '.join(missing)}."
    return None


def _validate_semantics(assertion: StatisticAssertion) -> str | None:
    assert assertion.test_type is not None
    assert assertion.statistic is not None
    assert assertion.degrees_of_freedom is not None
    assert assertion.reported_p is not None
    assert assertion.sidedness is not None
    dfs = assertion.degrees_of_freedom
    if not 0 <= assertion.reported_p <= 1:
        return "reported_p must be between 0 and 1 inclusive"
    expected_df = (
        2 if assertion.test_type is TestType.F else (0 if assertion.test_type is TestType.Z else 1)
    )
    if len(dfs) != expected_df:
        return (
            f"{assertion.test_type.value} requires exactly {expected_df} "
            "degrees-of-freedom value(s)"
        )
    if any(df <= 0 for df in dfs):
        return "degrees of freedom must be strictly positive"
    if assertion.test_type in (TestType.F, TestType.CHI_SQUARE) and assertion.statistic < 0:
        return f"{assertion.test_type.value} statistics cannot be negative"
    if (
        assertion.test_type in (TestType.F, TestType.CHI_SQUARE)
        and assertion.sidedness is not Sidedness.GREATER
    ):
        return f"{assertion.test_type.value} 0.1.0 requires sidedness='greater'"
    return None


def _calculate(assertion: StatisticAssertion) -> tuple[float, str]:
    test_type = assertion.test_type
    statistic = assertion.statistic
    dfs = assertion.degrees_of_freedom
    sidedness = assertion.sidedness
    assert test_type is not None and statistic is not None and dfs is not None
    assert sidedness is not None

    if test_type is TestType.T:
        distribution = stats.t(df=dfs[0])
        procedure = f"scipy.stats.t(df={dfs[0]:g})"
    elif test_type is TestType.Z:
        distribution = stats.norm()
        procedure = "scipy.stats.norm()"
    elif test_type is TestType.F:
        value = float(stats.f.sf(statistic, dfs[0], dfs[1]))
        return value, f"scipy.stats.f.sf(statistic, dfn={dfs[0]:g}, dfd={dfs[1]:g})"
    else:
        value = float(stats.chi2.sf(statistic, dfs[0]))
        return value, f"scipy.stats.chi2.sf(statistic, df={dfs[0]:g})"

    if sidedness is Sidedness.TWO_SIDED:
        return float(2 * distribution.sf(abs(statistic))), f"2 * {procedure}.sf(abs(statistic))"
    if sidedness is Sidedness.GREATER:
        return float(distribution.sf(statistic)), f"{procedure}.sf(statistic)"
    return float(distribution.cdf(statistic)), f"{procedure}.cdf(statistic)"


def _invalid_finding(
    verification_input: VerificationInput,
    protocol: ProtocolRef,
    rationale: str,
    *,
    missing: bool,
) -> tuple[VerificationFinding, ...]:
    status = FindingStatus.UNVERIFIABLE if missing else FindingStatus.FAILED
    return (
        make_finding(
            protocol=protocol,
            input_sha256=verification_input.computed_sha256,
            status=status,
            title="Reported statistic could not be verified",
            rationale=rationale,
            details={"validation": "missing-or-ambiguous" if missing else "malformed"},
            evidence_ids=verification_input.evidence_ids,
        ),
    )


def verify_reported_statistic(
    verification_input: VerificationInput, protocol: ProtocolRef
) -> tuple[VerificationFinding, ...]:
    """Validate, independently calculate, and compare a reported p-value."""
    try:
        assertion = StatisticAssertion.model_validate(verification_input.payload)
    except ValidationError as exc:
        return _invalid_finding(
            verification_input,
            protocol,
            f"Malformed numeric or structured statistic input: {exc.errors(include_url=False)}",
            missing=False,
        )
    incomplete = _incomplete(assertion)
    if incomplete:
        return _invalid_finding(verification_input, protocol, incomplete, missing=True)
    invalid = _validate_semantics(assertion)
    if invalid:
        return _invalid_finding(verification_input, protocol, invalid, missing=False)

    recomputed, procedure = _calculate(assertion)
    if not math.isfinite(recomputed):
        return _invalid_finding(
            verification_input,
            protocol,
            "SciPy returned a non-finite probability.",
            missing=False,
        )
    assert assertion.reported_p is not None
    difference = abs(recomputed - assertion.reported_p)
    tolerance_limit = max(
        assertion.absolute_tolerance,
        assertion.relative_tolerance * max(abs(recomputed), abs(assertion.reported_p)),
    )
    accepted = difference <= tolerance_limit or math.isclose(
        difference,
        tolerance_limit,
        rel_tol=1e-12,
        abs_tol=1e-15,
    )
    status = FindingStatus.VERIFIED if accepted else FindingStatus.DISCREPANCY
    rationale = (
        "The reported p-value agrees with the independently recomputed value within the "
        "protocol/request tolerance."
        if accepted
        else "The reported p-value differs from the independently recomputed value beyond the "
        "protocol/request tolerance."
    )
    normalized: dict[str, Any] = assertion.model_dump(mode="json", exclude_none=True)
    details: dict[str, Any] = {
        "normalized_input": normalized,
        "formula_or_procedure": procedure,
        "library_versions": {"scipy": scipy.__version__},
        "recomputed_p": recomputed,
        "reported_p": assertion.reported_p,
        "absolute_difference": difference,
        "tolerance": {
            "absolute": assertion.absolute_tolerance,
            "relative": assertion.relative_tolerance,
        },
        "comparison": "absolute_difference <= max(abs_tol, rel_tol * max(abs(values)))",
        "effective_tolerance": tolerance_limit,
    }
    return (
        make_finding(
            protocol=protocol,
            input_sha256=verification_input.computed_sha256,
            status=status,
            title="Reported statistic consistency",
            rationale=rationale,
            details=details,
            evidence_ids=verification_input.evidence_ids,
        ),
    )
