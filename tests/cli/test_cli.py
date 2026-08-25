from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_verify_statistic_cli_and_artifact_retention(tmp_path: Path):
    fixture = Path(__file__).parents[1] / "fixtures" / "statistic_verified.json"
    environment = os.environ.copy()
    environment["ORATLAS_VERIFY_ARTIFACT_DIR"] = str(tmp_path / "artifacts")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "oratlas_verify.cli.main",
            "verify-statistic",
            "--input",
            str(fixture),
            "--run-id",
            "cli-fixture",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    response = json.loads(result.stdout)
    assert response["run_id"] == "cli-fixture"
    assert response["findings"][0]["status"] == "verified"
    assert len(list((tmp_path / "artifacts").glob("*.json"))) == 1
    assert "secret" not in result.stderr
