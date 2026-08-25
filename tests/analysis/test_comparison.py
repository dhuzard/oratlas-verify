from oratlas_verify.core.contracts import FindingStatus, ProtocolRef, ReproductionKind
from oratlas_verify.verifiers.analysis.comparison import verify_analysis_result

PROTOCOL = ProtocolRef(name="analysis-result-comparison", version="0.1.0")


def test_fixture_h_independent_equivalent_result(make_input):
    finding = verify_analysis_result(
        make_input(
            {
                "expected": {"effect": 1.0, "ci": [0.5, 1.5], "table": [[1, 2], [3, 4]]},
                "reproduced": {
                    "effect": 1.00001,
                    "ci": [0.50001, 1.49999],
                    "table": [[1, 2], [3, 4]],
                },
                "comparison_kind": "independent-reproduction",
                "absolute_tolerance": 0.0001,
                "relative_tolerance": 0,
            }
        ),
        PROTOCOL,
    )[0]
    assert finding.status is FindingStatus.VERIFIED
    assert finding.reproduction_kind is ReproductionKind.INDEPENDENT_REPRODUCTION


def test_fixture_i_beyond_tolerance(make_input):
    finding = verify_analysis_result(
        make_input(
            {
                "expected": {"metric": 5},
                "reproduced": {"metric": 6},
                "comparison_kind": "independent-reproduction",
                "absolute_tolerance": 0.1,
                "relative_tolerance": 0,
            }
        ),
        PROTOCOL,
    )[0]
    assert finding.status is FindingStatus.DISCREPANCY
    assert finding.details["differences"][0]["path"] == "$.metric"


def test_named_metric_missing_and_unexpected_are_detailed(make_input):
    finding = verify_analysis_result(
        make_input(
            {
                "expected": {"a": 1},
                "reproduced": {"b": 1},
                "comparison_kind": "structured-comparison",
                "absolute_tolerance": 0,
                "relative_tolerance": 0,
            }
        ),
        PROTOCOL,
    )[0]
    reasons = {item["reason"] for item in finding.details["differences"]}
    assert reasons == {"missing", "unexpected"}


def test_result_node_bound_is_enforced(make_input):
    finding = verify_analysis_result(
        make_input(
            {
                "expected": [1, 2, 3],
                "reproduced": [1, 2, 3],
                "comparison_kind": "regeneration",
                "absolute_tolerance": 0,
                "relative_tolerance": 0,
                "max_nodes": 2,
            }
        ),
        PROTOCOL,
    )[0]
    assert finding.status is FindingStatus.FAILED


def test_bool_is_not_equal_to_integer(make_input):
    finding = verify_analysis_result(
        make_input(
            {
                "expected": True,
                "reproduced": 1,
                "comparison_kind": "structured-comparison",
                "absolute_tolerance": 0,
                "relative_tolerance": 0,
            }
        ),
        PROTOCOL,
    )[0]
    assert finding.status is FindingStatus.DISCREPANCY
