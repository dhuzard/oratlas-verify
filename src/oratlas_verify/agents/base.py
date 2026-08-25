"""Agentic scientific audit interfaces and independent-first runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from oratlas_verify.core.contracts import ProtocolRef, VerificationFinding, VerificationInput


class ScientificAuditor(Protocol):
    name: str

    def audit(
        self, verification_input: VerificationInput, protocol: ProtocolRef
    ) -> tuple[VerificationFinding, ...]: ...


@dataclass(frozen=True, slots=True)
class AuditorOutput:
    auditor_name: str
    first_pass_findings: tuple[VerificationFinding, ...]


def run_independent_first_pass(
    auditors: tuple[ScientificAuditor, ...],
    verification_input: VerificationInput,
    protocol: ProtocolRef,
) -> tuple[AuditorOutput, ...]:
    """Run each auditor against the same input without sharing any peer findings."""
    return tuple(
        AuditorOutput(auditor.name, auditor.audit(verification_input, protocol))
        for auditor in auditors
    )
