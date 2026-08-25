from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from oratlas_verify.core.contracts import FindingStatus, ProtocolRef, VerificationFinding
from oratlas_verify.core.provenance import create_json_artifact


def test_canonical_artifact_hash_and_metadata(tmp_path):
    created = datetime(2026, 1, 2, tzinfo=UTC)
    artifact = create_json_artifact(
        {"b": 2, "a": 1},
        protocol=ProtocolRef(name="test", version="0.1.0"),
        input_hashes=("a" * 64,),
        finding_ids=("finding:1",),
        created_at=created,
    )
    assert artifact.content == b'{"a":1,"b":2}'
    assert (
        artifact.metadata.sha256
        == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )
    assert artifact.metadata.byte_length == len(artifact.content)
    assert artifact.metadata.created_at == created


def test_contract_models_are_frozen():
    protocol = ProtocolRef(name="x", version="0.1.0")
    with pytest.raises(ValidationError):
        protocol.name = "y"


def test_finding_nested_json_is_deeply_immutable():
    finding = VerificationFinding(
        finding_id="f",
        protocol=ProtocolRef(name="x", version="0.1.0"),
        status=FindingStatus.VERIFIED,
        title="x",
        rationale="x",
        details={"nested": {"values": [1, 2]}},
    )
    with pytest.raises(TypeError):
        finding.details["new"] = True
    with pytest.raises(TypeError):
        finding.details["nested"]["values"].append(3)
    assert finding.model_dump(mode="json")["details"] == {"nested": {"values": [1, 2]}}
