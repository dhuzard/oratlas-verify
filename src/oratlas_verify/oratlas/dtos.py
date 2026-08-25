"""Strict DTOs for the pinned ORAtlas scientific-verification API subset."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from oratlas_verify.core.contracts import FindingStatus, JsonValue
from oratlas_verify.core.json import canonical_json_bytes

VERIFICATION_API_SCHEMA_VERSION = "1.0.0"
VERIFICATION_INPUT_PROFILE_VERSION = "1.0.0"
PUBLICATION_PACKET_SCHEMA_VERSION = "1.3.0"
BLINDED_PUBLICATION_INPUT_SCHEMA = "verification-publication-input/1.0.0"
LEASE_HEADER = "X-ORAtlas-Verification-Lease"
ARTIFACT_MAX_BYTES = 8 * 1024 * 1024
STABLE_KEY_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"


class TransportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)


class PublicationVersionSubjectDTO(TransportModel):
    type: Literal["publication-version"]
    publication_version_id: str = Field(alias="publicationVersionId", min_length=1)


class PublicationClaimSubjectDTO(TransportModel):
    type: Literal["publication-claim-occurrence"]
    publication_claim_occurrence_id: str = Field(alias="publicationClaimOccurrenceId", min_length=1)


class KnowledgeNodeVersionSubjectDTO(TransportModel):
    type: Literal["knowledge-node-version"]
    knowledge_node_version_id: str = Field(alias="knowledgeNodeVersionId", min_length=1)


VerificationSubjectDTO = (
    PublicationVersionSubjectDTO | PublicationClaimSubjectDTO | KnowledgeNodeVersionSubjectDTO
)


class RunInputMetadataDTO(TransportModel):
    profile: Literal["full", "blinded-scientific"]
    profile_version: Literal["1.0.0"] = Field(alias="profileVersion")
    schema_version: str = Field(alias="schemaVersion", min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime = Field(alias="capturedAt")


class RunProvenanceDTO(TransportModel):
    agent_run_id: str | None = Field(alias="agentRunId")
    execution_passport_id: str | None = Field(alias="executionPassportId")
    replication_brief_id: str | None = Field(alias="replicationBriefId")


class RunLinksDTO(TransportModel):
    self: str
    claim: str
    input: str
    findings: str
    transition: str


class VerificationRunDTO(TransportModel):
    id: str = Field(min_length=1)
    verification_protocol_id: str = Field(alias="verificationProtocolId", min_length=1)
    subject: VerificationSubjectDTO = Field(discriminator="type")
    claimed_verifier_id: str | None = Field(alias="claimedVerifierId")
    status: Literal["requested", "claimed", "running", "completed", "failed", "cancelled"]
    input: RunInputMetadataDTO
    requested_at: datetime = Field(alias="requestedAt")
    claimed_at: datetime | None = Field(alias="claimedAt")
    started_at: datetime | None = Field(alias="startedAt")
    completed_at: datetime | None = Field(alias="completedAt")
    terminal_reason: str | None = Field(alias="terminalReason")
    provenance: RunProvenanceDTO
    replayed: bool
    links: RunLinksDTO


class VerificationClaimResponseDTO(VerificationRunDTO):
    lease_token: str = Field(alias="leaseToken", pattern=r"^oratlas_lease_", repr=False)
    lease_expires_at: datetime = Field(alias="leaseExpiresAt")


class SourceArtifactDTO(TransportModel):
    id: str = Field(min_length=1)
    media_type: str = Field(alias="mediaType", min_length=3)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(alias="byteLength", ge=0)
    available: bool
    href: str


class VerificationInputDTO(TransportModel):
    verification_run_id: str = Field(alias="verificationRunId", min_length=1)
    schema_version: str = Field(alias="schemaVersion", min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile: Literal["full", "blinded-scientific"]
    profile_version: Literal["1.0.0"] = Field(alias="profileVersion")
    captured_at: datetime = Field(alias="capturedAt")
    input: dict[str, JsonValue]
    source_artifacts: tuple[SourceArtifactDTO, ...] = Field(alias="sourceArtifacts")


class PublicationContentDocumentDTO(TransportModel):
    id: str = Field(min_length=1, max_length=200)
    title: str | None
    role: (
        Literal[
            "abstract",
            "introduction",
            "methods",
            "results",
            "discussion",
            "limitations",
            "references",
            "supplementary",
            "other",
        ]
        | None
    )
    source_path: str | None = Field(alias="sourcePath")
    published_url: str | None = Field(alias="publishedUrl")
    representation: Literal["published-structured-text", "source-text"]
    text: str = Field(min_length=1, max_length=1_000_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_artifact_identity_sha256: str = Field(
        alias="sourceArtifactIdentitySha256", pattern=r"^[0-9a-f]{64}$"
    )
    source_artifact_sha256: str = Field(alias="sourceArtifactSha256", pattern=r"^[0-9a-f]{64}$")


class PublicationVersionPacketDTO(TransportModel):
    schema_version: Literal["1.3.0"] = Field(alias="schemaVersion")
    publication: dict[str, JsonValue]
    version: dict[str, JsonValue]
    captures: tuple[dict[str, JsonValue], ...]
    content: tuple[PublicationContentDocumentDTO, ...]
    contributors: tuple[JsonValue, ...]
    occurrences: tuple[dict[str, JsonValue], ...]
    production_provenance: tuple[JsonValue, ...] = Field(alias="productionProvenance")
    relations: tuple[dict[str, JsonValue], ...]
    challenges: tuple[JsonValue, ...]
    completeness: dict[str, JsonValue]
    links: dict[str, JsonValue]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BlindedPublicationInputDTO(TransportModel):
    schema_version: Literal["verification-publication-input/1.0.0"] = Field(alias="schemaVersion")
    source_packet_schema_version: Literal["1.3.0"] = Field(alias="sourcePacketSchemaVersion")
    publication: dict[str, JsonValue]
    version: dict[str, JsonValue]
    captures: tuple[dict[str, JsonValue], ...]
    content: tuple[PublicationContentDocumentDTO, ...]
    contributors: tuple[JsonValue, ...]
    occurrences: tuple[dict[str, JsonValue], ...]
    production_provenance: tuple[JsonValue, ...] = Field(alias="productionProvenance")
    relations: tuple[dict[str, JsonValue], ...]
    challenges: tuple[JsonValue, ...]
    completeness: dict[str, JsonValue]
    links: dict[str, JsonValue]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def ensure_blinded(self) -> BlindedPublicationInputDTO:
        if self.contributors or self.production_provenance:
            raise ValueError("blinded-scientific input retained identifying presentation metadata")
        return self


PublicationInputDTO = PublicationVersionPacketDTO | BlindedPublicationInputDTO


class ProtocolAuthorityDTO(TransportModel):
    id: str
    slug: str
    name: str


class VerificationProtocolDTO(TransportModel):
    id: str
    authority_verifier_id: str = Field(alias="authorityVerifierId")
    authority: ProtocolAuthorityDTO
    series_key: str = Field(alias="seriesKey", pattern=STABLE_KEY_PATTERN, max_length=120)
    protocol_version: str = Field(alias="protocolVersion", min_length=1, max_length=50)
    title: str
    description: str
    verification_type: str = Field(alias="verificationType", pattern=STABLE_KEY_PATTERN)
    execution_mode: Literal["deterministic", "human", "ai", "hybrid", "external-execution"] = Field(
        alias="executionMode"
    )
    supported_subject_types: tuple[
        Literal["publication-version", "publication-claim-occurrence", "knowledge-node-version"],
        ...,
    ] = Field(alias="supportedSubjectTypes")
    definition: JsonValue
    definition_sha256: str = Field(alias="definitionSha256", pattern=r"^[0-9a-f]{64}$")
    status: Literal["active", "retired"]
    supersedes_protocol_id: str | None = Field(alias="supersedesProtocolId")
    created_at: datetime = Field(alias="createdAt")
    href: str


class VerificationProtocolsDTO(TransportModel):
    schema_version: Literal["1.0.0"] = Field(alias="schemaVersion")
    protocols: tuple[VerificationProtocolDTO, ...]


class ClaimRequestDTO(TransportModel):
    lease_seconds: int = Field(default=300, alias="leaseSeconds", ge=60, le=900)


class ArtifactPrepareDTO(TransportModel):
    artifact_key: str = Field(alias="artifactKey", pattern=STABLE_KEY_PATTERN, max_length=120)
    kind: str = Field(pattern=STABLE_KEY_PATTERN, max_length=120)
    media_type: str = Field(alias="mediaType", min_length=3, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(alias="byteLength", ge=0, le=ARTIFACT_MAX_BYTES)
    visibility: Literal["private", "public"] = "public"


class ArtifactUploadDTO(TransportModel):
    type: Literal["oratlas-direct-binary-v1"]
    method: Literal["PUT"]
    href: str
    headers: dict[str, str]


class ArtifactNegotiationDTO(TransportModel):
    artifact_id: str = Field(alias="artifactId")
    status: Literal["prepared", "uploaded", "completed"]
    upload: ArtifactUploadDTO
    expires_at: datetime = Field(alias="expiresAt")
    replayed: bool


class VerificationArtifactDTO(TransportModel):
    id: str
    verification_run_id: str = Field(alias="verificationRunId")
    artifact_key: str = Field(alias="artifactKey")
    kind: str
    media_type: str = Field(alias="mediaType")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(alias="byteLength", ge=0, le=ARTIFACT_MAX_BYTES)
    visibility: Literal["private", "public"]
    status: Literal["prepared", "uploaded", "completed"]
    provenance: dict[str, JsonValue]
    created_at: datetime = Field(alias="createdAt")
    content_href: str | None = Field(alias="contentHref")
    replayed: bool = False


EvidenceType = Literal[
    "publication-content-document",
    "publication-occurrence",
    "canonical-node-version",
    "canonical-relation",
    "capture",
    "production-provenance",
    "execution-passport",
    "verification-artifact",
]


class EvidenceReferenceDTO(TransportModel):
    type: EvidenceType
    id: str = Field(min_length=1)


def _json_depth(value: object, depth: int = 0) -> int:
    if depth > 12:
        return depth
    if isinstance(value, list | tuple):
        return max((depth, *(_json_depth(item, depth + 1) for item in value)))
    if isinstance(value, dict):
        return max((depth, *(_json_depth(item, depth + 1) for item in value.values())))
    return depth


def _validate_structured_json(value: JsonValue | None) -> JsonValue | None:
    def finite(item: object) -> bool:
        if isinstance(item, float):
            return math.isfinite(item)
        if isinstance(item, list | tuple):
            return all(finite(child) for child in item)
        if isinstance(item, dict):
            return all(isinstance(key, str) and finite(child) for key, child in item.items())
        return item is None or isinstance(item, bool | int | str)

    if not finite(value):
        raise ValueError("structured finding fields must contain plain finite JSON")
    if _json_depth(value) > 12:
        raise ValueError("structured finding fields exceed depth 12")
    if len(canonical_json_bytes(value)) > 64 * 1024:
        raise ValueError("structured finding fields exceed 64 KiB")
    return value


class FindingSubmissionDTO(TransportModel):
    finding_key: str = Field(alias="findingKey", pattern=STABLE_KEY_PATTERN, max_length=120)
    finding_type: str = Field(alias="findingType", pattern=STABLE_KEY_PATTERN, max_length=120)
    status: FindingStatus
    impact: Literal["informational", "minor", "major", "critical"]
    statement: str = Field(min_length=1, max_length=10_000)
    rationale: str = Field(min_length=1, max_length=20_000)
    reported: JsonValue | None = None
    observed: JsonValue | None = None
    tolerance: JsonValue | None = None
    evidence_refs: tuple[EvidenceReferenceDTO, ...] = Field(default=(), alias="evidenceRefs")
    artifact_refs: tuple[str, ...] = Field(default=(), alias="artifactRefs", max_length=100)
    supersedes_finding_id: str | None = Field(default=None, alias="supersedesFindingId")

    _reported_json = field_validator("reported")(_validate_structured_json)
    _observed_json = field_validator("observed")(_validate_structured_json)
    _tolerance_json = field_validator("tolerance")(_validate_structured_json)

    @model_validator(mode="after")
    def unique_references(self) -> FindingSubmissionDTO:
        if len(set(self.artifact_refs)) != len(self.artifact_refs):
            raise ValueError("artifact references must be unique")
        evidence = {(item.type, item.id) for item in self.evidence_refs}
        if len(evidence) != len(self.evidence_refs):
            raise ValueError("evidence references must be unique")
        return self


class VerificationFindingDTO(TransportModel):
    id: str
    verification_run_id: str = Field(alias="verificationRunId")
    submitted_by_verifier_id: str = Field(alias="submittedByVerifierId")
    finding_key: str = Field(alias="findingKey")
    finding_type: str = Field(alias="findingType")
    status: FindingStatus
    impact: Literal["informational", "minor", "major", "critical"]
    statement: str
    rationale: str
    reported: JsonValue | None
    observed: JsonValue | None
    tolerance: JsonValue | None
    evidence_refs: tuple[EvidenceReferenceDTO, ...] = Field(alias="evidenceRefs")
    artifact_refs: tuple[str, ...] = Field(alias="artifactRefs")
    payload_sha256: str = Field(alias="payloadSha256", pattern=r"^[0-9a-f]{64}$")
    supersedes_finding_id: str | None = Field(alias="supersedesFindingId")
    created_at: datetime = Field(alias="createdAt")
    replayed: bool = False


class TransitionDTO(TransportModel):
    status: Literal["running", "completed", "failed"]
    reason: str | None = Field(default=None, min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def reason_matches_status(self) -> TransitionDTO:
        if self.status == "failed" and self.reason is None:
            raise ValueError("failed transition requires a reason")
        if self.status != "failed" and self.reason is not None:
            raise ValueError("only failed transitions accept a reason")
        return self


class EmbeddedVerifierDTO(TransportModel):
    id: str
    slug: str
    name: str


class PublicVerifierDTO(EmbeddedVerifierDTO):
    description: str
    public_url: str | None = Field(alias="publicUrl")
    status: Literal["active", "suspended", "retired"]
    created_at: datetime = Field(alias="createdAt")
    href: str


class PublicVerifiersDTO(TransportModel):
    schema_version: Literal["1.0.0"] = Field(alias="schemaVersion")
    verifiers: tuple[PublicVerifierDTO, ...]


class LifecycleEventDTO(TransportModel):
    kind: str
    actor_user_id: str | None = Field(alias="actorUserId")
    actor_verifier_id: str | None = Field(alias="actorVerifierId")
    details: dict[str, JsonValue]
    created_at: datetime = Field(alias="createdAt")


class PublicVerificationRunDTO(VerificationRunDTO):
    protocol: VerificationProtocolDTO
    verifier: EmbeddedVerifierDTO | None
    artifacts: tuple[VerificationArtifactDTO, ...]
    findings: tuple[VerificationFindingDTO, ...]
    lifecycle: tuple[LifecycleEventDTO, ...]
    limitations: tuple[str, ...]


class ProjectionProtocolDTO(TransportModel):
    series_key: str = Field(alias="seriesKey")
    version: str


class ProjectionRunDTO(VerificationRunDTO):
    protocol: ProjectionProtocolDTO
    verifier: EmbeddedVerifierDTO | None
    findings: tuple[VerificationFindingDTO, ...]


class PublicationVerificationProjectionDTO(TransportModel):
    schema_version: Literal["1.0.0"] = Field(alias="schemaVersion")
    publication_version_id: str = Field(alias="publicationVersionId")
    summary: dict[str, dict[str, int]]
    runs: tuple[ProjectionRunDTO, ...]


class FindingsListDTO(TransportModel):
    schema_version: Literal["1.0.0"] = Field(alias="schemaVersion")
    verification_run_id: str = Field(alias="verificationRunId")
    findings: tuple[VerificationFindingDTO, ...]


def dump_request(model: TransportModel) -> dict[str, Any]:
    """Return an alias-cased request body with absent optional fields omitted."""
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def response_json(response_text: str) -> object:
    """Parse JSON without accepting NaN or Infinity extensions."""
    return json.loads(
        response_text,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
