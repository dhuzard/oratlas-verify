import json
from pathlib import Path

import pytest

from oratlas_verify.core.contracts import ProtocolRef, VerificationInput
from oratlas_verify.core.registry import build_default_registry, require_handler


@pytest.mark.parametrize("case_id", list("ABCDEFGHI"))
def test_scientific_fixture_catalog(case_id: str):
    catalog_path = Path(__file__).parent / "fixtures" / "scientific_cases.json"
    case = json.loads(catalog_path.read_text(encoding="utf-8"))[case_id]
    name, version = case["protocol"].rsplit("/", 1)
    protocol = ProtocolRef(name=name, version=version)
    handler = require_handler(build_default_registry().resolve(protocol))
    verification_input = VerificationInput(
        publication_id=f"fixture-{case_id}",
        publication_version_id="synthetic-0.1.0",
        payload=case["input"],
    )
    finding = handler(verification_input, protocol)[0]
    assert finding.status.value == case["expected_status"]
