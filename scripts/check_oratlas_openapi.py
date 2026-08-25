"""Fail closed unless the checked-out ORAtlas contract is the pinned document."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

PINNED_COMMIT = "999580bad1fee5b22e8113c5e1c7c9b888eb1217"
PINNED_OPENAPI_SHA256 = "6e3a2cff2d266e67bbf999186520bb404aea7921a9362a44e1fd2c47f14b0a26"
REQUIRED_ROUTES = (
    "/api/verifiers:",
    "/api/verifiers/{id}:",
    "/api/verification-protocols:",
    "/api/verification-protocols/{id}:",
    "/api/verification-runs/{id}:",
    "/api/verification-runs/{id}/claim:",
    "/api/verification-runs/{id}/input:",
    "/api/verification-runs/{id}/source-artifacts/{artifactId}:",
    "/api/verification-runs/{id}/artifacts/prepare:",
    "/api/verification-artifacts/{id}/content:",
    "/api/verification-runs/{id}/artifacts/complete:",
    "/api/verification-runs/{id}/findings:",
    "/api/verification-runs/{id}/transition:",
    "/api/publication-versions/{id}/verifications:",
)


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != PINNED_COMMIT:
        raise SystemExit(f"ORAtlas checkout is {commit}, expected {PINNED_COMMIT}")
    document = (root / "docs" / "openapi.yaml").read_bytes().replace(b"\r\n", b"\n")
    actual_sha256 = hashlib.sha256(document).hexdigest()
    if actual_sha256 != PINNED_OPENAPI_SHA256:
        raise SystemExit(
            f"pinned ORAtlas OpenAPI digest changed: {actual_sha256} != {PINNED_OPENAPI_SHA256}"
        )
    text = document.decode("utf-8")
    missing = [route for route in REQUIRED_ROUTES if route not in text]
    if missing:
        raise SystemExit(f"pinned ORAtlas OpenAPI omitted routes: {missing}")
    print(f"ORAtlas OpenAPI compatible at {PINNED_COMMIT} ({actual_sha256})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
