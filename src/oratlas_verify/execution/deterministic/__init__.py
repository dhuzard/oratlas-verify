"""Only built-in registered Python procedures execute in this process."""

from __future__ import annotations

from dataclasses import dataclass

from oratlas_verify.core.contracts import ProtocolRef, VerificationInput
from oratlas_verify.core.registry import ProtocolRegistry, require_handler
from oratlas_verify.execution.base import BackendResult


@dataclass(frozen=True, slots=True)
class DeterministicBackend:
    registry: ProtocolRegistry
    name: str = "deterministic-built-in"

    def execute(
        self, verification_input: VerificationInput, protocol: ProtocolRef
    ) -> BackendResult:
        definition = self.registry.resolve(protocol)
        handler = require_handler(definition)
        return BackendResult(handler(verification_input, protocol), self.name)
