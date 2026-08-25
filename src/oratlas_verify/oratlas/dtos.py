"""Evolving HTTP DTOs mapped explicitly to stable local domain contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from oratlas_verify.core.contracts import (
    ArtifactReference,
    ExecutionPassport,
    ProtocolRef,
    VerificationArtifact,
    VerificationFinding,
    VerificationInput,
    VerificationRequest,
)


class TransportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProtocolDTO(TransportModel):
    name: str
    version: str

    def to_domain(self) -> ProtocolRef:
        return ProtocolRef(name=self.name, version=self.version)


class ArtifactReferenceDTO(TransportModel):
    artifact_id: str = Field(alias="artifactId")
    sha256: str
    media_type: str = Field(alias="mediaType")
    byte_length: int = Field(alias="byteLength")

    def to_domain(self) -> ArtifactReference:
        return ArtifactReference(**self.model_dump())


class ExecutionPassportDTO(TransportModel):
    passport_id: str = Field(alias="passportId")
    source_commit: str | None = Field(default=None, alias="sourceCommit")
    workflow: str | None = None
    environment: dict[str, Any] = Field(default_factory=dict)
    artifact_hashes: tuple[str, ...] = Field(default=(), alias="artifactHashes")
    verified_by_oratlas: bool = Field(default=False, alias="verifiedByORAtlas")

    def to_domain(self) -> ExecutionPassport:
        return ExecutionPassport(**self.model_dump())


class FrozenInputDTO(TransportModel):
    publication_id: str = Field(alias="publicationId")
    publication_version_id: str = Field(alias="publicationVersionId")
    payload: dict[str, Any]
    evidence_ids: tuple[str, ...] = Field(default=(), alias="evidenceIds")
    artifact_references: tuple[ArtifactReferenceDTO, ...] = Field(
        default=(), alias="artifactReferences"
    )
    execution_passport: ExecutionPassportDTO | None = Field(default=None, alias="executionPassport")
    input_sha256: str = Field(alias="inputSha256")

    def to_domain(self) -> VerificationInput:
        return VerificationInput(
            publication_id=self.publication_id,
            publication_version_id=self.publication_version_id,
            payload=self.payload,
            evidence_ids=self.evidence_ids,
            artifact_references=tuple(item.to_domain() for item in self.artifact_references),
            execution_passport=(
                self.execution_passport.to_domain() if self.execution_passport is not None else None
            ),
            input_sha256=self.input_sha256,
        )


class VerificationRunDTO(TransportModel):
    run_id: str = Field(alias="runId")
    frozen_input: FrozenInputDTO = Field(alias="frozenInput")
    protocols: tuple[ProtocolDTO, ...]
    requested_at: datetime | None = Field(default=None, alias="requestedAt")
    correlation_id: str | None = Field(default=None, alias="correlationId")

    def to_domain(self) -> VerificationRequest:
        return VerificationRequest(
            run_id=self.run_id,
            input=self.frozen_input.to_domain(),
            protocols=tuple(item.to_domain() for item in self.protocols),
            requested_at=self.requested_at,
            correlation_id=self.correlation_id,
        )


class CreateVerificationRunDTO(TransportModel):
    publication_id: str = Field(alias="publicationId")
    publication_version_id: str = Field(alias="publicationVersionId")
    protocols: tuple[ProtocolDTO, ...]


class FindingSubmissionDTO(TransportModel):
    findings: list[dict[str, Any]]

    @classmethod
    def from_domain(cls, findings: tuple[VerificationFinding, ...]) -> FindingSubmissionDTO:
        return cls(findings=[item.model_dump(mode="json", by_alias=True) for item in findings])


class ArtifactSubmissionDTO(TransportModel):
    artifacts: list[dict[str, Any]]

    @classmethod
    def from_domain(cls, artifacts: tuple[VerificationArtifact, ...]) -> ArtifactSubmissionDTO:
        return cls(artifacts=[item.model_dump(mode="json", by_alias=True) for item in artifacts])


class TransitionDTO(TransportModel):
    state: Literal["completed", "failed"]
    reason: str | None = None
