"""Execution boundary; arbitrary publication code has no backend in 0.1.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from oratlas_verify.core.contracts import ProtocolRef, VerificationFinding, VerificationInput


@dataclass(frozen=True, slots=True)
class BackendResult:
    findings: tuple[VerificationFinding, ...]
    backend_name: str


class ExecutionBackend(Protocol):
    name: str

    def execute(
        self, verification_input: VerificationInput, protocol: ProtocolRef
    ) -> BackendResult: ...


class ArbitraryExecutionUnsupported(RuntimeError):
    """Raised when callers attempt to run untrusted code in the initial release."""
