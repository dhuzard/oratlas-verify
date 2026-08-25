from oratlas_verify.core.blinding import apply_bias_reduced_profile


def test_blinded_profile_removes_identity_and_prestige_but_preserves_science():
    source = {
        "contributors": ["A"],
        "journal": "Prestige",
        "citation_count": 99,
        "production_mode": "author-run",
        "methods": {"design": "randomized", "affiliations": ["Lab"]},
        "scientific_provenance": {"instrument": "scope-7", "calibration": "2026-01"},
    }
    result = apply_bias_reduced_profile(source)
    assert "contributors" not in result.transformed
    assert "journal" not in result.transformed
    assert result.transformed["methods"] == {"design": "randomized"}
    assert result.transformed["scientific_provenance"]["instrument"] == "scope-7"
    assert result.transformed["production_mode"] == "author-run"
    assert source["contributors"] == ["A"]
    assert result.profile_version == "0.1.0"


def test_production_mode_removal_is_explicit():
    result = apply_bias_reduced_profile({"production_mode": "x"}, remove_production_mode=True)
    assert result.transformed == {}
    assert result.removed_paths == ("production_mode",)
