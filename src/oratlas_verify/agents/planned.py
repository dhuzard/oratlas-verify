"""Named extension points for later specialist implementations."""

from __future__ import annotations

from dataclasses import dataclass

from oratlas_verify.core.contracts import (
    FindingStatus,
    ProtocolRef,
    VerificationFinding,
    VerificationInput,
)
from oratlas_verify.core.findings import make_finding


@dataclass(frozen=True, slots=True)
class DisabledPlannedAuditor:
    name: str
    perspective: str

    def audit(
        self, verification_input: VerificationInput, protocol: ProtocolRef
    ) -> tuple[VerificationFinding, ...]:
        return (
            make_finding(
                protocol=protocol,
                input_sha256=verification_input.computed_sha256,
                status=FindingStatus.UNVERIFIABLE,
                title=f"{self.name} is not enabled",
                rationale="No production AI auditor is configured in oratlas-verify 0.1.0.",
                details={"auditor": self.name, "perspective": self.perspective, "enabled": False},
                evidence_ids=verification_input.evidence_ids,
            ),
        )


class MethodsAuditor(DisabledPlannedAuditor):
    def __init__(self) -> None:
        super().__init__("MethodsAuditor", "methodological adequacy")


class StatisticsDesignAuditor(DisabledPlannedAuditor):
    def __init__(self) -> None:
        super().__init__("StatisticsDesignAuditor", "statistical design adequacy")


class ClaimEvidenceAuditor(DisabledPlannedAuditor):
    def __init__(self) -> None:
        super().__init__("ClaimEvidenceAuditor", "claim-to-evidence alignment")


class ReproducibilityAuditor(DisabledPlannedAuditor):
    def __init__(self) -> None:
        super().__init__("ReproducibilityAuditor", "reproducibility readiness")
