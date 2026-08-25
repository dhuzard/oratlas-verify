from __future__ import annotations

import json
import logging
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from oratlas_verify.core.errors import (
    ORAtlasArtifactIntegrityError,
    ORAtlasIdempotencyConflict,
    ORAtlasInputIntegrityError,
    ORAtlasLeaseConflict,
    ORAtlasProtocolMismatch,
)
from oratlas_verify.core.json import sha256_bytes, sha256_json
from oratlas_verify.core.registry import build_default_registry
from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.client import ORAtlasClient
from oratlas_verify.oratlas.dtos import (
    ArtifactPrepareDTO,
    EvidenceReferenceDTO,
    FindingSubmissionDTO,
    SourceArtifactDTO,
)
from oratlas_verify.oratlas.worker import (
    STATISTICS_REPORT_SCHEMA,
    ORAtlasVerificationWorker,
)

NOW = "2026-08-25T12:00:00Z"
LEASE_EXPIRY = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
LEASE = "oratlas_lease_test-only-opaque-secret"
TOKEN = "oratlas_verify_test-token"
PROTOCOL_ID = "reported-statistic-consistency-0-1-0"
PUBLICATION_ID = "synthetic-publication"
VERSION_ID = "synthetic-version"
DOCUMENT_ID = "publication-content:results"


def _protocol(
    *, series: str = "reported-statistic-consistency", version: str = "0.1.0"
) -> dict[str, Any]:
    definition: dict[str, Any] = {}
    return {
        "id": PROTOCOL_ID,
        "authorityVerifierId": "verifier-1",
        "authority": {"id": "verifier-1", "slug": "verify", "name": "Verify"},
        "seriesKey": series,
        "protocolVersion": version,
        "title": "Reported statistic consistency",
        "description": "External deterministic protocol.",
        "verificationType": series,
        "executionMode": "external-execution",
        "supportedSubjectTypes": ["publication-version"],
        "definition": definition,
        "definitionSha256": sha256_json(definition),
        "status": "active",
        "supersedesProtocolId": None,
        "createdAt": NOW,
        "href": f"/api/verification-protocols/{PROTOCOL_ID}",
    }


def _frozen_input(
    text: str,
    *,
    profile: str = "blinded-scientific",
    outer_sha: str | None = None,
    schema_version: str | None = None,
) -> dict[str, Any]:
    document = {
        "id": DOCUMENT_ID,
        "title": "Synthetic result",
        "role": "results",
        "sourcePath": "article.md",
        "publishedUrl": "https://example.test/article/",
        "representation": "published-structured-text",
        "text": text,
        "sha256": sha256_bytes(text.encode()),
        "sourceArtifactIdentitySha256": sha256_bytes(b"slot"),
        "sourceArtifactSha256": sha256_bytes(text.encode()),
    }
    packet: dict[str, Any] = {
        "schemaVersion": "1.3.0",
        "publication": {"id": PUBLICATION_ID},
        "version": {"id": VERSION_ID},
        "captures": [],
        "content": [document],
        "contributors": [{"id": "contributor"}],
        "occurrences": [],
        "productionProvenance": [{"id": "production"}],
        "relations": [],
        "challenges": [],
        "completeness": {"content": "complete"},
        "links": {"self": "/packet"},
    }
    if profile == "blinded-scientific":
        packet["schemaVersion"] = "verification-publication-input/1.0.0"
        packet["sourcePacketSchemaVersion"] = "1.3.0"
        packet["contributors"] = []
        packet["productionProvenance"] = []
    packet["sha256"] = sha256_json(packet)
    resolved_schema = schema_version or str(packet["schemaVersion"])
    return {
        "verificationRunId": "run-1",
        "schemaVersion": resolved_schema,
        "sha256": outer_sha or sha256_json(packet),
        "profile": profile,
        "profileVersion": "1.0.0",
        "capturedAt": NOW,
        "input": packet,
        "sourceArtifacts": [],
    }


