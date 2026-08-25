from __future__ import annotations

from typing import Any

import pytest

from oratlas_verify.core.contracts import ProtocolRef, VerificationInput


@pytest.fixture
def make_input():
    def factory(payload: dict[str, Any]) -> VerificationInput:
        return VerificationInput(
            publication_id="publication-exact",
            publication_version_id="version-exact",
            payload=payload,
            evidence_ids=("evidence-1",),
        )

    return factory


@pytest.fixture
def statistic_protocol() -> ProtocolRef:
    return ProtocolRef(name="reported-statistic-consistency", version="0.1.0")
