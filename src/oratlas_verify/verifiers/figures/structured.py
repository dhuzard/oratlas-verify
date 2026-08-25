"""Scientific comparison of explicit structured figure data."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from oratlas_verify.core.contracts import (
    FindingStatus,
    ProtocolRef,
    ReproductionKind,
    VerificationFinding,
    VerificationInput,
)
from oratlas_verify.core.findings import make_finding


class PlotSeries(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    x: tuple[float, ...]
    y: tuple[float, ...]

    @field_validator("x", "y")
    @classmethod
    def finite_values(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if any(not math.isfinite(item) for item in value):
            raise ValueError("plot values must be finite")
        return value


class StructuredPlot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    series: tuple[PlotSeries, ...]
    x_label: str | None = None
    y_label: str | None = None
    title: str | None = None


class FigureComparisonInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    original: StructuredPlot
    regenerated: StructuredPlot
    comparison_kind: ReproductionKind = ReproductionKind.STRUCTURED_COMPARISON
    absolute_tolerance: float = Field(default=0.0, ge=0)
    relative_tolerance: float = Field(default=0.0, ge=0)
    compare_labels: bool = True

    @field_validator("comparison_kind")
    @classmethod
    def supported_kind(cls, value: ReproductionKind) -> ReproductionKind:
        allowed = {
            ReproductionKind.REGENERATION,
            ReproductionKind.INDEPENDENT_REPRODUCTION,
            ReproductionKind.STRUCTURED_COMPARISON,
        }
        if value not in allowed:
            raise ValueError("visual-consistency is not a structured scientific comparison")
        return value


def _compare_series(
    expected: PlotSeries, actual: PlotSeries, *, absolute: float, relative: float, index: int
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    if expected.name != actual.name:
        differences.append(
            {"path": f"series[{index}].name", "expected": expected.name, "actual": actual.name}
        )
    for axis in ("x", "y"):
        left = getattr(expected, axis)
        right = getattr(actual, axis)
        if len(left) != len(right):
            differences.append(
                {
                    "path": f"series[{index}].{axis}.length",
                    "expected": len(left),
                    "actual": len(right),
                }
            )
            continue
        for value_index, (expected_value, actual_value) in enumerate(zip(left, right, strict=True)):
            if not math.isclose(expected_value, actual_value, abs_tol=absolute, rel_tol=relative):
                differences.append(
                    {
                        "path": f"series[{index}].{axis}[{value_index}]",
                        "expected": expected_value,
                        "actual": actual_value,
                        "absolute_difference": abs(expected_value - actual_value),
                    }
                )
    return differences


def verify_structured_figure(
    verification_input: VerificationInput, protocol: ProtocolRef
) -> tuple[VerificationFinding, ...]:
    try:
        comparison = FigureComparisonInput.model_validate(verification_input.payload)
    except ValidationError as exc:
        return (
            make_finding(
                protocol=protocol,
                input_sha256=verification_input.computed_sha256,
                status=FindingStatus.FAILED,
                title="Structured figure input is malformed",
                rationale=(
                    f"The structured data failed strict validation: {exc.errors(include_url=False)}"
                ),
                details={"validation": "malformed"},
                evidence_ids=verification_input.evidence_ids,
                reproduction_kind=ReproductionKind.STRUCTURED_COMPARISON,
            ),
        )

    original = comparison.original
    regenerated = comparison.regenerated
    differences: list[dict[str, Any]] = []
    if len(original.series) != len(regenerated.series):
        differences.append(
            {
                "path": "series.length",
                "expected": len(original.series),
                "actual": len(regenerated.series),
            }
        )
    for index, (expected, actual) in enumerate(
        zip(original.series, regenerated.series, strict=False)
    ):
        differences.extend(
            _compare_series(
                expected,
                actual,
                absolute=comparison.absolute_tolerance,
                relative=comparison.relative_tolerance,
                index=index,
            )
        )
    if comparison.compare_labels:
        for label in ("x_label", "y_label", "title"):
            expected_label = getattr(original, label)
            actual_label = getattr(regenerated, label)
            if expected_label != actual_label:
                differences.append(
                    {"path": label, "expected": expected_label, "actual": actual_label}
                )

    status = FindingStatus.VERIFIED if not differences else FindingStatus.DISCREPANCY
    rationale = (
        "Structured figure data, dimensions, series, and configured labels agree within tolerance."
        if not differences
        else f"Structured figure comparison found {len(differences)} difference(s)."
    )
    details: dict[str, Any] = {
        "comparison_kind": comparison.comparison_kind.value,
        "series_compared": min(len(original.series), len(regenerated.series)),
        "tolerance": {
            "absolute": comparison.absolute_tolerance,
            "relative": comparison.relative_tolerance,
        },
        "compare_labels": comparison.compare_labels,
        "differences": differences,
        "visual_similarity_used": False,
    }
    return (
        make_finding(
            protocol=protocol,
            input_sha256=verification_input.computed_sha256,
            status=status,
            title="Structured figure comparison",
            rationale=rationale,
            details=details,
            evidence_ids=verification_input.evidence_ids,
            reproduction_kind=comparison.comparison_kind,
        ),
    )
