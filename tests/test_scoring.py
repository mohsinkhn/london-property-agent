"""Tests for the scoring engine."""

from src.scoring.engine import (
    score_value,
    score_commute,
    score_crime,
    score_epc,
    score_schools,
    score_size,
    PropertyScore,
    compute_total,
)


def test_score_value_below_average():
    # 20% below average => ~100
    assert abs(score_value(400_000, 500_000) - 100.0) < 0.01


def test_score_value_at_average():
    # At average => ~50
    assert abs(score_value(500_000, 500_000) - 50.0) < 0.01


def test_score_value_above_average():
    # 20% above => 0
    assert score_value(600_000, 500_000) == 0.0


def test_score_value_zero_average():
    assert score_value(500_000, 0) == 50.0


def test_score_commute_zero():
    assert score_commute(0, 45) == 100.0


def test_score_commute_at_max():
    assert score_commute(45, 45) == 20.0


def test_score_commute_over_max():
    assert score_commute(68, 45) == 0.0


def test_score_commute_half():
    # 22 min out of 45 max
    result = score_commute(22, 45)
    assert 50 < result < 70


def test_score_crime_zero():
    assert score_crime(0) == 100.0


def test_score_crime_high():
    assert score_crime(100) == 0.0


def test_score_crime_medium():
    assert score_crime(50) == 50.0


def test_score_epc_ratings():
    assert score_epc("A") == 100.0
    assert score_epc("C") == 70.0
    assert score_epc("G") == 10.0


def test_score_schools_string():
    assert score_schools("Outstanding") == 100.0
    assert score_schools("Good") == 70.0


def test_score_schools_numeric():
    assert score_schools(1.0) == 100.0
    assert score_schools(2.0) == 70.0


def test_score_size():
    assert score_size(5) == 100.0
    assert score_size(2) == 40.0
    # With sqft
    result = score_size(3, 1000)
    assert result > 50


def test_compute_total():
    ps = PropertyScore(address="Test", price=500_000)
    ps.value_score = 80
    ps.commute_score = 60
    ps.crime_score = 70
    ps.schools_score = 90
    ps.epc_score = 50
    ps.size_score = 40
    total = compute_total(ps)
    expected = 80 * 0.25 + 60 * 0.25 + 70 * 0.15 + 90 * 0.15 + 50 * 0.10 + 40 * 0.10
    assert abs(total - expected) < 0.01
