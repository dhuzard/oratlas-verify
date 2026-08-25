"""Isolated ORAtlas HTTP adapter. Scientific modules do not import this package."""

from oratlas_verify.oratlas.authentication import ORAtlasConfig
from oratlas_verify.oratlas.client import ORAtlasClient

__all__ = ["ORAtlasClient", "ORAtlasConfig"]
