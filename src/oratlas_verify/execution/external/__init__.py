"""Accepts already-produced results only when accompanied by verified provenance."""

from __future__ import annotations

from dataclasses import dataclass

from oratlas_verify.core.contracts import ProtocolRef, VerificationFinding, VerificationInput
from oratlas_verify.execution.base import BackendResult


@dataclass(frozen=True, slots=True)
class ExternalAttestedResultBackend:
    supplied_findings: tuple[VerificationFinding, ...]
    name: str = "external-attested-result"

    def execute(
        self, verification_input: VerificationInput, protocol: ProtocolRef
    ) -> BackendResult:
        passport = verification_input.execution_passport
        if passport is None or not passport.verified_by_oratlas:
            raise ValueError("external results require an ORAtlas-verified ExecutionPassport")
        for finding in self.supplied_findings:
            if finding.protocol != protocol:
                raise ValueError("external finding protocol does not match the requested protocol")
        return BackendResult(self.supplied_findings, self.name)
