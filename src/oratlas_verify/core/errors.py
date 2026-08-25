"""Typed failures at trust boundaries."""


class ORAtlasVerifyError(Exception):
    """Base domain error."""


class UnknownProtocolError(ORAtlasVerifyError):
    """An exact protocol name/version is not registered."""


class MalformedScientificInput(ORAtlasVerifyError):
    """Input is structurally present but unsafe or invalid to calculate."""


class MissingScientificInput(ORAtlasVerifyError):
    """Required information is absent or ambiguous."""


class TransportError(ORAtlasVerifyError):
    """ORAtlas transport failed or violated its contract."""


class ORAtlasAuthenticationError(TransportError):
    """The verifier bearer credential was missing or invalid."""


class ORAtlasAuthorizationError(TransportError):
    """The verifier credential is not authorized for the operation."""


class ORAtlasLeaseConflict(TransportError):
    """A run claim or state transition conflicts with the authoritative run state."""


class ORAtlasLeaseExpired(ORAtlasAuthorizationError):
    """The in-memory run lease has expired."""


class ORAtlasIdempotencyConflict(TransportError):
    """A stable key was replayed with different immutable content."""


class ORAtlasInputIntegrityError(TransportError):
    """Frozen ORAtlas input failed schema or digest validation."""


class ORAtlasArtifactIntegrityError(TransportError):
    """Artifact bytes or immutable metadata failed validation."""


class ORAtlasProtocolMismatch(TransportError):
    """The requested ORAtlas protocol is unsupported or internally inconsistent."""


class ORAtlasServerError(TransportError):
    """ORAtlas returned a transient or permanent server-side failure."""
