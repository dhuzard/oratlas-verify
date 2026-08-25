"""Call-on-request CLI. It never crawls or executes publication code."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from oratlas_verify.core.artifacts import LocalArtifactStore
from oratlas_verify.core.contracts import (
    ProtocolRef,
    VerificationInput,
    VerificationRequest,
    VerificationResponse,
)
from oratlas_verify.core.json import canonical_json_bytes
from oratlas_verify.core.logging import configure_logging
from oratlas_verify.core.orchestration import VerificationOrchestrator
from oratlas_verify.core.registry import build_default_registry
from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.client import ORAtlasClient


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input JSON must contain an object at the top level")
    return value


def _write_json(value: object) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value) + b"\n")


def _orchestrator() -> VerificationOrchestrator:
    artifact_dir = Path(os.environ.get("ORATLAS_VERIFY_ARTIFACT_DIR", ".oratlas-verify/artifacts"))
    return VerificationOrchestrator(build_default_registry(), LocalArtifactStore(artifact_dir))


def _verify_statistic(args: argparse.Namespace) -> int:
    payload = _load_json(args.input)
    protocol = ProtocolRef(name="reported-statistic-consistency", version="0.1.0")
    request = VerificationRequest(
        run_id=args.run_id or f"local-{uuid4()}",
        input=VerificationInput(
            publication_id=args.publication_id,
            publication_version_id=args.publication_version_id,
            payload=payload,
        ),
        protocols=(protocol,),
    )
    response = _orchestrator().execute(request)
    _write_json(response)
    return 0


def _run(args: argparse.Namespace) -> int:
    with ORAtlasClient(ORAtlasConfig.from_environment()) as client:
        response = _orchestrator().run_remote(args.verification_run_id, client)
    _write_json(response)
    return 0


def _inspect(args: argparse.Namespace) -> int:
    with ORAtlasClient(ORAtlasConfig.from_environment()) as client:
        request = client.retrieve_frozen_input(args.verification_run_id)
    # Inspection is explicit; callers control terminal output handling.
    _write_json(request)
    return 0


def _validate_result(args: argparse.Namespace) -> int:
    value = _load_json(args.input)
    response = VerificationResponse.model_validate(value)
    for finding in response.findings:
        if finding.content_sha256 != finding.computed_content_sha256:
            raise ValueError(f"finding integrity hash mismatch: {finding.finding_id}")
    _write_json({"valid": True, "run_id": response.run_id, "finding_count": len(response.findings)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oratlas-verify",
        description="Run deterministic, request-scoped scientific verification procedures.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    statistic = subparsers.add_parser("verify-statistic", help="verify one structured statistic")
    statistic.add_argument("--input", required=True, type=Path, help="structured assertion JSON")
    statistic.add_argument("--run-id")
    statistic.add_argument("--publication-id", default="local")
    statistic.add_argument("--publication-version-id", default="local")
    statistic.set_defaults(handler=_verify_statistic)

    run = subparsers.add_parser("run", help="retrieve and execute an ORAtlas verification run")
    run.add_argument("verification_run_id")
    run.set_defaults(handler=_run)

    inspect = subparsers.add_parser("inspect", help="inspect an exact frozen ORAtlas input")
    inspect.add_argument("verification_run_id")
    inspect.set_defaults(handler=_inspect)

    validate = subparsers.add_parser(
        "validate-result", help="validate a response and finding hashes"
    )
    validate.add_argument("--input", required=True, type=Path)
    validate.set_defaults(handler=_validate_result)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ValueError, ValidationError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
