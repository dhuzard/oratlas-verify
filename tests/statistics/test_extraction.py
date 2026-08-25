from oratlas_verify.verifiers.statistics.extraction import extract_explicit_statistics


def test_deterministic_extractor_keeps_spans_and_evidence():
    text = "Results were t(38) = 3.12, p = 0.0034, two-sided. Then z = 1.96, p = 0.05, greater."
    result = extract_explicit_statistics(text, evidence_id="paragraph-4")
    assert len(result.assertions) == 2
    assert result.assertions[0].source_span == "t(38) = 3.12, p = 0.0034, two-sided"
    assert all(item.evidence_id == "paragraph-4" for item in result.assertions)


def test_extractor_does_not_guess_sidedness():
    result = extract_explicit_statistics("t(38)=3.12, p=0.0034", evidence_id="e1")
    assert result.assertions == ()