def _run(input_value: dict[str, Any], *, status: str) -> dict[str, Any]:
    return {
        "id": "run-1",
        "verificationProtocolId": PROTOCOL_ID,
        "subject": {"type": "publication-version", "publicationVersionId": VERSION_ID},
        "claimedVerifierId": None if status == "requested" else "verifier-1",
        "status": status,
        "input": {
            "profile": input_value["profile"],
            "profileVersion": input_value["profileVersion"],
            "schemaVersion": input_value["schemaVersion"],
            "sha256": input_value["sha256"],
            "capturedAt": input_value["capturedAt"],
        },
        "requestedAt": NOW,
        "claimedAt": None if status == "requested" else NOW,
        "startedAt": NOW if status in {"running", "completed", "failed"} else None,
        "completedAt": NOW if status in {"completed", "failed"} else None,
        "terminalReason": None,
        "provenance": {
            "agentRunId": None,
            "executionPassportId": None,
            "replicationBriefId": None,
        },
        "replayed": False,
        "links": {
            "self": "/api/verification-runs/run-1",
            "claim": "/api/verification-runs/run-1/claim",
            "input": "/api/verification-runs/run-1/input",
            "findings": "/api/verification-runs/run-1/findings",
            "transition": "/api/verification-runs/run-1/transition",
        },
    }


