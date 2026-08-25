"""Critical reviewer extension point."""

from oratlas_verify.agents.planned import DisabledPlannedAuditor


class CriticalReviewer(DisabledPlannedAuditor):
    def __init__(self) -> None:
        super().__init__(
            "CriticalReviewer", "actively seek methodological and evidential weaknesses"
        )


__all__ = ["CriticalReviewer"]
