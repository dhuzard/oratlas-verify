from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from scipy import stats

from oratlas_verify.core.contracts import FindingStatus, VerificationInput
from oratlas_verify.verifiers.statistics.reported import verify_reported_statistic


def test_t_fixture_a_correct_rounding_is_verified(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "t",
                "statistic": 3.12,
                "degrees_of_freedom": [38],
                "reported_p": 0.0034,
                "sidedness": "two-sided",
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED
    assert finding.details["recomputed_p"] == pytest.approx(0.0034449775695829343)
    assert finding.content_sha256 == finding.computed_content_sha256


def test_t_fixture_b_wrong_p_is_discrepancy(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "t",
                "statistic": 3.12,
                "degrees_of_freedom": [38],
                "reported_p": 0.2,
                "sidedness": "two-sided",
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.DISCREPANCY
    assert finding.details["absolute_difference"] > 0.19


@pytest.mark.parametrize("missing", ["sidedness", "degrees_of_freedom", "reported_p"])
def test_fixture_c_missing_information_is_unverifiable(make_input, statistic_protocol, missing):
    payload = {
        "test_type": "t",
        "statistic": 3.12,
        "degrees_of_freedom": [38],
        "reported_p": 0.0034,
        "sidedness": "two-sided",
    }
    del payload[missing]
    finding = verify_reported_statistic(make_input(payload), statistic_protocol)[0]
    assert finding.status is FindingStatus.UNVERIFIABLE


def test_fixture_d_correct_f_test(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "F",
                "statistic": 4.0,
                "degrees_of_freedom": [2, 30],
                "reported_p": 0.02884462329569682,
                "sidedness": "greater",
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED
    assert "scipy.stats.f.sf" in finding.details["formula_or_procedure"]


def test_fixture_e_incorrect_chi_square(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "chi-square",
                "statistic": 10.0,
                "degrees_of_freedom": [4],
                "reported_p": 0.4,
                "sidedness": "greater",
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.DISCREPANCY


def test_z_has_no_degrees_of_freedom(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "z",
                "statistic": 1.96,
                "degrees_of_freedom": [],
                "reported_p": 0.04999579029644087,
                "sidedness": "two-sided",
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED


@pytest.mark.parametrize(
    "payload",
    [
        {
            "test_type": "t",
            "statistic": 1,
            "degrees_of_freedom": [0],
            "reported_p": 0.1,
            "sidedness": "two-sided",
        },
        {
            "test_type": "F",
            "statistic": -1,
            "degrees_of_freedom": [1, 2],
            "reported_p": 0.1,
            "sidedness": "greater",
        },
        {
            "test_type": "chi-square",
            "statistic": 1,
            "degrees_of_freedom": [-2],
            "reported_p": 0.1,
            "sidedness": "greater",
        },
        {
            "test_type": "t",
            "statistic": 1,
            "degrees_of_freedom": [10],
            "reported_p": -0.1,
            "sidedness": "two-sided",
        },
        {
            "test_type": "t",
            "statistic": 1,
            "degrees_of_freedom": [10],
            "reported_p": 1.1,
            "sidedness": "two-sided",
        },
        {
            "test_type": "F",
            "statistic": 1,
            "degrees_of_freedom": [1, 2],
            "reported_p": 0.5,
            "sidedness": "two-sided",
        },
    ],
)
def test_invalid_parameters_fail_closed(make_input, statistic_protocol, payload):
    finding = verify_reported_statistic(make_input(payload), statistic_protocol)[0]
    assert finding.status is FindingStatus.FAILED


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_input_rejected_at_frozen_boundary(value):
    with pytest.raises((ValidationError, ValueError)):
        VerificationInput(
            publication_id="p",
            publication_version_id="v",
            payload={
                "test_type": "t",
                "statistic": value,
                "degrees_of_freedom": [10],
                "reported_p": 0.1,
                "sidedness": "two-sided",
            },
        )


def test_p_one_edge_at_zero_statistic(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "t",
                "statistic": 0,
                "degrees_of_freedom": [10],
                "reported_p": 1,
                "sidedness": "two-sided",
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED


def test_p_zero_extreme_value(make_input, statistic_protocol):
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "z",
                "statistic": 50,
                "degrees_of_freedom": [],
                "reported_p": 0,
                "sidedness": "greater",
                "absolute_tolerance": 0,
                "relative_tolerance": 0,
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED
    assert finding.details["recomputed_p"] == 0


def test_tolerance_boundary_is_inclusive(make_input, statistic_protocol):
    recomputed = float(stats.norm.sf(1.0))
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "z",
                "statistic": 1.0,
                "degrees_of_freedom": [],
                "reported_p": recomputed + 0.01,
                "sidedness": "greater",
                "absolute_tolerance": 0.01,
                "relative_tolerance": 0,
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED


@given(
    statistic=st.floats(min_value=-12, max_value=12, allow_nan=False, allow_infinity=False),
    df=st.integers(min_value=1, max_value=10000),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_t_matches_scipy(make_input, statistic_protocol, statistic, df):
    expected = float(2 * stats.t.sf(abs(statistic), df))
    finding = verify_reported_statistic(
        make_input(
            {
                "test_type": "t",
                "statistic": statistic,
                "degrees_of_freedom": [df],
                "reported_p": expected,
                "sidedness": "two-sided",
                "absolute_tolerance": 0,
                "relative_tolerance": 0,
            }
        ),
        statistic_protocol,
    )[0]
    assert finding.status is FindingStatus.VERIFIED
