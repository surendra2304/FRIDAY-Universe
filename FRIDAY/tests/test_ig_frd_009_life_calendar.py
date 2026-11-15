"""TASK-IG-FRD-009 — life-in-weeks computation tests (fixed 'today')."""

from __future__ import annotations

from datetime import date

import pytest

from friday.tools.builtin.life_calendar import compute_life_calendar

TODAY = date(2026, 11, 15)


def test_exact_week_math():
    # Born exactly 520 weeks (3640 days) before TODAY.
    dob = date(2016, 11, 20)  # 3647 days before -> 521 weeks floor
    data = compute_life_calendar(dob, lifespan_years=90, today=TODAY)
    days = (TODAY - dob).days
    assert data["weeks_lived"] == days // 7
    assert data["total_weeks"] == 90 * 52
    assert data["weeks_remaining"] == data["total_weeks"] - data["weeks_lived"]
    assert 0 < data["pct_lived"] < 100


def test_grid_shape_and_marker():
    dob = date(2000, 1, 1)
    data = compute_life_calendar(dob, lifespan_years=80, today=TODAY)
    assert len(data["grid"]) == 80
    assert all(len(row) == 52 for row in data["grid"])
    flat = "".join(data["grid"])
    assert flat.count("#") == data["weeks_lived"]
    assert flat.count("o") == 1
    assert flat.index("o") == data["weeks_lived"]  # marker sits at the current week
    assert flat.count(".") == data["total_weeks"] - data["weeks_lived"] - 1


def test_newborn():
    data = compute_life_calendar(TODAY, lifespan_years=90, today=TODAY)
    assert data["weeks_lived"] == 0
    assert data["pct_lived"] == 0.0
    assert data["grid"][0][0] == "o"
    assert data["current_year_of_life"] == 1


def test_past_lifespan_clamps():
    dob = date(1900, 1, 1)
    data = compute_life_calendar(dob, lifespan_years=90, today=TODAY)
    assert data["weeks_lived"] == data["total_weeks"]
    assert data["weeks_remaining"] == 0
    assert data["pct_lived"] == 100.0
    assert data["past_assumed_lifespan"] is True
    assert data["current_week_index"] is None
    assert "".join(data["grid"]).count("o") == 0


def test_validation():
    with pytest.raises(ValueError):
        compute_life_calendar(date(2030, 1, 1), today=TODAY)
    with pytest.raises(ValueError):
        compute_life_calendar(date(2000, 1, 1), lifespan_years=0, today=TODAY)
    with pytest.raises(ValueError):
        compute_life_calendar(date(2000, 1, 1), lifespan_years=200, today=TODAY)
