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
