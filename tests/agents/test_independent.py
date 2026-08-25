from dataclasses import dataclass

from oratlas_verify.agents.base import run_independent_first_pass
from oratlas_verify.core.contracts import FindingStatus, ProtocolRef
from oratlas_verify.core.findings import make_finding


@dataclass
class RecordingAuditor:
    name: str
    calls: int = 0

    def audit(self, verification_input, protocol):
        self.calls += 1
        return (
            make_finding(
                protocol=protocol,
                input_sha256=verification_input.computed_sha256,
                status=FindingStatus.VERIFIED,
                title=self.name,
                rationale="independent fixture",
                details={"auditor": self.name},
            ),
        )


def test_first_pass_outputs_remain_separate(make_input):
    auditors = (RecordingAuditor("critical"), RecordingAuditor("strength"))
    protocol = ProtocolRef(name="methods-audit", version="0.1.0")
    outputs = run_independent_first_pass(auditors, make_input({"methods": "fixture"}), protocol)
    assert [output.auditor_name for output in outputs] == ["critical", "strength"]
    assert outputs[0].first_pass_findings != outputs[1].first_pass_findings
    assert [auditor.calls for auditor in auditors] == [1, 1]
