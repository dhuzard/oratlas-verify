"""Synchronous client for ORAtlas verification API 1.0.0."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, TypeVar
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter, ValidationError

from oratlas_verify.core.errors import (
    ORAtlasArtifactIntegrityError,
    ORAtlasAuthenticationError,
    ORAtlasAuthorizationError,
    ORAtlasIdempotencyConflict,
    ORAtlasInputIntegrityError,
    ORAtlasLeaseConflict,
    ORAtlasLeaseExpired,
    ORAtlasServerError,
    TransportError,
)
from oratlas_verify.core.json import sha256_bytes, sha256_json
from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.dtos import (
    LEASE_HEADER,
    ArtifactNegotiationDTO,
    ArtifactPrepareDTO,
    ClaimRequestDTO,
    FindingsListDTO,
    FindingSubmissionDTO,
    PublicationVerificationProjectionDTO,
    PublicVerificationRunDTO,
    PublicVerifierDTO,
    PublicVerifiersDTO,
    SourceArtifactDTO,
    TransitionDTO,
    VerificationArtifactDTO,
    VerificationClaimResponseDTO,
    VerificationFindingDTO,
    VerificationInputDTO,
    VerificationProtocolDTO,
    VerificationProtocolsDTO,
    VerificationRunDTO,
    dump_request,
    response_json,
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True, repr=False)
class _Lease:
    token: str
    expires_at: datetime


class ORAtlasClient:
    """Exact route owner; lease secrets are retained only in process memory."""

    def __init__(
        self, config: ORAtlasConfig, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.config = config
        self._leases: dict[str, _Lease] = {}
        self._client = httpx.Client(
            base_url=f"{config.base_url.rstrip('/')}/",
            headers={"Accept": "application/json"},
            timeout=config.timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self) -> ORAtlasClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._leases.clear()
        self._client.close()

    @staticmethod
    def _run_path(run_id: str, suffix: str = "") -> str:
        encoded = quote(run_id, safe="")
        return f"/api/verification-runs/{encoded}{suffix}"

    def _lease_header(self, run_id: str) -> dict[str, str]:
        lease = self._leases.get(run_id)
        if lease is None:
            raise ORAtlasLeaseConflict("ORAtlas run has not been claimed by this client")
        if lease.expires_at <= datetime.now(UTC):
            raise ORAtlasLeaseExpired("ORAtlas verification lease expired")
        return {LEASE_HEADER: lease.token}

    def _headers(self, *, run_id: str | None = None) -> dict[str, str]:
        headers = self.config.authorization_header()
        if run_id is not None:
            headers.update(self._lease_header(run_id))
        return headers

    def _raise_status(
        self,
        response: httpx.Response,
        method: str,
        path: str,
        *,
        conflict: Literal["lease", "idempotency"] = "lease",
        run_id: str | None = None,
    ) -> None:
        status = response.status_code
        message = f"ORAtlas request failed: {method} {path} (HTTP {status})"
        if status == 401:
            raise ORAtlasAuthenticationError(message)
        if status == 403:
            if run_id is not None:
                lease = self._leases.get(run_id)
                if lease is not None and lease.expires_at <= datetime.now(UTC):
                    raise ORAtlasLeaseExpired(message)
            raise ORAtlasAuthorizationError(message)
        if status == 409:
            error = (
                ORAtlasIdempotencyConflict if conflict == "idempotency" else ORAtlasLeaseConflict
            )
            raise error(message)
        if status >= 500:
            raise ORAtlasServerError(message)
        raise TransportError(message)

    def _request(
        self,
        method: str,
        path: str,
        *,
        run_id: str | None = None,
        json_body: object | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        conflict: Literal["lease", "idempotency"] = "lease",
        retry_transient: bool = False,
    ) -> httpx.Response:
        attempts = 3 if retry_transient else 1
        request_headers = self._headers(run_id=run_id) if run_id is not None else {}
        if headers:
            request_headers.update(headers)
        for attempt in range(attempts):
            try:
                response = self._client.request(
                    method,
                    path,
                    headers=request_headers,
                    json=json_body,
                    content=content,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt + 1 == attempts:
                    raise ORAtlasServerError(
                        f"ORAtlas request failed: {method} {path} (network error)"
                    ) from exc
                time.sleep(0.1 * (2**attempt))
                continue
            if response.is_success:
                return response
            if response.status_code >= 500 and attempt + 1 < attempts:
                time.sleep(0.1 * (2**attempt))
                continue
            self._raise_status(response, method, path, conflict=conflict, run_id=run_id)
        raise AssertionError("unreachable")

    @staticmethod
    def _validate(response: httpx.Response, model_type: type[T], description: str) -> T:
        try:
            value = response_json(response.text)
            return TypeAdapter(model_type).validate_python(value)
        except (ValidationError, ValueError, TypeError) as exc:
            raise TransportError(f"ORAtlas returned invalid {description}") from exc

    def claim_run(self, run_id: str, lease_seconds: int = 300) -> VerificationClaimResponseDTO:
        request = ClaimRequestDTO(leaseSeconds=lease_seconds)
        path = self._run_path(run_id, "/claim")
        response = self._request(
            "POST",
            path,
            json_body=dump_request(request),
            headers=self.config.authorization_header(),
        )
        claim = self._validate(response, VerificationClaimResponseDTO, "claim response")
        if claim.id != run_id:
            raise TransportError("ORAtlas claim response run id mismatch")
        self._leases[run_id] = _Lease(claim.lease_token, claim.lease_expires_at)
        return claim

    def get_protocol(self, protocol_id: str) -> VerificationProtocolDTO:
        path = f"/api/verification-protocols/{quote(protocol_id, safe='')}"
        response = self._request("GET", path, retry_transient=True)
        return self._validate(response, VerificationProtocolDTO, "verification protocol")

    def list_verifiers(self) -> PublicVerifiersDTO:
        response = self._request("GET", "/api/verifiers", retry_transient=True)
        return self._validate(response, PublicVerifiersDTO, "verifier list")

    def get_verifier(self, verifier_id: str) -> PublicVerifierDTO:
        path = f"/api/verifiers/{quote(verifier_id, safe='')}"
        response = self._request("GET", path, retry_transient=True)
        return self._validate(response, PublicVerifierDTO, "verifier")

    def list_protocols(self) -> VerificationProtocolsDTO:
        response = self._request("GET", "/api/verification-protocols", retry_transient=True)
        return self._validate(response, VerificationProtocolsDTO, "verification protocol list")

    def retrieve_frozen_input(self, run_id: str) -> VerificationInputDTO:
        path = self._run_path(run_id, "/input")
        response = self._request("GET", path, run_id=run_id, retry_transient=True)
        dto = self._validate(response, VerificationInputDTO, "frozen verification input")
        if dto.verification_run_id != run_id:
            raise ORAtlasInputIntegrityError("frozen input run id mismatch")
        if sha256_json(dto.input) != dto.sha256:
            raise ORAtlasInputIntegrityError("frozen input SHA-256 mismatch")
        return dto

    def download_source_artifact(self, run_id: str, expected: SourceArtifactDTO) -> bytes:
        if not expected.available:
            raise ORAtlasArtifactIntegrityError("source artifact is marked unavailable")
        path = self._run_path(run_id, f"/source-artifacts/{quote(expected.id, safe='')}")
        response = self._request("GET", path, run_id=run_id, retry_transient=True)
        received = response.content
        header_sha = response.headers.get("X-ORAtlas-SHA256")
        header_length = response.headers.get("Content-Length")
        actual_type = response.headers.get("Content-Type", "").strip()
        if header_sha != expected.sha256:
            raise ORAtlasArtifactIntegrityError("source artifact digest header mismatch")
        if header_length is None or not header_length.isdigit():
            raise ORAtlasArtifactIntegrityError("source artifact length header is missing")
        if int(header_length) != expected.byte_length or len(received) != expected.byte_length:
            raise ORAtlasArtifactIntegrityError("source artifact byte length mismatch")
        if actual_type != expected.media_type:
            raise ORAtlasArtifactIntegrityError("source artifact media type mismatch")
        if sha256_bytes(received) != expected.sha256:
            raise ORAtlasArtifactIntegrityError("source artifact SHA-256 mismatch")
        return received

    def prepare_artifact(self, run_id: str, artifact: ArtifactPrepareDTO) -> ArtifactNegotiationDTO:
        path = self._run_path(run_id, "/artifacts/prepare")
        response = self._request(
            "POST",
            path,
            run_id=run_id,
            json_body=dump_request(artifact),
            conflict="idempotency",
            retry_transient=True,
        )
        negotiation = self._validate(response, ArtifactNegotiationDTO, "artifact negotiation")
        artifact_id = quote(negotiation.artifact_id, safe="")
        expected_href = f"/api/verification-artifacts/{artifact_id}/content"
        if negotiation.upload.href != expected_href:
            raise ORAtlasArtifactIntegrityError(
                "ORAtlas returned a non-canonical artifact upload path"
            )
        return negotiation

    def upload_artifact(
        self, run_id: str, artifact_id: str, content: bytes, media_type: str
    ) -> VerificationArtifactDTO:
        path = f"/api/verification-artifacts/{quote(artifact_id, safe='')}/content"
        response = self._request(
            "PUT",
            path,
            run_id=run_id,
            content=content,
            headers={"Content-Type": media_type, "Content-Length": str(len(content))},
            conflict="idempotency",
            retry_transient=True,
        )
        artifact = self._validate(response, VerificationArtifactDTO, "uploaded artifact")
        if artifact.id != artifact_id or artifact.verification_run_id != run_id:
            raise ORAtlasArtifactIntegrityError("uploaded artifact identity mismatch")
        if (
            artifact.sha256 != sha256_bytes(content)
            or artifact.byte_length != len(content)
            or artifact.media_type != media_type
        ):
            raise ORAtlasArtifactIntegrityError("uploaded artifact metadata mismatch")
        return artifact

    def complete_artifact(self, run_id: str, artifact_id: str) -> VerificationArtifactDTO:
        path = self._run_path(run_id, "/artifacts/complete")
        response = self._request(
            "POST",
            path,
            run_id=run_id,
            json_body={"artifactId": artifact_id},
            conflict="idempotency",
            retry_transient=True,
        )
        artifact = self._validate(response, VerificationArtifactDTO, "completed artifact")
        if artifact.id != artifact_id or artifact.status != "completed":
            raise ORAtlasArtifactIntegrityError("artifact completion response mismatch")
        return artifact

    def download_completed_artifact(
        self,
        expected: VerificationArtifactDTO,
        *,
        run_id: str | None = None,
    ) -> bytes:
        if expected.status != "completed":
            raise ORAtlasArtifactIntegrityError("verification artifact is not completed")
        path = f"/api/verification-artifacts/{quote(expected.id, safe='')}/content"
        request_run_id = run_id if expected.visibility == "private" else None
        response = self._request("GET", path, run_id=request_run_id, retry_transient=True)
        content = response.content
        if response.headers.get("X-ORAtlas-SHA256") != expected.sha256:
            raise ORAtlasArtifactIntegrityError("verification artifact digest header mismatch")
        if response.headers.get("Content-Type", "").strip() != expected.media_type:
            raise ORAtlasArtifactIntegrityError("verification artifact media type mismatch")
        length = response.headers.get("Content-Length")
        if length is None or not length.isdigit() or int(length) != expected.byte_length:
            raise ORAtlasArtifactIntegrityError("verification artifact length header mismatch")
        if len(content) != expected.byte_length or sha256_bytes(content) != expected.sha256:
            raise ORAtlasArtifactIntegrityError("verification artifact byte integrity mismatch")
        return content

    def submit_finding(self, run_id: str, finding: FindingSubmissionDTO) -> VerificationFindingDTO:
        path = self._run_path(run_id, "/findings")
        response = self._request(
            "POST",
            path,
            run_id=run_id,
            json_body=dump_request(finding),
            conflict="idempotency",
            retry_transient=True,
        )
        submitted = self._validate(response, VerificationFindingDTO, "verification finding")
        if submitted.verification_run_id != run_id or submitted.finding_key != finding.finding_key:
            raise TransportError("submitted finding identity mismatch")
        return submitted

    def list_findings(self, run_id: str) -> FindingsListDTO:
        path = self._run_path(run_id, "/findings")
        response = self._request("GET", path, retry_transient=True)
        return self._validate(response, FindingsListDTO, "verification findings")

    def transition_run(
        self,
        run_id: str,
        status: Literal["running", "completed", "failed"],
        reason: str | None = None,
    ) -> VerificationRunDTO:
        dto = TransitionDTO(status=status, reason=reason)
        path = self._run_path(run_id, "/transition")
        response = self._request(
            "POST",
            path,
            run_id=run_id,
            json_body=dump_request(dto),
            retry_transient=True,
        )
        run = self._validate(response, VerificationRunDTO, "verification run transition")
        if run.id != run_id or run.status != status:
            raise TransportError("ORAtlas transition response mismatch")
        return run

    def get_public_run(self, run_id: str) -> PublicVerificationRunDTO:
        path = self._run_path(run_id)
        response = self._request("GET", path, retry_transient=True)
        return self._validate(response, PublicVerificationRunDTO, "public verification run")

    def list_publication_version_verifications(
        self, publication_version_id: str
    ) -> PublicationVerificationProjectionDTO:
        encoded = quote(publication_version_id, safe="")
        path = f"/api/publication-versions/{encoded}/verifications"
        response = self._request("GET", path, retry_transient=True)
        return self._validate(
            response,
            PublicationVerificationProjectionDTO,
            "publication verification projection",
        )
