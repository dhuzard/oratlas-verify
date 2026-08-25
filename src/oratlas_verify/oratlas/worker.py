"""One-shot ORAtlas worker for deterministic scientific verification."""

from __future__ import annotations

import logging
import platform
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

import numpy
import scipy
from pydantic import BaseModel, ConfigDict, ValidationError

from oratlas_verify import __version__
from oratlas_verify.core.contracts import ProtocolRef, VerificationFinding, VerificationInput
from oratlas_verify.core.errors import (
    ORAtlasInputIntegrityError,
    ORAtlasLeaseExpired,
    ORAtlasProtocolMismatch,
)
from oratlas_verify.core.json import canonical_json_bytes, sha256_bytes, sha256_json
from oratlas_verify.core.registry import ProtocolRegistry
from oratlas_verify.execution.deterministic import DeterministicBackend
from oratlas_verify.oratlas.client import ORAtlasClient
from oratlas_verify.oratlas.dtos import (
    BLINDED_PUBLICATION_INPUT_SCHEMA,
    PUBLICATION_PACKET_SCHEMA_VERSION,
    ArtifactPrepareDTO,
    BlindedPublicationInputDTO,
    EvidenceReferenceDTO,
    FindingSubmissionDTO,
    PublicationInputDTO,
    PublicationVerificationProjectionDTO,
    PublicationVersionPacketDTO,
    PublicationVersionSubjectDTO,
    PublicVerificationRunDTO,
    VerificationFindingDTO,
    VerificationInputDTO,
    VerificationProtocolDTO,
)
from oratlas_verify.oratlas.mapping import map_finding
from oratlas_verify.verifiers.statistics.extraction import extract_statistic_candidates
from oratlas_verify.verifiers.statistics.models import StatisticAssertion

logger = logging.getLogger(__name__)
STATISTICS_REPORT_SCHEMA = "oratlas-verify-statistics-report/0.1.0"
STATISTICS_PROTOCOL = ProtocolRef(name="reported-statistic-consistency", version="0.1.0")


class WorkerRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    protocol: ProtocolRef
    input_sha256: str
    input_profile: str
    input_profile_version: str
    artifact_id: str
    artifact_sha256: str
    findings: tuple[VerificationFindingDTO, ...]
    public_run: PublicVerificationRunDTO
    publication_projection: PublicationVerificationProjectionDTO


def _validate_packet(
    frozen: VerificationInputDTO,
    subject: PublicationVersionSubjectDTO,
) -> PublicationInputDTO:
    if frozen.profile == "full" and frozen.schema_version == PUBLICATION_PACKET_SCHEMA_VERSION:
        packet_type: type[PublicationVersionPacketDTO | BlindedPublicationInputDTO] = (
            PublicationVersionPacketDTO
        )
    elif (
        frozen.profile == "blinded-scientific"
        and frozen.schema_version == BLINDED_PUBLICATION_INPUT_SCHEMA
    ):
        packet_type = BlindedPublicationInputDTO
    else:
        raise ORAtlasInputIntegrityError(
            f"unsupported ORAtlas input schema/profile: {frozen.schema_version}/{frozen.profile}"
        )
    try:
        packet = packet_type.model_validate(frozen.input)
    except ValidationError as exc:
        raise ORAtlasInputIntegrityError("frozen publication input schema mismatch") from exc
    if packet.schema_version != frozen.schema_version:
        raise ORAtlasInputIntegrityError("input envelope and payload schema versions differ")
    without_digest = dict(frozen.input)
    without_digest.pop("sha256", None)
    if sha256_json(without_digest) != packet.sha256:
        raise ORAtlasInputIntegrityError("publication input internal SHA-256 mismatch")
    version_id = packet.version.get("id")
    if version_id != subject.publication_version_id:
        raise ORAtlasInputIntegrityError("publication version subject mismatch")
    for document in packet.content:
        if sha256_bytes(document.text.encode("utf-8")) != document.sha256:
            raise ORAtlasInputIntegrityError(
                f"publication content document integrity mismatch: {document.id}"
            )
    return packet


def _protocol_ref(protocol: VerificationProtocolDTO, registry: ProtocolRegistry) -> ProtocolRef:
    ref = ProtocolRef(name=protocol.series_key, version=protocol.protocol_version)
    if protocol.id == "" or protocol.status != "active":
        raise ORAtlasProtocolMismatch("ORAtlas verification protocol is not active")
    if protocol.verification_type != protocol.series_key:
        raise ORAtlasProtocolMismatch("ORAtlas protocol series/type mismatch")
    try:
        registry.resolve(ref)
    except Exception as exc:
        raise ORAtlasProtocolMismatch(f"unsupported ORAtlas protocol: {ref.key}") from exc
    if ref != STATISTICS_PROTOCOL:
        raise ORAtlasProtocolMismatch(
            f"ORAtlas worker round trip is not enabled for protocol: {ref.key}"
        )
    return ref


