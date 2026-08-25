"""Artifact creation and runtime version provenance."""

from __future__ import annotations

import importlib.metadata
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from oratlas_verify.core.contracts import ProtocolRef, VerificationArtifact
from oratlas_verify.core.json import canonical_json_bytes, sha256_bytes

SCIENTIFIC_PACKAGES = ("numpy", "scipy", "pandas", "statsmodels", "matplotlib")


def tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in SCIENTIFIC_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def runtime_identity() -> tuple[str, str]:
    return platform.python_version(), platform.platform()


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    metadata: VerificationArtifact
    content: bytes


def create_json_artifact(
    value: object,
    *,
    protocol: ProtocolRef,
    input_hashes: tuple[str, ...],
    finding_ids: tuple[str, ...] = (),
    filename: str | None = None,
    created_at: datetime | None = None,
) -> GeneratedArtifact:
    content = canonical_json_bytes(value)
    metadata = VerificationArtifact(
        artifact_id=str(uuid4()),
        sha256=sha256_bytes(content),
        media_type="application/json",
        byte_length=len(content),
        generator_protocol=protocol,
        input_hashes=input_hashes,
        tool_versions=tool_versions(),
        created_at=created_at or datetime.now(UTC),
        finding_ids=finding_ids,
        filename=filename,
    )
    return GeneratedArtifact(metadata=metadata, content=content)


def verify_downloaded_artifact(path: Path, expected_sha256: str, expected_length: int) -> None:
    content = path.read_bytes()
    if len(content) != expected_length:
        raise ValueError("artifact byte length does not match immutable reference")
    if sha256_bytes(content) != expected_sha256:
        raise ValueError("artifact SHA-256 does not match immutable reference")
