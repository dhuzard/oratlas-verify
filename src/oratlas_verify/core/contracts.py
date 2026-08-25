"""Repository-local contracts. ORAtlas identifiers are opaque exact strings."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Never, Self, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import TypeAliasType

from oratlas_verify.core.json import sha256_json

JsonValue = TypeAliasType(
    "JsonValue",
    Union[  # noqa: UP007 - runtime PEP 695 alias must support Python 3.11
        None, bool, int, float, str, list[Any], dict[str, Any]
    ],
)


class FrozenDict(dict[str, Any]):
    """JSON-serializable dict that rejects mutation after construction."""

    @staticmethod
    def _blocked() -> Never:
        raise TypeError("domain JSON values are immutable")

    def __setitem__(self, key: str, value: Any) -> None:
        self._blocked()

    def __delitem__(self, key: str) -> None:
        self._blocked()

    def clear(self) -> None:
        self._blocked()

    def pop(self, key: str, default: Any = None) -> Any:
        self._blocked()

    def popitem(self) -> tuple[str, Any]:
        self._blocked()

    def setdefault(self, key: str, default: Any = None) -> Any:
        self._blocked()

    def update(self, *args: Any, **kwargs: Any) -> None:
        self._blocked()

    def __ior__(self, value: Any) -> Self:  # type: ignore[override,misc]
        self._blocked()


class FrozenList(list[Any]):
    """JSON-serializable list that rejects mutation after construction."""

    @staticmethod
    def _blocked() -> Never:
        raise TypeError("domain JSON values are immutable")

    def __setitem__(self, key: int | slice, value: Any) -> None:  # type: ignore[override]
        self._blocked()

    def __delitem__(self, key: int | slice) -> None:  # type: ignore[override]
        self._blocked()

    def append(self, value: Any) -> None:
        self._blocked()

    def extend(self, values: Any) -> None:
        self._blocked()

    def insert(self, index: int, value: Any) -> None:  # type: ignore[override]
        self._blocked()

    def pop(self, index: int = -1) -> Any:  # type: ignore[override]
        self._blocked()

    def remove(self, value: Any) -> None:
        self._blocked()

    def clear(self) -> None:
        self._blocked()

    def reverse(self) -> None:
        self._blocked()

    def sort(self, *args: Any, **kwargs: Any) -> None:
        self._blocked()

    def __iadd__(self, value: Any) -> Self:  # type: ignore[misc]
        self._blocked()

    def __imul__(self, value: int) -> Self:  # type: ignore[override,misc]
        self._blocked()


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return FrozenDict({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return FrozenList(_deep_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_post_init(self, context: Any, /) -> None:
        for field, value in self.__dict__.items():
            object.__setattr__(self, field, _deep_freeze(value))


class FindingStatus(StrEnum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially-verified"
    DISCREPANCY = "discrepancy"
    UNVERIFIABLE = "unverifiable"
    NOT_APPLICABLE = "not-applicable"
    FAILED = "failed"


class ReproductionKind(StrEnum):
    REGENERATION = "regeneration"
    INDEPENDENT_REPRODUCTION = "independent-reproduction"
    STRUCTURED_COMPARISON = "structured-comparison"
    VISUAL_CONSISTENCY = "visual-consistency"
    NOT_APPLICABLE = "not-applicable"


class ProtocolRef(FrozenModel):
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")

    @property
    def key(self) -> str:
        return f"{self.name}/{self.version}"


class ArtifactReference(FrozenModel):
    artifact_id: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(min_length=1)
    byte_length: int = Field(ge=0)


class ExecutionPassport(FrozenModel):
    passport_id: str = Field(min_length=1)
    source_commit: str | None = None
    workflow: str | None = None
    environment: dict[str, JsonValue] = Field(default_factory=dict)
    artifact_hashes: tuple[str, ...] = ()
    verified_by_oratlas: bool = False


class VerificationInput(FrozenModel):
    """Frozen input payload plus exact identifiers supplied by ORAtlas."""

    publication_id: str
    publication_version_id: str
    payload: dict[str, JsonValue]
    evidence_ids: tuple[str, ...] = ()
    artifact_references: tuple[ArtifactReference, ...] = ()
    execution_passport: ExecutionPassport | None = None
    input_sha256: str | None = None

    @model_validator(mode="after")
    def validate_hash(self) -> VerificationInput:
        computed = sha256_json(self.payload)
        if self.input_sha256 is not None and self.input_sha256 != computed:
            raise ValueError("input_sha256 does not match the canonical payload")
        return self

    @property
    def computed_sha256(self) -> str:
        return sha256_json(self.payload)


class VerificationRequest(FrozenModel):
    run_id: str = Field(min_length=1)
    input: VerificationInput
    protocols: tuple[ProtocolRef, ...] = Field(min_length=1)
    requested_at: datetime | None = None
    correlation_id: str | None = None


class VerificationExecutionMetadata(FrozenModel):
    backend: str
    started_at: datetime
    completed_at: datetime
    run_id: str
    correlation_id: str
    python_version: str
    platform: str
    tool_versions: dict[str, str]
    input_sha256: str
    execution_passport_id: str | None = None


class VerificationArtifact(FrozenModel):
    artifact_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    byte_length: int = Field(ge=0)
    generator_protocol: ProtocolRef
    input_hashes: tuple[str, ...]
    tool_versions: dict[str, str]
    created_at: datetime
    finding_ids: tuple[str, ...] = ()
    filename: str | None = None


class VerificationFinding(FrozenModel):
    finding_id: str
    protocol: ProtocolRef
    status: FindingStatus
    title: str
    rationale: str
    reproduction_kind: ReproductionKind = ReproductionKind.NOT_APPLICABLE
    evidence_ids: tuple[str, ...] = ()
    details: dict[str, JsonValue] = Field(default_factory=dict)
    artifact_ids: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_sha256: str | None = None

    def content_for_hash(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"content_sha256"})

    @property
    def computed_content_sha256(self) -> str:
        return sha256_json(self.content_for_hash())


class VerificationResponse(FrozenModel):
    run_id: str
    findings: tuple[VerificationFinding, ...]
    artifacts: tuple[VerificationArtifact, ...]
    execution: VerificationExecutionMetadata
    outcome: Literal["completed", "failed"] = "completed"