def _publication_identity(packet: PublicationInputDTO) -> tuple[str, str]:
    publication_id = packet.publication.get("id")
    version_id = packet.version.get("id")
    if not isinstance(publication_id, str) or not isinstance(version_id, str):
        raise ORAtlasInputIntegrityError("publication packet omitted exact publication identity")
    return publication_id, version_id


def _scientific_inputs(
    packet: PublicationInputDTO,
    publication_id: str,
    publication_version_id: str,
) -> tuple[tuple[VerificationInput, dict[str, Any], EvidenceReferenceDTO], ...]:
    values: list[tuple[VerificationInput, dict[str, Any], EvidenceReferenceDTO]] = []
    for document in packet.content:
        extraction = extract_statistic_candidates(document.text, evidence_id=document.id)
        for assertion in extraction.assertions:
            payload = assertion.model_dump(mode="json", exclude_none=True)
            evidence = EvidenceReferenceDTO(type="publication-content-document", id=document.id)
            values.append(
                (
                    VerificationInput(
                        publication_id=publication_id,
                        publication_version_id=publication_version_id,
                        payload=payload,
                        evidence_ids=(document.id,),
                    ),
                    payload,
                    evidence,
                )
            )
    if values:
        return tuple(values)
    evidence_id = packet.content[0].id if packet.content else ""
    assertion = StatisticAssertion()
    payload = assertion.model_dump(mode="json", exclude_none=True)
    fallback_evidence = (
        EvidenceReferenceDTO(type="publication-content-document", id=evidence_id)
        if evidence_id
        else None
    )
    return (
        (
            (
                VerificationInput(
                    publication_id=publication_id,
                    publication_version_id=publication_version_id,
                    payload=payload,
                    evidence_ids=(evidence_id,) if evidence_id else (),
                ),
                payload,
                fallback_evidence,
            ),
        )
        if fallback_evidence is not None
        else ()
    )


def _assert_exact_submission(
    request: FindingSubmissionDTO, response: VerificationFindingDTO
) -> None:
    pairs = (
        (request.finding_key, response.finding_key),
        (request.finding_type, response.finding_type),
        (request.status, response.status),
        (request.impact, response.impact),
        (request.statement, response.statement),
        (request.rationale, response.rationale),
        (request.reported, response.reported),
        (request.observed, response.observed),
        (request.tolerance, response.tolerance),
        (request.evidence_refs, response.evidence_refs),
        (request.artifact_refs, response.artifact_refs),
    )
    if any(left != right for left, right in pairs):
        raise ORAtlasInputIntegrityError("ORAtlas public finding differs from submitted finding")


