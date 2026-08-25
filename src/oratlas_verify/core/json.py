"""Canonical JSON helpers used for immutable machine artifacts and hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def json_compatible(value: Any) -> Any:
    """Convert domain objects to plain JSON-compatible values."""
    if isinstance(value, BaseModel):
        return json_compatible(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [json_compatible(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize with stable key ordering, encoding, and separators."""
    return json.dumps(
        json_compatible(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))
