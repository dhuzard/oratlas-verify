from oratlas_verify.verifiers.figures.image import compare_images


def test_exact_image_hash_is_only_supplementary_evidence():
    comparison = compare_images(b"same bytes", b"same bytes")
    assert comparison.exact_hash_equal is True
    assert "supplementary" in comparison.interpretation
    assert comparison.perceptual_similarity is None
