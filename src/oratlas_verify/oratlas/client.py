"""Synchronous ORAtlas API client with no scientific behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from oratlas_verify.core.contracts import (
    ProtocolRef,
    VerificationArtifact,
    VerificationFinding,
    VerificationRequest,
)
from oratlas_verify.core.errors import TransportError
from oratlas_verify.core.provenance import verify_downloaded_artifact
from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.dtos import (
    ArtifactSubmissionDTO,
    CreateVerificationRunDTO,
    FindingSubmissionDTO,
    ProtocolDTO,
    TransitionDTO,
    VerificationRunDTO,
)


class ORAtlasClient:
    """Owns all current endpoint paths and transport casing assumptions."""

    def __init__(
        self, config: ORAtlasConfig, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.config = config
        self._client = httpx.Client(
            base_url=f"{config.base_url.rstrip('/')}/",
            headers={**config.authorization_header(), "Accept": "application/json"},
            timeout=config.timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self) -> ORAtlasClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self, method: str, path: str, *, json_body: object | None = None
    ) -> httpx.Response:
        try:
            if json_body is None:
                response = self._client.request(method, path)
            else:
                response = self._client.request(method, path, json=json_body)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            # Do not surface bodies, which may contain unpublished content.
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            suffix = f" (HTTP {status})" if status is not None else ""
            raise TransportError(f"ORAtlas request failed: {method} {path}{suffix}") from exc

    def create_verification_run(
        self,
        publication_id: str,
        publication_version_id: str,
        protocols: tuple[ProtocolRef, ...],
    ) -> str:
        dto = CreateVerificationRunDTO(
            publicationId=publication_id,
            publicationVersionId=publication_version_id,
            protocols=tuple(
                ProtocolDTO(name=item.name, version=item.version) for item in protocols
            ),
        )
        response = self._request(
            "POST",
            "api/verifications/runs",
            json_body=dto.model_dump(mode="json", by_alias=True),
        )
        run_id = response.json().get("runId")
        if not isinstance(run_id, str) or not run_id:
            raise TransportError("ORAtlas create-run response omitted runId")
        return run_id

    def retrieve_frozen_input(self, run_id: str) -> VerificationRequest:
        path = f"api/verifications/runs/{quote(run_id, safe='')}/input"
        response = self._request("GET", path)
        try:
            return VerificationRunDTO.model_validate(response.json()).to_domain()
        except (ValidationError, ValueError, TypeError) as exc:
            raise TransportError("ORAtlas returned an invalid frozen verification input") from exc

    def download_artifact(
        self,
        run_id: str,
        artifact_id: str,
        destination: Path,
        *,
        expected_sha256: str,
        expected_length: int,
    ) -> None:
        path = (
            f"api/verifications/runs/{quote(run_id, safe='')}/artifacts/"
            f"{quote(artifact_id, safe='')}/content"
        )
        response = self._request("GET", path)
        destination.write_bytes(response.content)
        try:
            verify_downloaded_artifact(destination, expected_sha256, expected_length)
        except ValueError:
            destination.unlink(missing_ok=True)
            raise

    def submit_findings(self, run_id: str, findings: tuple[VerificationFinding, ...]) -> None:
        dto = FindingSubmissionDTO.from_domain(findings)
        self._request(
            "POST",
            f"api/verifications/runs/{quote(run_id, safe='')}/findings",
            json_body=dto.model_dump(mode="json", by_alias=True),
        )

    def submit_artifact_metadata(
        self, run_id: str, artifacts: tuple[VerificationArtifact, ...]
    ) -> None:
        dto = ArtifactSubmissionDTO.from_domain(artifacts)
        self._request(
            "POST",
            f"api/verifications/runs/{quote(run_id, safe='')}/artifacts",
            json_body=dto.model_dump(mode="json", by_alias=True),
        )

    def transition_run(
        self,
        run_id: str,
        state: Literal["completed", "failed"],
        reason: str | None = None,
    ) -> None:
        dto = TransitionDTO(state=state, reason=reason)
        self._request(
            "POST",
            f"api/verifications/runs/{quote(run_id, safe='')}/transition",
            json_body=dto.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
