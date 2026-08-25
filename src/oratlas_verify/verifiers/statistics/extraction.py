"""Optional deterministic candidate extraction; candidates never bypass validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from oratlas_verify.verifiers.statistics.models import Sidedness, StatisticAssertion, TestType

_PATTERNS: tuple[tuple[TestType, re.Pattern[str]], ...] = (
    (
        TestType.T,
        re.compile(
            r"\bt\s*\(\s*(?P<df>\d+(?:\.\d+)?)\s*\)\s*=\s*(?P<stat>[+-]?\d+(?:\.\d+)?)"
            r"\s*,\s*p\s*=\s*(?P<p>\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*,\s*"
            r"(?P<side>two-sided|greater|less)\b",
            re.IGNORECASE,
        ),
    ),
    (
        TestType.F,
        re.compile(
            r"\bF\s*\(\s*(?P<df1>\d+(?:\.\d+)?)\s*,\s*(?P<df2>\d+(?:\.\d+)?)\s*\)"
            r"\s*=\s*(?P<stat>\d+(?:\.\d+)?)\s*,\s*p\s*=\s*"
            r"(?P<p>\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*,\s*(?P<side>greater)\b",
            re.IGNORECASE,
        ),
    ),
    (
        TestType.CHI_SQUARE,
        re.compile(
            r"\b(?:chi-square|χ2)\s*\(\s*(?P<df>\d+(?:\.\d+)?)\s*\)\s*=\s*"
            r"(?P<stat>\d+(?:\.\d+)?)\s*,\s*p\s*=\s*"
            r"(?P<p>\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*,\s*(?P<side>greater)\b",
            re.IGNORECASE,
        ),
    ),
    (
        TestType.Z,
        re.compile(
            r"\bz\s*=\s*(?P<stat>[+-]?\d+(?:\.\d+)?)\s*,\s*p\s*=\s*"
            r"(?P<p>\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*,\s*"
            r"(?P<side>two-sided|greater|less)\b",
            re.IGNORECASE,
        ),
    ),
)

_PARTIAL_T_PATTERN = re.compile(
    r"\bt\s*\(\s*(?P<df>\d+(?:\.\d+)?)\s*\)\s*=\s*(?P<stat>[+-]?\d+(?:\.\d+)?)"
    r"(?:\s*,\s*p\s*=\s*(?P<p>\d+(?:\.\d+)?(?:e[+-]?\d+)?))?"
    r"(?:\s*,\s*(?P<side>two-sided|greater|less))?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    assertions: tuple[StatisticAssertion, ...]
    extractor: str = "deterministic-explicit-statistic-regex/0.1.0"


def extract_explicit_statistics(text: str, *, evidence_id: str) -> ExtractionResult:
    """Extract only fully explicit assertions; never infer df or sidedness."""
    assertions: list[tuple[int, StatisticAssertion]] = []
    for test_type, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groupdict()
            dfs: tuple[float, ...]
            if test_type is TestType.F:
                dfs = (float(groups["df1"]), float(groups["df2"]))
            elif test_type is TestType.Z:
                # z uses the standard normal but retains an explicit empty df tuple.
                dfs = ()
            else:
                dfs = (float(groups["df"]),)
            assertions.append(
                (
                    match.start(),
                    StatisticAssertion(
                        test_type=test_type,
                        statistic=float(groups["stat"]),
                        degrees_of_freedom=dfs,
                        reported_p=float(groups["p"]),
                        sidedness=Sidedness(groups["side"].lower()),
                        source_span=match.group(0),
                        evidence_id=evidence_id,
                    ),
                )
            )
    return ExtractionResult(tuple(item for _, item in sorted(assertions, key=lambda item: item[0])))


def extract_statistic_candidates(text: str, *, evidence_id: str) -> ExtractionResult:
    """Extract explicit calculations and incomplete t-test candidates without inference.

    The incomplete form exists so missing p-values or sidedness become an
    ``unverifiable`` scientific finding instead of disappearing from the run.
    """
    complete = extract_explicit_statistics(text, evidence_id=evidence_id)
    assertions: list[tuple[int, StatisticAssertion]] = []
    complete_spans = {item.source_span for item in complete.assertions}
    for pattern_match in _PARTIAL_T_PATTERN.finditer(text):
        source_span = pattern_match.group(0)
        if source_span in complete_spans:
            continue
        groups = pattern_match.groupdict()
        assertions.append(
            (
                pattern_match.start(),
                StatisticAssertion(
                    test_type=TestType.T,
                    statistic=float(groups["stat"]),
                    degrees_of_freedom=(float(groups["df"]),),
                    reported_p=float(groups["p"]) if groups["p"] is not None else None,
                    sidedness=(
                        Sidedness(groups["side"].lower()) if groups["side"] is not None else None
                    ),
                    source_span=source_span,
                    evidence_id=evidence_id,
                ),
            )
        )
    for assertion in complete.assertions:
        start = text.find(assertion.source_span or "")
        assertions.append((start, assertion))
    return ExtractionResult(tuple(item for _, item in sorted(assertions, key=lambda item: item[0])))
