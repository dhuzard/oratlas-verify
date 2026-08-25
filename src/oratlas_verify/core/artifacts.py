"""Local immutable artifact retention with path-safe filenames."""

from __future__ import annotations

import os
from pathlib import Path

from oratlas_verify.core.provenance import GeneratedArtifact


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def persist(self, artifact: GeneratedArtifact) -> Path:
        # Artifact IDs are generated locally; strip punctuation for a conservative filename.
        safe_id = "".join(
            char for char in artifact.metadata.artifact_id if char.isalnum() or char in "-_"
        )
        if not safe_id:
            raise ValueError("artifact id cannot form a safe filename")
        destination = (self.root / f"{safe_id}.json").resolve()
        if self.root not in destination.parents:
            raise ValueError("artifact path escaped configured storage root")
        if destination.exists():
            existing = destination.read_bytes()
            if existing != artifact.content:
                raise FileExistsError("immutable artifact already exists with different content")
            return destination
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(artifact.content)
        os.replace(temporary, destination)
        return destination
