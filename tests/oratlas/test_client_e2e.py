from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from oratlas_verify.core.artifacts import LocalArtifactStore
from oratlas_verify.core.errors import TransportError
from oratlas_verify.core.json import sha256_bytes, sha256_json
from oratlas_verify.core.orchestration import VerificationOrchestrator
from oratlas_verify.core.registry import build_default_registry
from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.client import ORAtlasClient


def frozen_response(run_id: str = "run-1") -> dict:
    payload = {
        "test_type": "t",
        "statistic": 3.12,
        "degrees_of_freedom": [38],
        "reported_p": 0.0034,
        "sidedness": "two-sided",
    }
    return {
        "runId": run_id,
        "correlationId": "correlation-1",
        "requestedAt": "2026-08-25T08:00:00Z",
        "protocols": [{"name": "reported-statistic-consistency", "version": "0.1.0"}],
        "frozenInput": {
            "publicationId": "publication-1",
            "publicationVersionId": "version-1",
            "payload": payload,
            "evidenceIds": ["evidence-1"],
            "artifactReferences": [],
            "executionPassport": None,
            "inputSha256": sha256_json(payload),
        },
    }


def test_mocked_oratlas_run_end_to_end(tmp_path: Path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=frozen_response())
        return httpx.Response(204)

    client = ORAtlasClient(
        ORAtlasConfig("https://oratlas.test", "secret-token"),
        transport=httpx.MockTransport(handler),
    )
    orchestrator = VerificationOrchestrator(
        build_default_registry(), LocalArtifactStore(tmp_path / "artifacts")
    )
    response = orchestrator.run_remote("run-1", client)
    client.close()

    assert response.findings[0].status.value == "verified"
    assert [request.url.path for request in requests] == [
        "/api/verifications/runs/run-1/input",
        "/api/verifications/runs/run-1/findings",
        "/api/verifications/runs/run-1/artifacts",
        "/api/verifications/runs/run-1/transition",
    ]
    assert all(request.headers["authorization"] == "Bearer secret-token" for request in requests)
    finding_body = json.loads(requests[1].content)
    assert finding_body["findings"][0]["status"] == "verified"
    assert len(list((tmp_path / "artifacts").glob("*.json"))) == 1


def test_remote_hash_mismatch_fails_and_transitions():
    requests: list[httpx.Request] = []
    response = frozen_response()
    response["frozenInput"]["inputSha256"] = "0" * 64

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=response)
        return httpx.Response(204)

    client = ORAtlasClient(
        ORAtlasConfig("https://oratlas.test", "secret-token"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TransportError):
        VerificationOrchestrator(build_default_registry()).run_remote("run-1", client)
    client.close()
    assert requests[-1].url.path.endswith("/transition")
    assert json.loads(requests[-1].content)["state"] == "failed"


def test_downloaded_artifact_is_hash_checked(tmp_path: Path):
    content = b"immutable content"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    destination = tmp_path / "artifact.bin"
    with ORAtlasClient(
        ORAtlasConfig("https://oratlas.test", "token"), transport=httpx.MockTransport(handler)
    ) as client:
        client.download_artifact(
            "run",
            "artifact",
            destination,
            expected_sha256=sha256_bytes(content),
            expected_length=len(content),
        )
    assert destination.read_bytes() == content


def test_download_hash_mismatch_removes_file(tmp_path: Path):
    destination = tmp_path / "artifact.bin"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"bad")

    with (
        ORAtlasClient(
            ORAtlasConfig("https://oratlas.test", "token"), transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(ValueError),
    ):
        client.download_artifact(
            "run",
            "artifact",
            destination,
            expected_sha256="0" * 64,
            expected_length=3,
        )
    assert not destination.exists()


def test_token_not_in_config_repr():
    config = ORAtlasConfig("https://oratlas.test", "never-print-this")
    assert "never-print-this" not in repr(config)
