"""Secret-bearing transport configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True, repr=False)
class ORAtlasConfig:
    base_url: str
    verifier_token: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("ORATLAS_BASE_URL must be an absolute HTTP(S) URL")
        if not self.verifier_token:
            raise ValueError("ORATLAS_VERIFIER_TOKEN must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @classmethod
    def from_environment(cls) -> ORAtlasConfig:
        try:
            base_url = os.environ["ORATLAS_BASE_URL"]
            token = os.environ["ORATLAS_VERIFIER_TOKEN"]
        except KeyError as exc:
            raise ValueError(f"missing required environment variable: {exc.args[0]}") from exc
        return cls(base_url=base_url.rstrip("/"), verifier_token=token)

    def authorization_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.verifier_token}"}
