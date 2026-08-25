"""Exact, immutable-at-runtime scientific protocol registry."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from oratlas_verify.core.contracts import ProtocolRef, VerificationFinding, VerificationInput
from oratlas_verify.core.errors import UnknownProtocolError

ProtocolHandler = Callable[[VerificationInput, ProtocolRef], tuple[VerificationFinding, ...]]


@dataclass(frozen=True, slots=True)
class ProtocolDefinition:
    ref: ProtocolRef
    description: str
    handler: ProtocolHandler | None
    availability: str = "implemented"


class ProtocolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ProtocolDefinition] = {}

    def register(self, definition: ProtocolDefinition) -> None:
        key = definition.ref.key
        if key in self._definitions:
            raise ValueError(f"protocol already registered: {key}")
        self._definitions[key] = definition

    def resolve(self, ref: ProtocolRef) -> ProtocolDefinition:
        try:
            return self._definitions[ref.key]
        except KeyError as exc:
            raise UnknownProtocolError(f"unknown protocol: {ref.key}") from exc

    def all(self) -> tuple[ProtocolDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))


def build_default_registry() -> ProtocolRegistry:
    # Local imports keep the domain registry independent of verifier dependencies.
    from oratlas_verify.verifiers.analysis.comparison import verify_analysis_result
    from oratlas_verify.verifiers.figures.structured import verify_structured_figure
    from oratlas_verify.verifiers.statistics.reported import verify_reported_statistic

    registry = ProtocolRegistry()
    implemented: Iterable[tuple[str, str, ProtocolHandler]] = (
        (
            "reported-statistic-consistency",
            "Recompute reported t, F, chi-square, or z p-values with SciPy.",
            verify_reported_statistic,
        ),
        (
            "figure-structured-comparison",
            "Compare explicit structured plot data, series, values, and labels.",
            verify_structured_figure,
        ),
        (
            "analysis-result-comparison",
            "Compare bounded explicit scalars, arrays, tables, and named metrics.",
            verify_analysis_result,
        ),
    )
    for name, description, handler in implemented:
        registry.register(
            ProtocolDefinition(ProtocolRef(name=name, version="0.1.0"), description, handler)
        )
    for name in (
        "methods-audit",
        "claim-evidence-audit",
        "statistical-design-audit",
        "reproducibility-audit",
    ):
        registry.register(
            ProtocolDefinition(
                ProtocolRef(name=name, version="0.1.0"),
                "Reserved protocol; no production auditor is enabled.",
                None,
                availability="reserved",
            )
        )
    return registry


def require_handler(definition: ProtocolDefinition) -> ProtocolHandler:
    if definition.handler is None:
        raise UnknownProtocolError(
            f"protocol is reserved but not implemented: {definition.ref.key}"
        )
    return definition.handler