class FakeORAtlas:
    def __init__(
        self,
        text: str,
        *,
        profile: str = "blinded-scientific",
        outer_sha: str | None = None,
        schema_version: str | None = None,
        protocol_series: str = "reported-statistic-consistency",
    ) -> None:
        self.input = _frozen_input(
            text, profile=profile, outer_sha=outer_sha, schema_version=schema_version
        )
        self.protocol = _protocol(series=protocol_series)
        self.requests: list[httpx.Request] = []
        self.status = "requested"
        self.artifact_bytes = b""
        self.artifact_metadata: dict[str, Any] | None = None
        self.findings: list[dict[str, Any]] = []

    def _artifact(self, status: str) -> dict[str, Any]:
        assert self.artifact_metadata is not None
        return {
            "id": "artifact-1",
            "verificationRunId": "run-1",
            **self.artifact_metadata,
            "status": status,
            "provenance": {"leaseGeneration": 1},
            "createdAt": NOW,
            "contentHref": (
                "/api/verification-artifacts/artifact-1/content" if status == "completed" else None
            ),
        }

    def _public_finding(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(body)
        payload.setdefault("reported", None)
        payload.setdefault("observed", None)
        payload.setdefault("tolerance", None)
        payload.setdefault("evidenceRefs", [])
        payload.setdefault("artifactRefs", [])
        return {
            "id": f"finding-{len(self.findings) + 1}",
            "verificationRunId": "run-1",
            "submittedByVerifierId": "verifier-1",
            **payload,
            "payloadSha256": sha256_json(body),
            "supersedesFindingId": body.get("supersedesFindingId"),
            "createdAt": NOW,
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/verification-runs/run-1/claim":
            assert request.headers["authorization"] == f"Bearer {TOKEN}"
            assert json.loads(request.content) == {"leaseSeconds": 300}
            self.status = "claimed"
            return httpx.Response(
                200,
                json={
                    **_run(self.input, status="claimed"),
                    "leaseToken": LEASE,
                    "leaseExpiresAt": LEASE_EXPIRY,
                },
            )
        if path == f"/api/verification-protocols/{PROTOCOL_ID}":
            return httpx.Response(200, json=self.protocol)
        if path == "/api/verification-runs/run-1/input":
            return httpx.Response(200, json=self.input)
        if path == "/api/verification-runs/run-1/transition":
            body = json.loads(request.content)
            self.status = body["status"]
            return httpx.Response(200, json=_run(self.input, status=self.status))
        if path == "/api/verification-runs/run-1/artifacts/prepare":
            self.artifact_metadata = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "artifactId": "artifact-1",
                    "status": "prepared",
                    "upload": {
                        "type": "oratlas-direct-binary-v1",
                        "method": "PUT",
                        "href": "/api/verification-artifacts/artifact-1/content",
                        "headers": {"content-type": "application/json"},
                    },
                    "expiresAt": LEASE_EXPIRY,
                    "replayed": False,
                },
            )
        if path == "/api/verification-artifacts/artifact-1/content":
            self.artifact_bytes = request.content
            assert request.headers["content-type"] == "application/json"
            assert request.headers["content-length"] == str(len(request.content))
            assert sha256_bytes(request.content) == self.artifact_metadata["sha256"]
            return httpx.Response(200, json=self._artifact("uploaded"))
        if path == "/api/verification-runs/run-1/artifacts/complete":
            assert json.loads(request.content) == {"artifactId": "artifact-1"}
            return httpx.Response(200, json=self._artifact("completed"))
        if path == "/api/verification-runs/run-1/findings" and request.method == "POST":
            finding = self._public_finding(json.loads(request.content))
            self.findings.append(finding)
            return httpx.Response(201, json=finding)
        if path == "/api/verification-runs/run-1":
            return httpx.Response(
                200,
                json={
                    **_run(self.input, status=self.status),
                    "protocol": self.protocol,
                    "verifier": {"id": "verifier-1", "slug": "verify", "name": "Verify"},
                    "artifacts": [self._artifact("completed")],
                    "findings": self.findings,
                    "lifecycle": [],
                    "limitations": ["Protocol-scoped evidence."],
                },
            )
        if path == f"/api/publication-versions/{VERSION_ID}/verifications":
            projected = {
                **_run(self.input, status=self.status),
                "protocol": {"seriesKey": self.protocol["seriesKey"], "version": "0.1.0"},
                "verifier": {"id": "verifier-1", "slug": "verify", "name": "Verify"},
                "findings": self.findings,
            }
            return httpx.Response(
                200,
                json={
                    "schemaVersion": "1.0.0",
                    "publicationVersionId": VERSION_ID,
                    "summary": {},
                    "runs": [projected],
                },
            )
        return httpx.Response(404)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> ORAtlasClient:
    return ORAtlasClient(
        ORAtlasConfig("https://oratlas.test", TOKEN),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.parametrize(
    ("text", "expected_status"),
    [
        ("Results: t(38) = 3.12, p = 0.0034, two-sided.", "verified"),
        ("Results: t(38) = 3.12, p = 0.2, two-sided.", "discrepancy"),
        ("Results: t(38) = 3.12, p = 0.0034.", "unverifiable"),
    ],
)
def test_real_http_scientific_round_trips(text: str, expected_status: str) -> None:
    server = FakeORAtlas(text)
    with _client(server) as client:
        result = ORAtlasVerificationWorker(build_default_registry()).run("run-1", client)

    assert result.findings[0].status.value == expected_status
    assert server.status == "completed"
    assert json.loads(server.artifact_bytes)["schemaVersion"] == STATISTICS_REPORT_SCHEMA
    assert sha256_bytes(server.artifact_bytes) == result.artifact_sha256
    assert result.findings[0].artifact_refs == ("artifact-1",)
    assert result.findings[0].evidence_refs == (
        EvidenceReferenceDTO(type="publication-content-document", id=DOCUMENT_ID),
    )
    paths = [request.url.path for request in server.requests]
    assert paths == [
        "/api/verification-runs/run-1/claim",
        "/api/verification-runs/run-1/input",
        f"/api/verification-protocols/{PROTOCOL_ID}",
        "/api/verification-runs/run-1/transition",
        "/api/verification-runs/run-1/artifacts/prepare",
        "/api/verification-artifacts/artifact-1/content",
        "/api/verification-runs/run-1/artifacts/complete",
        "/api/verification-runs/run-1/findings",
        "/api/verification-runs/run-1/transition",
        "/api/verification-runs/run-1",
        f"/api/publication-versions/{VERSION_ID}/verifications",
    ]
    leased_paths = paths[1:2] + paths[3:9]
    for request in server.requests:
        if request.url.path in leased_paths:
            assert request.headers["x-oratlas-verification-lease"] == LEASE
    upload_request = server.requests[5]
    assert upload_request.content.startswith(b"{")
    assert not upload_request.headers["content-type"].startswith("multipart/")
    assert "scipy" in json.loads(server.artifact_bytes)["software"]


def test_full_publication_packet_is_supported() -> None:
    server = FakeORAtlas("Results: t(38) = 3.12, p = 0.0034, two-sided.", profile="full")
    with _client(server) as client:
        result = ORAtlasVerificationWorker(build_default_registry()).run("run-1", client)
    assert result.input_profile == "full"
    assert result.findings[0].status.value == "verified"


def test_claim_conflict_is_not_retried() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(409)

    with _client(handler) as client, pytest.raises(ORAtlasLeaseConflict):
        client.claim_run("run-1")
    assert len(requests) == 1


def test_input_hash_mismatch_fails_run() -> None:
    server = FakeORAtlas("Results: t(38) = 3.12, p = 0.0034, two-sided.", outer_sha="0" * 64)
    with _client(server) as client, pytest.raises(ORAtlasInputIntegrityError):
        ORAtlasVerificationWorker(build_default_registry()).run("run-1", client)
    assert server.status == "failed"


def test_unsupported_input_schema_fails_closed() -> None:
    server = FakeORAtlas(
        "Results: t(38) = 3.12, p = 0.0034, two-sided.",
        schema_version="verification-publication-input/9.0.0",
    )
    server.input["sha256"] = sha256_json(server.input["input"])
    with _client(server) as client, pytest.raises(ORAtlasInputIntegrityError):
        ORAtlasVerificationWorker(build_default_registry()).run("run-1", client)
    assert server.status == "failed"


def test_unknown_protocol_fails_closed() -> None:
    server = FakeORAtlas(
        "Results: t(38) = 3.12, p = 0.0034, two-sided.", protocol_series="unknown-protocol"
    )
    with _client(server) as client, pytest.raises(ORAtlasProtocolMismatch):
        ORAtlasVerificationWorker(build_default_registry()).run("run-1", client)
    assert server.status == "failed"


@pytest.mark.parametrize(
    ("changed_header", "value"),
    [
        ("X-ORAtlas-SHA256", "0" * 64),
        ("Content-Type", "application/octet-stream"),
        ("Content-Length", "2"),
    ],
)
def test_source_artifact_integrity_mismatch_fails(changed_header: str, value: str) -> None:
    content = b"source"
    expected = SourceArtifactDTO(
        id="source-1",
        mediaType="text/plain",
        sha256=sha256_bytes(content),
        byteLength=len(content),
        available=True,
        href="/api/verification-runs/run-1/source-artifacts/source-1",
    )
    frozen = _frozen_input("Results: t(38) = 3.12, p = 0.0034, two-sided.")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/claim"):
            return httpx.Response(
                200,
                json={
                    **_run(frozen, status="claimed"),
                    "leaseToken": LEASE,
                    "leaseExpiresAt": LEASE_EXPIRY,
                },
            )
        headers = {
            "X-ORAtlas-SHA256": expected.sha256,
            "Content-Type": expected.media_type,
            "Content-Length": str(expected.byte_length),
        }
        headers[changed_header] = value
        return httpx.Response(200, content=content, headers=headers)

    with _client(handler) as client, pytest.raises(ORAtlasArtifactIntegrityError):
        client.claim_run("run-1")
        client.download_source_artifact("run-1", expected)


def test_source_artifact_exact_bytes_are_returned_but_never_executed() -> None:
    content = b"import os; os.system('never')"
    expected = SourceArtifactDTO(
        id="source-1",
        mediaType="text/plain",
        sha256=sha256_bytes(content),
        byteLength=len(content),
        available=True,
        href="/api/verification-runs/run-1/source-artifacts/source-1",
    )
    frozen = _frozen_input("Results: t(38) = 3.12, p = 0.0034, two-sided.")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/claim"):
            return httpx.Response(
                200,
                json={
                    **_run(frozen, status="claimed"),
                    "leaseToken": LEASE,
                    "leaseExpiresAt": LEASE_EXPIRY,
                },
            )
        return httpx.Response(
            200,
            content=content,
            headers={
                "X-ORAtlas-SHA256": expected.sha256,
                "Content-Type": expected.media_type,
                "Content-Length": str(expected.byte_length),
            },
        )

    with _client(handler) as client:
        client.claim_run("run-1")
        assert client.download_source_artifact("run-1", expected) == content


def test_source_artifact_actual_digest_mismatch_fails() -> None:
    expected_content = b"expected"
    received_content = b"tampered"
    expected = SourceArtifactDTO(
        id="source-1",
        mediaType="text/plain",
        sha256=sha256_bytes(expected_content),
        byteLength=len(received_content),
        available=True,
        href="/api/verification-runs/run-1/source-artifacts/source-1",
    )
    frozen = _frozen_input("Results: t(38) = 3.12, p = 0.0034, two-sided.")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/claim"):
            return httpx.Response(
                200,
                json={
                    **_run(frozen, status="claimed"),
                    "leaseToken": LEASE,
                    "leaseExpiresAt": LEASE_EXPIRY,
                },
            )
        return httpx.Response(
            200,
            content=received_content,
            headers={
                "X-ORAtlas-SHA256": expected.sha256,
                "Content-Type": expected.media_type,
                "Content-Length": str(expected.byte_length),
            },
        )

    with _client(handler) as client, pytest.raises(ORAtlasArtifactIntegrityError):
        client.claim_run("run-1")
        client.download_source_artifact("run-1", expected)


def test_finding_exact_replay_and_conflicting_replay() -> None:
    frozen = _frozen_input("Results: t(38) = 3.12, p = 0.0034, two-sided.")
    calls = 0
    finding = FindingSubmissionDTO(
        findingKey="stat-t-stable",
        findingType="statistic-consistency",
        status="verified",
        impact="informational",
        statement="Verified.",
        rationale="Exact recomputation.",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("/claim"):
            return httpx.Response(
                200,
                json={
                    **_run(frozen, status="claimed"),
                    "leaseToken": LEASE,
                    "leaseExpiresAt": LEASE_EXPIRY,
                },
            )
        calls += 1
        if calls == 1:
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "finding-1",
                    "verificationRunId": "run-1",
                    "submittedByVerifierId": "verifier-1",
                    **body,
                    "reported": None,
                    "observed": None,
                    "tolerance": None,
                    "evidenceRefs": [],
                    "artifactRefs": [],
                    "payloadSha256": sha256_json(body),
                    "supersedesFindingId": None,
                    "createdAt": NOW,
                    "replayed": True,
                },
            )
        return httpx.Response(409)

    with _client(handler) as client:
        client.claim_run("run-1")
        assert client.submit_finding("run-1", finding).replayed
        with pytest.raises(ORAtlasIdempotencyConflict):
            client.submit_finding("run-1", finding.model_copy(update={"statement": "Changed."}))


