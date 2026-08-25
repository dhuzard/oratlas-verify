"""Strict input/result models for reported statistics."""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TestType(StrEnum):
    T = "t"
    F = "F"
    CHI_SQUARE = "chi-square"
    Z = "z"


class Sidedness(StrEnum):
    TWO_SIDED = "two-sided"
    GREATER = "greater"
    LESS = "less"


class StatisticAssertion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    test_type: TestType | None = None
    statistic: float | None = None
    degrees_of_freedom: tuple[float, ...] | None = None
    reported_p: float | None = None
    sidedness: Sidedness | None = None
    absolute_tolerance: float = Field(default=5e-5, ge=0)
    relative_tolerance: float = Field(default=1e-4, ge=0)
    source_span: str | None = None
    evidence_id: str | None = None

    @field_validator("statistic", "reported_p", "absolute_tolerance", "relative_tolerance")
    @classmethod
    def finite_scalar(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("numeric inputs must be finite")
        return value

    @field_validator("degrees_of_freedom")
    @classmethod
    def finite_df(cls, value: tuple[float, ...] | None) -> tuple[float, ...] | None:
        if value is not None and any(not math.isfinite(item) for item in value):
            raise ValueError("degrees of freedom must be finite")
        return value
