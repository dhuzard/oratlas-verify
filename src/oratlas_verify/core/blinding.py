"""Versioned bias-reduced input transformations for scientific review."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from oratlas_verify.core.json import sha256_json

DEFAULT_REMOVED_FIELDS = frozenset(
    {
        "contributors",
        "contributor_names",
        "authors",
        "affiliations",
        "institutions",
        "institutional_identities",
        "journal",
        "journal_name",
        "prestige_metadata",
        "citation_count",
        "citation_counts",
        "previous_certification_outcomes",
        "certification_outcomes",
    }
)


@dataclass(frozen=True, slots=True)
class BlindedInput:
    profile_name: str
    profile_version: str
    transformed: dict[str, Any]
    removed_paths: tuple[str, ...]
    source_sha256: str
    transformed_sha256: str


def apply_bias_reduced_profile(
    payload: dict[str, Any],
    *,
    remove_production_mode: bool = False,
) -> BlindedInput:
    """Remove assessment-irrelevant identity/prestige fields without guessing provenance needs."""
    removed_fields = set(DEFAULT_REMOVED_FIELDS)
    if remove_production_mode:
        removed_fields.add("production_mode")
    transformed = deepcopy(payload)
    removed: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key in list(value):
                child_path = f"{path}.{key}" if path else key
                if key.lower() in removed_fields:
                    del value[key]
                    removed.append(child_path)
                else:
                    visit(value[key], child_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(transformed, "")
    return BlindedInput(
        profile_name="bias-reduced-scientific-review",
        profile_version="0.1.0",
        transformed=transformed,
        removed_paths=tuple(removed),
        source_sha256=sha256_json(payload),
        transformed_sha256=sha256_json(transformed),
    )
