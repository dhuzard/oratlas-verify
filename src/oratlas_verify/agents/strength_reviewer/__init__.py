"""Strength reviewer extension point."""

from oratlas_verify.agents.planned import DisabledPlannedAuditor


class StrengthReviewer(DisabledPlannedAuditor):
    def __init__(self) -> None:
        super().__init__(
            "StrengthReviewer",
            "identify unusually strong support, transparency, and reproducibility",
        )


__all__ = ["StrengthReviewer"]
