"""Map local scientific findings into the generic ORAtlas finding contract."""

from __future__ import annotations

from typing import Literal

from oratlas_verify.core.contracts import (
    FindingStatus,
    JsonValue,
    VerificationFinding,
)
from oratlas_verify.core.json import sha256_json
from oratlas_verify.oratlas.dtos import EvidenceReferenceDTO, FindingSubmissionDTO

STATISTICS_IMPACT_RULE_VERSION = "oratlas-verify-statistics-impact/0.1.0"
Impact = Literal["informational", "minor", "major", "critical"]


def _statistics_impact(
    finding: VerificationFinding, scientific_input: dict[str, JsonValue]
) -> Impact:
    """Version 0.1.0: mismatch impact follows significance-decision consequences."""
    if finding.status is FindingStatus.VERIFIED:
        return "informational"
    if finding.status in {FindingStatus.UNVERIFIABLE, FindingStatus.NOT_APPLICABLE}:
        return "minor"
    if finding.status is FindingStatus.DISCREPANCY:
        reported = scientific_input.get("reported_p")
        observed = finding.details.get("recomputed_p")
        if isinstance(reported, int | float) and isinstance(observed, int | float):
            return "major" if (reported <= 0.05) != (observed <= 0.05) else "minor"
        return "minor"
    return "major"


def _statistic_reported(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "testType": value.get("test_type"),
        "statistic": value.get("statistic"),
        "degreesOfFreedom": value.get("degrees_of_freedom"),
        "reportedP": value.get("reported_p"),
        "sidedness": value.get("sidedness"),
    }


def _statistic_mapping(
    finding: VerificationFinding, scientific_input: dict[str, JsonValue]
) -> tuple[str, Impact, JsonValue, JsonValue, JsonValue]:
    impact = _statistics_impact(finding, scientific_input)
    if finding.status is FindingStatus.VERIFIED:
        statement = "The reported statistic is consistent with independent SciPy recomputation."
    elif finding.status is FindingStatus.DISCREPANCY:
        statement = "The reported p-value differs materially from independent SciPy recomputation."
    elif finding.status is FindingStatus.UNVERIFIABLE:
        statement = "The reported statistic lacks evidence required for a unique recomputation."
    else:
        statement = "The reported statistic verification procedure returned a failed result."
    library_versions = finding.details.get("library_versions")
    library_version = library_versions.get("scipy") if isinstance(library_versions, dict) else None
    observed: dict[str, JsonValue] = {
        "library": "scipy",
        "libraryVersion": library_version,
        "recomputedP": finding.details.get("recomputed_p"),
        "procedure": finding.details.get("formula_or_procedure"),
        "absoluteDifference": finding.details.get("absolute_difference"),
        "impactRuleVersion": STATISTICS_IMPACT_RULE_VERSION,
    }
    tolerance_value = finding.details.get("tolerance")
    tolerance: dict[str, JsonValue] = {
        "absolute": tolerance_value.get("absolute")
        if isinstance(tolerance_value, dict)
        else scientific_input.get("absolute_tolerance", 5e-5),
        "relative": tolerance_value.get("relative")
        if isinstance(tolerance_value, dict)
        else scientific_input.get("relative_tolerance", 1e-4),
        "effective": finding.details.get("effective_tolerance"),
    }
    return statement, impact, _statistic_reported(scientific_input), observed, tolerance


def _comparison_mapping(
    finding: VerificationFinding,
    scientific_input: dict[str, JsonValue],
    *,
    figure: bool,
) -> tuple[str, Impact, JsonValue, JsonValue, JsonValue]:
    impact: Literal["informational", "major"] = (
        "informational" if finding.status is FindingStatus.VERIFIED else "major"
    )
    kind = "figure" if figure else "analysis result"
    statement = (
        f"The structured {kind} comparison agrees within the explicit tolerance."
        if finding.status is FindingStatus.VERIFIED
        else f"The structured {kind} comparison found differences beyond tolerance."
    )
    expected_key = "original" if figure else "expected"
    observed_key = "regenerated" if figure else "reproduced"
    reported: JsonValue = {
        expected_key: scientific_input.get(expected_key),
        "method": finding.reproduction_kind.value,
    }
    observed: JsonValue = {
        observed_key: scientific_input.get(observed_key),
        "method": finding.reproduction_kind.value,
        "differences": finding.details.get("differences"),
        "visualSimilarityUsed": finding.details.get("visual_similarity_used", False),
    }
    tolerance: JsonValue = finding.details.get("tolerance")
    return statement, impact, reported, observed, tolerance


def map_finding(
    finding: VerificationFinding,
    scientific_input: dict[str, JsonValue],
    *,
    evidence_refs: tuple[EvidenceReferenceDTO, ...],
    artifact_ids: tuple[str, ...],
) -> FindingSubmissionDTO:
    """Create a deterministic stable-key ORAtlas submission for one local finding."""
    protocol_name = finding.protocol.name
    if protocol_name == "reported-statistic-consistency":
        statement, impact, reported, observed, tolerance = _statistic_mapping(
            finding, scientific_input
        )
        finding_type = "statistic-consistency"
        prefix = "stat"
    elif protocol_name == "figure-structured-comparison":
        statement, impact, reported, observed, tolerance = _comparison_mapping(
            finding, scientific_input, figure=True
        )
        finding_type = protocol_name
        prefix = "figure"
    elif protocol_name == "analysis-result-comparison":
        statement, impact, reported, observed, tolerance = _comparison_mapping(
            finding, scientific_input, figure=False
        )
        finding_type = protocol_name
        prefix = "analysis"
    else:
        raise ValueError(f"no ORAtlas finding mapping for protocol {finding.protocol.key}")

    identity = sha256_json(
        {
            "protocol": finding.protocol,
            "scientificInput": scientific_input,
            "evidenceRefs": evidence_refs,
        }
    )[:24]
    test_type = scientific_input.get("test_type")
    discriminator = str(test_type).lower() if isinstance(test_type, str) else "result"
    finding_key = f"{prefix}-{discriminator}-{identity}"
    return FindingSubmissionDTO(
        findingKey=finding_key,
        findingType=finding_type,
        status=finding.status,
        impact=impact,
        statement=statement,
        rationale=finding.rationale,
        reported=reported,
        observed=observed,
        tolerance=tolerance,
        evidenceRefs=evidence_refs,
        artifactRefs=artifact_ids,
    )
