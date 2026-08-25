"""Run the three pinned ORAtlas compatibility cases through HTTP only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from oratlas_verify.core.registry import build_default_registry
from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.client import ORAtlasClient
from oratlas_verify.oratlas.worker import ORAtlasVerificationWorker, installed_scipy_version


def main() -> int:
    bootstrap = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    worker = ORAtlasVerificationWorker(build_default_registry())
    observed: dict[str, str] = {}
    with ORAtlasClient(ORAtlasConfig("http://127.0.0.1:3100", bootstrap["token"])) as client:
        for case, run_id in bootstrap["runs"].items():
            result = worker.run(run_id, client)
            observed[case] = result.findings[0].status.value
    expected = {
        "verified": "verified",
        "discrepancy": "discrepancy",
        "unverifiable": "unverifiable",
    }
    if observed != expected:
        raise AssertionError(f"ORAtlas compatibility outcomes differ: {observed!r}")
    print(
        json.dumps(
            {
                "oratlasCommit": "999580bad1fee5b22e8113c5e1c7c9b888eb1217",
                "scipy": installed_scipy_version(),
                "outcomes": observed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
