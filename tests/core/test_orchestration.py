from oratlas_verify.core.contracts import ProtocolRef, VerificationInput, VerificationRequest
from oratlas_verify.core.orchestration import VerificationOrchestrator
from oratlas_verify.core.registry import build_default_registry


def test_multi_protocol_envelope_routes_exact_payloads():
    statistic = ProtocolRef(name="reported-statistic-consistency", version="0.1.0")
    analysis = ProtocolRef(name="analysis-result-comparison", version="0.1.0")
    request = VerificationRequest(
        run_id="run-multi",
        input=VerificationInput(
            publication_id="p",
            publication_version_id="v",
            payload={
                "protocol_inputs": {
                    statistic.key: {
                        "test_type": "t",
                        "statistic": 0,
                        "degrees_of_freedom": [10],
                        "reported_p": 1,
                        "sidedness": "two-sided",
                    },
                    analysis.key: {
                        "expected": [1, 2],
                        "reproduced": [1, 2],
                        "comparison_kind": "independent-reproduction",
                        "absolute_tolerance": 0,
                        "relative_tolerance": 0,
                    },
                }
            },
        ),
        protocols=(statistic, analysis),
    )
    response = VerificationOrchestrator(build_default_registry()).execute(request)
    assert [finding.status.value for finding in response.findings] == ["verified", "verified"]
    assert response.execution.run_id == "run-multi"
    assert response.artifacts[0].finding_ids == tuple(
        finding.finding_id for finding in response.findings
    )
