"""Bounded recursive comparison of explicit machine-readable analysis results."""

from __future__ import annotations

import math
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from oratlas_verify.core.contracts import (
    FindingStatus,
    JsonValue,
    ProtocolRef,
    ReproductionKind,
    VerificationFinding,
    VerificationInput,
)
from oratlas_verify.core.findings import make_finding


class AnalysisComparisonInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    expected: JsonValue
    reproduced: JsonValue
    comparison_kind: ReproductionKind
    absolute_tolerance: float = Field(ge=0)
    relative_tolerance: float = Field(ge=0)
    max_nodes: int = Field(default=10_000, ge=1, le=100_000)

    @field_validator("comparison_kind")
    @classmethod
    def meaningful_kind(cls, value: ReproductionKind) -> ReproductionKind:
        if value not in {
            ReproductionKind.REGENERATION,
            ReproductionKind.INDEPENDENT_REPRODUCTION,
            ReproductionKind.STRUCTURED_COMPARISON,
        }:
            raise ValueError("analysis comparison requires a scientific comparison kind")
        return value


def _validate_finite(value: JsonValue, counter: list[int], limit: int) -> None:
    counter[0] += 1
    if counter[0] > limit:
        raise ValueError(f"structured result exceeds max_nodes={limit}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("structured results cannot contain NaN or infinity")
    if isinstance(value, list):
        for item in value:
            _validate_finite(item, counter, limit)
    elif isinstance(value, dict):
        for item in value.values():
            _validate_finite(item, counter, limit)


def _compare(
    expected: JsonValue,
    actual: JsonValue,
    *,
    path: str,
    absolute: float,
    relative: float,
    differences: list[dict[str, JsonValue]],
) -> None:
    numeric_expected = isinstance(expected, int | float) and not isinstance(expected, bool)
    numeric_actual = isinstance(actual, int | float) and not isinstance(actual, bool)
    if numeric_expected and numeric_actual:
        expected_number = float(cast(int | float, expected))
        actual_number = float(cast(int | float, actual))
        if not math.isclose(expected_number, actual_number, abs_tol=absolute, rel_tol=relative):
            differences.append(
                {
                    "path": path,
                    "expected": expected,
                    "actual": actual,
                    "absolute_difference": abs(expected_number - actual_number),
                }
            )
        return
    if type(expected) is not type(actual):
        differences.append(
            {"path": path, "expected": expected, "actual": actual, "reason": "type-mismatch"}
        )
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            differences.append(
                {
                    "path": f"{path}.length",
                    "expected": len(expected),
                    "actual": len(actual),
                    "reason": "dimension-mismatch",
                }
            )
        for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
            _compare(
                left,
                right,
                path=f"{path}[{index}]",
                absolute=absolute,
                relative=relative,
                differences=differences,
            )
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        expected_keys, actual_keys = set(expected), set(actual)
        for key in sorted(expected_keys - actual_keys):
            differences.append(
                {
                    "path": f"{path}.{key}",
                    "expected": expected[key],
                    "actual": None,
                    "reason": "missing",
                }
            )
        for key in sorted(actual_keys - expected_keys):
            differences.append(
                {
                    "path": f"{path}.{key}",
                    "expected": None,
                    "actual": actual[key],
                    "reason": "unexpected",
                }
            )
        for key in sorted(expected_keys & actual_keys):
            _compare(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
                absolute=absolute,
                relative=relative,
                differences=differences,
            )
        return
    if expected != actual:
        differences.append({"path": path, "expected": expected, "actual": actual})


def verify_analysis_result(
    verification_input: VerificationInput, protocol: ProtocolRef
) -> tuple[VerificationFinding, ...]:
    try:
        comparison = AnalysisComparisonInput.model_validate(verification_input.payload)
        _validate_finite(comparison.expected, [0], comparison.max_nodes)
        _validate_finite(comparison.reproduced, [0], comparison.max_nodes)
    except (ValidationError, ValueError) as exc:
        return (
            make_finding(
                protocol=protocol,
                input_sha256=verification_input.computed_sha256,
                status=FindingStatus.FAILED,
                title="Analysis result input is malformed",
                rationale=f"The explicit result failed strict bounded validation: {exc}",
                details={"validation": "malformed-or-over-limit"},
                evidence_ids=verification_input.evidence_ids,
                reproduction_kind=ReproductionKind.STRUCTURED_COMPARISON,
            ),
        )

    differences: list[dict[str, JsonValue]] = []
    _compare(
        comparison.expected,
        comparison.reproduced,
        path="$",
        absolute=comparison.absolute_tolerance,
        relative=comparison.relative_tolerance,
        differences=differences,
    )
    status = FindingStatus.VERIFIED if not differences else FindingStatus.DISCREPANCY
    rationale = (
        "Expected and reproduced structured results agree within the explicit tolerance."
        if not differences
        else f"Analysis result comparison found {len(differences)} difference(s) beyond tolerance."
    )
    details: dict[str, Any] = {
        "comparison_kind": comparison.comparison_kind.value,
        "tolerance": {
            "absolute": comparison.absolute_tolerance,
            "relative": comparison.relative_tolerance,
        },
        "differences": differences,
        "bounded_max_nodes": comparison.max_nodes,
    }
    return (
        make_finding(
            protocol=protocol,
            input_sha256=verification_input.computed_sha256,
            status=status,
            title="Analysis result comparison",
            rationale=rationale,
            details=details,
            evidence_ids=verification_input.evidence_ids,
            reproduction_kind=comparison.comparison_kind,
        ),
    )
