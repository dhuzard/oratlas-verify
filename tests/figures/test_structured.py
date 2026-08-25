from oratlas_verify.core.contracts import FindingStatus, ProtocolRef, ReproductionKind
from oratlas_verify.verifiers.figures.structured import verify_structured_figure

PROTOCOL = ProtocolRef(name="figure-structured-comparison", version="0.1.0")


def plot_payload(regenerated_y, **overrides):
    payload = {
        "original": {
            "series": [{"name": "control", "x": [0, 1, 2], "y": [1, 2, 3]}],
            "x_label": "time",
            "y_label": "activity",
            "title": "Result",
        },
        "regenerated": {
            "series": [{"name": "control", "x": [0, 1, 2], "y": regenerated_y}],
            "x_label": "time",
            "y_label": "activity",
            "title": "Result",
        },
        "comparison_kind": "regeneration",
        "absolute_tolerance": 0,
        "relative_tolerance": 0,
    }
    payload.update(overrides)
    return payload


def test_fixture_f_identical_structured_figure(make_input):
    finding = verify_structured_figure(make_input(plot_payload([1, 2, 3])), PROTOCOL)[0]
    assert finding.status is FindingStatus.VERIFIED
    assert finding.reproduction_kind is ReproductionKind.REGENERATION
    assert finding.details["visual_similarity_used"] is False


def test_fixture_g_altered_series_is_discrepancy(make_input):
    finding = verify_structured_figure(make_input(plot_payload([1, 20, 3])), PROTOCOL)[0]
    assert finding.status is FindingStatus.DISCREPANCY
    assert finding.details["differences"][0]["path"] == "series[0].y[1]"


def test_series_dimension_difference(make_input):
    finding = verify_structured_figure(make_input(plot_payload([1, 2])), PROTOCOL)[0]
    assert finding.status is FindingStatus.DISCREPANCY
    assert finding.details["differences"][0]["path"] == "series[0].y.length"


def test_label_difference_can_be_ignored(make_input):
    payload = plot_payload([1, 2, 3], compare_labels=False)
    payload["regenerated"]["title"] = "Cosmetic retitle"
    finding = verify_structured_figure(make_input(payload), PROTOCOL)[0]
    assert finding.status is FindingStatus.VERIFIED


def test_nan_figure_input_is_rejected_by_frozen_envelope():
    from pydantic import ValidationError

    from oratlas_verify.core.contracts import VerificationInput

    try:
        VerificationInput(
            publication_id="p",
            publication_version_id="v",
            payload=plot_payload([1, float("nan"), 3]),
        )
    except (ValidationError, ValueError):
        return
    raise AssertionError("NaN was accepted")