def test_artifact_prepare_mapping_and_conflict() -> None:
    frozen = _frozen_input("Results: t(38) = 3.12, p = 0.0034, two-sided.")
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/claim"):
            return httpx.Response(
                200,
                json={
                    **_run(frozen, status="claimed"),
                    "leaseToken": LEASE,
                    "leaseExpiresAt": LEASE_EXPIRY,
                },
            )
        captured.update(json.loads(request.content))
        return httpx.Response(409)

    prepared = ArtifactPrepareDTO(
        artifactKey="statistics-report-stable",
        kind="statistics-report",
        mediaType="application/json",
        sha256="0" * 64,
        byteLength=10,
        visibility="public",
    )
    with _client(handler) as client:
        client.claim_run("run-1")
        with pytest.raises(ORAtlasIdempotencyConflict):
            client.prepare_artifact("run-1", prepared)
    assert captured == prepared.model_dump(mode="json", by_alias=True)


def test_secrets_never_appear_in_repr_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    config = ORAtlasConfig("https://oratlas.test", TOKEN)
    caplog.set_level(logging.DEBUG)
    server = FakeORAtlas("Results: t(38) = 3.12, p = 0.0034, two-sided.")
    with _client(server) as client:
        claim = client.claim_run("run-1")
        logging.getLogger("test").info("claim complete")
    rendered = repr(config) + repr(claim) + caplog.text
    assert TOKEN not in rendered
    assert LEASE not in rendered
