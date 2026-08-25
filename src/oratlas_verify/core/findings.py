"""Finding construction with stable identifiers and integrity hashes."""

from __future__ import annotations

from datetime import UTC, datetime

from oratlas_verify.core.contracts import (
    FindingStatus,
    JsonValue,
    ProtocolRef,
    ReproductionKind,
    VerificationFinding,
)
from oratlas_verify.core.json import sha256_json


def make_finding(
    *,
    protocol: ProtocolRef,
    input_sha256: str,
    status: FindingStatus,
    title: str,
    rationale: str,
    details: dict[str, JsonValue],
    reproduction_kind: ReproductionKind = ReproductionKind.NOT_APPLICABLE,
    evidence_ids: tuple[str, ...] = (),
    artifact_ids: tuple[str, ...] = (),
    created_at: datetime | None = None,
) -> VerificationFinding:
    identity = sha256_json(
        {
            "protocol": protocol,
            "input_sha256": input_sha256,
            "status": status,
            "details": details,
            "evidence_ids": evidence_ids,
        }
    )
    finding = VerificationFinding(
        finding_id=f"finding:{identity}",
        protocol=protocol,
        status=status,
        title=title,
        rationale=rationale,
        reproduction_kind=reproduction_kind,
        evidence_ids=evidence_ids,
        details=details,
        artifact_ids=artifact_ids,
        created_at=created_at or datetime.now(UTC),
    )
    return finding.model_copy(update={"content_sha256": finding.computed_content_sha256})
