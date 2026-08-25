"""Future isolated-worker integration point; intentionally no local arbitrary-code backend."""

from oratlas_verify.execution.base import ArbitraryExecutionUnsupported


def execute_untrusted_repository(*_args: object, **_kwargs: object) -> None:
    raise ArbitraryExecutionUnsupported(
        "oratlas-verify 0.1.0 never executes publication repositories on the host"
    )