class ORAtlasVerificationWorker:
    def __init__(self, registry: ProtocolRegistry) -> None:
        self.registry = registry
        self.backend = DeterministicBackend(registry)

    def run(
        self, run_id: str, client: ORAtlasClient, *, lease_seconds: int = 300
    ) -> WorkerRunResult:
        claimed = False
        try:
            claim = client.claim_run(run_id, lease_seconds)
            claimed = True
            frozen = client.retrieve_frozen_input(run_id)
            if (
                claim.input.profile != frozen.profile
                or claim.input.profile_version != frozen.profile_version
                or claim.input.schema_version != frozen.schema_version
                or claim.input.sha256 != frozen.sha256
            ):
                raise ORAtlasInputIntegrityError("claim and frozen-input metadata differ")
            protocol_dto = client.get_protocol(claim.verification_protocol_id)
            if protocol_dto.id != claim.verification_protocol_id:
                raise ORAtlasProtocolMismatch("ORAtlas protocol id mismatch")
            protocol = _protocol_ref(protocol_dto, self.registry)
            if not isinstance(claim.subject, PublicationVersionSubjectDTO):
                raise ORAtlasProtocolMismatch(
                    "reported-statistic worker currently requires a publication-version subject"
                )
            if claim.subject.type not in protocol_dto.supported_subject_types:
                raise ORAtlasProtocolMismatch("ORAtlas protocol does not support the run subject")
            packet = _validate_packet(frozen, claim.subject)
            publication_id, publication_version_id = _publication_identity(packet)
            client.transition_run(run_id, "running")
            started_at = datetime.now(UTC)
            executions = _scientific_inputs(packet, publication_id, publication_version_id)
            if not executions:
                raise ORAtlasInputIntegrityError("publication input contains no citable content")
            local_results: list[
                tuple[VerificationFinding, dict[str, Any], EvidenceReferenceDTO]
            ] = []
            for scientific_input, payload, evidence in executions:
                result = self.backend.execute(scientific_input, protocol)
                local_results.extend((finding, payload, evidence) for finding in result.findings)
            completed_at = datetime.now(UTC)
            report = {
                "schemaVersion": STATISTICS_REPORT_SCHEMA,
                "protocol": {"series": protocol.name, "version": protocol.version},
                "input": {
                    "schemaVersion": frozen.schema_version,
                    "sha256": frozen.sha256,
                    "profile": frozen.profile,
                    "profileVersion": frozen.profile_version,
                    "publicationId": publication_id,
                    "publicationVersionId": publication_version_id,
                    "assertions": [payload for _, payload, _ in local_results],
                },
                "calculation": {
                    "engine": self.backend.name,
                    "results": [finding.details for finding, _, _ in local_results],
                },
                "result": {
                    "statuses": [finding.status.value for finding, _, _ in local_results],
                    "rationales": [finding.rationale for finding, _, _ in local_results],
                },
                "software": {
                    "oratlasVerify": __version__,
                    "python": platform.python_version(),
                    "scipy": scipy.__version__,
                    "numpy": numpy.__version__,
                },
                "provenance": {
                    "runId": run_id,
                    "platform": platform.platform(),
                    "inputSha256": frozen.sha256,
                    "inputProfile": frozen.profile,
                    "inputProfileVersion": frozen.profile_version,
                    "startedAt": started_at.isoformat(),
                    "completedAt": completed_at.isoformat(),
                },
            }
            artifact_bytes = canonical_json_bytes(report)
            artifact_sha256 = sha256_bytes(artifact_bytes)
            artifact_key = f"statistics-report-{frozen.sha256[:24]}"
            negotiation = client.prepare_artifact(
                run_id,
                ArtifactPrepareDTO(
                    artifactKey=artifact_key,
                    kind="statistics-report",
                    mediaType="application/json",
                    sha256=artifact_sha256,
                    byteLength=len(artifact_bytes),
                    visibility="public",
                ),
            )
            client.upload_artifact(
                run_id, negotiation.artifact_id, artifact_bytes, "application/json"
            )
            completed_artifact = client.complete_artifact(run_id, negotiation.artifact_id)
            if completed_artifact.sha256 != artifact_sha256:
                raise ORAtlasInputIntegrityError("completed artifact digest mismatch")
            submissions = tuple(
                map_finding(
                    finding,
                    payload,
                    evidence_refs=(evidence,),
                    artifact_ids=(completed_artifact.id,),
                )
                for finding, payload, evidence in local_results
            )
            submitted = tuple(client.submit_finding(run_id, item) for item in submissions)
            for request, response in zip(submissions, submitted, strict=True):
                _assert_exact_submission(request, response)
            client.transition_run(run_id, "completed")
            public_run = client.get_public_run(run_id)
            projection = client.list_publication_version_verifications(publication_version_id)
            public_by_key = {item.finding_key: item for item in public_run.findings}
            projected_run = next((item for item in projection.runs if item.id == run_id), None)
            if public_run.status != "completed" or projected_run is None:
                raise ORAtlasInputIntegrityError("completed run is absent from public projection")
            projected_by_key = {item.finding_key: item for item in projected_run.findings}
            for request in submissions:
                public = public_by_key.get(request.finding_key)
                projected = projected_by_key.get(request.finding_key)
                if public is None or projected is None:
                    raise ORAtlasInputIntegrityError(
                        "submitted finding is absent from public evidence"
                    )
                _assert_exact_submission(request, public)
                _assert_exact_submission(request, projected)
            return WorkerRunResult(
                run_id=run_id,
                protocol=protocol,
                input_sha256=frozen.sha256,
                input_profile=frozen.profile,
                input_profile_version=frozen.profile_version,
                artifact_id=completed_artifact.id,
                artifact_sha256=artifact_sha256,
                findings=submitted,
                public_run=public_run,
                publication_projection=projection,
            )
        except Exception as exc:
            if claimed:
                try:
                    client.transition_run(run_id, "failed", reason=type(exc).__name__[:4_000])
                except ORAtlasLeaseExpired:
                    logger.warning(
                        "verification lease expired before failure transition",
                        extra={"run_id": run_id},
                    )
                except Exception:
                    logger.exception(
                        "failed to transition verification run", extra={"run_id": run_id}
                    )
            raise


def installed_scipy_version() -> str:
    """Expose the actual installed distribution version for acceptance assertions."""
    return metadata.version("scipy")
