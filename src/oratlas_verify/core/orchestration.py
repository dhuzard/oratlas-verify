"""Run orchestration independent of ORAtlas endpoint details."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from oratlas_verify.core.artifacts import LocalArtifactStore
from oratlas_verify.core.contracts import (
    ProtocolRef,
    VerificationExecutionMetadata,
    VerificationFinding,
    VerificationInput,
    VerificationRequest,
    VerificationResponse,
)
from oratlas_verify.core.provenance import create_json_artifact, runtime_identity, tool_versions
from oratlas_verify.core.registry import ProtocolRegistry
from oratlas_verify.execution.deterministic import DeterministicBackend

logger = logging.getLogger(__name__)


def _input_for_protocol(source: VerificationInput, protocol_key: str) -> VerificationInput:
    """Allow a frozen envelope to carry exact per-protocol payloads without transport coupling."""
    protocol_inputs = source.payload.get("protocol_inputs")
    if protocol_inputs is None:
        return source
    if not isinstance(protocol_inputs, dict) or protocol_key not in protocol_inputs:
        raise ValueError(f"frozen input has no payload for requested protocol {protocol_key}")
    selected = protocol_inputs[protocol_key]
    if not isinstance(selected, dict):
        raise ValueError(f"payload for protocol {protocol_key} must be a JSON object")
    return source.model_copy(update={"payload": selected, "input_sha256": None})


class VerificationOrchestrator:
    def __init__(
        self, registry: ProtocolRegistry, artifact_store: LocalArtifactStore | None = None
    ) -> None:
        self.registry = registry
        self.backend = DeterministicBackend(registry)
        self.artifact_store = artifact_store

    def execute(self, request: VerificationRequest) -> VerificationResponse:
        started_at = datetime.now(UTC)
        correlation_id = request.correlation_id or str(uuid4())
        logger.info(
            "verification run started",
            extra={"run_id": request.run_id, "correlation_id": correlation_id},
        )
        findings: list[VerificationFinding] = []
        for protocol in request.protocols:
            selected_input = _input_for_protocol(request.input, protocol.key)
            result = self.backend.execute(selected_input, protocol)
            findings.extend(result.findings)
            logger.info(
                "protocol completed",
                extra={
                    "run_id": request.run_id,
                    "correlation_id": correlation_id,
                    "protocol": protocol.key,
                },
            )
        findings_tuple = tuple(findings)
        # One canonical machine artifact captures raw immutable findings;
        # bytes can be stored by the worker.
        artifact = create_json_artifact(
            {"run_id": request.run_id, "findings": findings_tuple},
            protocol=ProtocolRef(name="verification-findings-artifact", version="0.1.0"),
            input_hashes=(request.input.computed_sha256,),
            finding_ids=tuple(item.finding_id for item in findings_tuple),
            filename=f"{request.run_id}-findings.json",
        )
        if self.artifact_store is not None:
            self.artifact_store.persist(artifact)
        python_version, platform_name = runtime_identity()
        execution = VerificationExecutionMetadata(
            backend=self.backend.name,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            run_id=request.run_id,
            correlation_id=correlation_id,
            python_version=python_version,
            platform=platform_name,
            tool_versions=tool_versions(),
            input_sha256=request.input.computed_sha256,
            execution_passport_id=(
                request.input.execution_passport.passport_id
                if request.input.execution_passport is not None
                else None
            ),
        )
        return VerificationResponse(
            run_id=request.run_id,
            findings=findings_tuple,
            artifacts=(artifact.metadata,),
            execution=execution,
        )
