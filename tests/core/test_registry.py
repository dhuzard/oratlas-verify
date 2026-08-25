import pytest

from oratlas_verify.core.contracts import ProtocolRef
from oratlas_verify.core.errors import UnknownProtocolError
from oratlas_verify.core.registry import build_default_registry, require_handler


def test_exact_protocol_registry_contains_implemented_and_reserved_versions():
    registry = build_default_registry()
    assert registry.keys() == (
        "analysis-result-comparison/0.1.0",
        "claim-evidence-audit/0.1.0",
        "figure-structured-comparison/0.1.0",
        "methods-audit/0.1.0",
        "reported-statistic-consistency/0.1.0",
        "reproducibility-audit/0.1.0",
        "statistical-design-audit/0.1.0",
    )


def test_unknown_version_never_falls_back():
    with pytest.raises(UnknownProtocolError):
        build_default_registry().resolve(
            ProtocolRef(name="reported-statistic-consistency", version="0.1.1")
        )


def test_reserved_protocol_has_no_handler():
    definition = build_default_registry().resolve(
        ProtocolRef(name="methods-audit", version="0.1.0")
    )
    assert definition.availability == "reserved"
    with pytest.raises(UnknownProtocolError):
        require_handler(definition)
