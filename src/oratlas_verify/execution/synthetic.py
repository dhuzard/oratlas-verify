"""Controlled test-only backend."""

from __future__ import annotations

from dataclasses import dataclass

from oratlas_verify.core.contracts import ProtocolRef, VerificationFinding, VerificationInput
from oratlas_verify.execution.base import BackendResult


@dataclass(frozen=True, slots=True)
class SyntheticTestBackend:
    findings: tuple[VerificationFinding, ...]
    enabled_for_tests: bool = False
    name: str = "controlled-synthetic-test"

    def execute(
        self, verification_input: VerificationInput, protocol: ProtocolRef
    ) -> BackendResult:
        if not self.enabled_for_tests:
            raise RuntimeError("synthetic execution backend is disabled outside explicit tests")
        return BackendResult(self.findings, self.name)
