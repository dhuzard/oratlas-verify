from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from oratlas_verify.core.contracts import ProtocolRef, VerificationInput
from oratlas_verify.oratlas.dtos import EvidenceReferenceDTO, FindingSubmissionDTO
from oratlas_verify.oratlas.mapping import map_finding
from oratlas_verify.verifiers.analysis.comparison import verify_analysis_result
from oratlas_verify.verifiers.figures.structured import verify_structured_figure


def test_figure_mapping_preserves_regeneration_and_structured_comparison() -> None:
    protocol = ProtocolRef(name="figure-structured-comparison", version="0.1.0")
    payload = {
        "original": {"series": [{"name": "a", "x": [1], "y": [2]}]},
        "regenerated": {"series": [{"name": "a", "x": [1], "y": [2]}]},
        "comparison_kind": "regeneration",
        "absolute_tolerance": 0,
        "relative_tolerance": 0,
    }
    finding = verify_structured_figure(
        VerificationInput(publication_id="p", publication_version_id="v", payload=payload),
        protocol,
    )[0]
    mapped = map_finding(
        finding,
        payload,
        evidence_refs=(EvidenceReferenceDTO(type="publication-content-document", id="doc"),),
        artifact_ids=("artifact",),
    )
    assert mapped.finding_type == "figure-structured-comparison"
    assert mapped.observed["method"] == "regeneration"
    assert mapped.observed["visualSimilarityUsed"] is False


def test_analysis_mapping_preserves_independent_reproduction() -> None:
    protocol = ProtocolRef(name="analysis-result-comparison", version="0.1.0")
    payload = {
        "expected": [1, 2],
        "reproduced": [1, 2],
        "comparison_kind": "independent-reproduction",
        "absolute_tolerance": 0,
        "relative_tolerance": 0,
    }
    finding = verify_analysis_result(
        VerificationInput(publication_id="p", publication_version_id="v", payload=payload),
        protocol,
    )[0]
    mapped = map_finding(
        finding,
        payload,
        evidence_refs=(),
        artifact_ids=("artifact",),
    )
    assert mapped.finding_type == "analysis-result-comparison"
    assert mapped.observed["method"] == "independent-reproduction"
    assert "score" not in mapped.observed


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_finding_structured_fields_reject_non_finite_json(value: float) -> None:
    with pytest.raises(ValidationError):
        FindingSubmissionDTO(
            findingKey="finite-json",
            findingType="statistic-consistency",
            status="verified",
            impact="informational",
            statement="Finite only.",
            rationale="ORAtlas requires plain finite JSON.",
            observed={"value": value},
        )
