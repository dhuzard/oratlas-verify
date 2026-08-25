import pytest

from oratlas_verify.execution.base import ArbitraryExecutionUnsupported
from oratlas_verify.execution.sandbox import execute_untrusted_repository


def test_arbitrary_repository_execution_is_unavailable():
    with pytest.raises(ArbitraryExecutionUnsupported):
        execute_untrusted_repository("https://untrusted.invalid/repository")
