"""Optional supplementary image comparison; never establishes reproduction alone."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from oratlas_verify.core.json import sha256_bytes


@dataclass(frozen=True, slots=True)
class ImageComparison:
    exact_hash_equal: bool
    expected_sha256: str
    actual_sha256: str
    expected_dimensions: tuple[int, int] | None
    actual_dimensions: tuple[int, int] | None
    perceptual_similarity: float | None
    interpretation: str = "supplementary visual-consistency evidence only"


def compare_images(expected: bytes, actual: bytes, *, perceptual: bool = False) -> ImageComparison:
    """Compare local bytes. Pillow is optional and no URL/file execution is performed."""
    expected_dimensions: tuple[int, int] | None = None
    actual_dimensions: tuple[int, int] | None = None
    similarity: float | None = None
    try:
        from PIL import Image, ImageChops, ImageStat

        with Image.open(BytesIO(expected)) as expected_image:
            expected_dimensions = expected_image.size
            expected_rgb = expected_image.convert("RGB") if perceptual else None
        with Image.open(BytesIO(actual)) as actual_image:
            actual_dimensions = actual_image.size
            actual_rgb = actual_image.convert("RGB") if perceptual else None
        if (
            perceptual
            and expected_rgb is not None
            and actual_rgb is not None
            and expected_rgb.size == actual_rgb.size
        ):
            rms = sum(ImageStat.Stat(ImageChops.difference(expected_rgb, actual_rgb)).rms) / 3
            similarity = max(0.0, 1.0 - rms / 255.0)
    except ImportError:
        if perceptual:
            raise RuntimeError("Install oratlas-verify[images] for perceptual comparison") from None
    except OSError:
        # Hash comparison remains valid for opaque/unsupported image encodings.
        if perceptual:
            raise ValueError("perceptual comparison requires two valid supported images") from None
    return ImageComparison(
        exact_hash_equal=expected == actual,
        expected_sha256=sha256_bytes(expected),
        actual_sha256=sha256_bytes(actual),
        expected_dimensions=expected_dimensions,
        actual_dimensions=actual_dimensions,
        perceptual_similarity=similarity,
    )
