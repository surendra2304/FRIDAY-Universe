"""Tests for the TASK-FUT-009 what-if scenario prototype.

The module is a deterministic transform of a caller-supplied base path.
These tests pin the arithmetic (hand-computed), the coherence invariants,
and the honest-labelling contract (FUT-002/FUT-003 standard): evidence
class inherited and never upgraded, probability never recomputed,
elasticities printed as declared assumptions.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from futuris.core.enums import ConfidenceLevel, EvidenceClass
from futuris.core.schemas import Forecast
from futuris.scenarios.whatif import (
    DecayProfile,
    PathPoint,
    Shock,
    ShockKind,
    WhatIfRequest,
    apply_whatif,
    base_path_from_forecast,
    request_from_forecast,
)
from pydantic import ValidationError


def flat_path(central=100.0, half=10.0, steps=4):
    return [
        PathPoint(step=i + 1, central=central, lower=central - half, upper=central + half)
        for i in range(steps)
    ]


def test_single_permanent_shock_hand_computed():
    """BTC -20% with declared elasticity 0.5 -> -10% on the target, all steps."""
    req = WhatIfRequest(
        target="BTCUSDT",
        base_path=flat_path(),
        shocks=[
            Shock(name="btc_drop", driver="BTC", kind=ShockKind.PCT_CHANGE,
                  magnitude=-20.0, elasticity=0.5),
        ],
    )
    res = apply_whatif(req)
    for p in res.adjusted_path:
        assert p.total_effect_pct == pytest.approx(-10.0)
        assert p.contributions_pct == {"btc_drop": pytest.approx(-10.0)}
        assert p.adjusted_central == pytest.approx(90.0)
        # widen = 1 + 0.5 * 10/100 = 1.05; half-width 10 * 1.05 * factor 0.9 = 9.45
        assert p.adjusted_lower == pytest.approx(80.55)
        assert p.adjusted_upper == pytest.approx(99.45)
        assert p.adjusted_lower <= p.adjusted_central <= p.adjusted_upper


def test_pp_shock_uses_percentage_points():
    """Rates +1pp with declared elasticity -2.0 -> -2% on the target."""
    req = WhatIfRequest(
        target="equity_index",
        base_path=flat_path(central=200.0, half=4.0, steps=2),
        shocks=[
            Shock(name="rate_hike", driver="policy_rate", kind=ShockKind.PP_CHANGE,
                  magnitude=1.0, elasticity=-2.0),
        ],
    )
    res = apply_whatif(req)
    for p in res.adjusted_path:
        assert p.total_effect_pct == pytest.approx(-2.0)
        assert p.adjusted_central == pytest.approx(196.0)


def test_ramp_profile():
    """Onset step 2, ramp 3: effects 0%, +10%, +20%, +30% on a +30% shock."""
    req = WhatIfRequest(
        target="X",
        base_path=flat_path(central=200.0, half=0.0, steps=4),
        shocks=[
            Shock(name="oil_spike", driver="oil", magnitude=30.0, elasticity=1.0,
                  onset_step=2, ramp_steps=3),
        ],
        band_widening_per_effect_pct=0.0,
    )
    res = apply_whatif(req)
    centrals = [p.adjusted_central for p in res.adjusted_path]
    assert centrals == pytest.approx([200.0, 220.0, 240.0, 260.0])


def test_linear_decay_profile():
    """Ramp 1, decay over 2 steps: +10%, +5%, 0%."""
    req = WhatIfRequest(
        target="X",
        base_path=flat_path(central=100.0, half=0.0, steps=3),
        shocks=[
            Shock(name="headline", driver="news", magnitude=10.0, elasticity=1.0,
                  decay=DecayProfile.LINEAR_DECAY, decay_steps=2),
        ],
        band_widening_per_effect_pct=0.0,
    )
    res = apply_whatif(req)
    effects = [p.total_effect_pct for p in res.adjusted_path]
    assert effects == pytest.approx([10.0, 5.0, 0.0])


def test_multiple_shocks_add_with_attribution():
    req = WhatIfRequest(
        target="BTCUSDT",
        base_path=flat_path(steps=1),
        shocks=[
            Shock(name="btc", driver="BTC", magnitude=-20.0, elasticity=0.5),
            Shock(name="oil", driver="oil", magnitude=15.0, elasticity=0.2),
        ],
    )
    res = apply_whatif(req)
    p = res.adjusted_path[0]
    assert p.contributions_pct["btc"] == pytest.approx(-10.0)
    assert p.contributions_pct["oil"] == pytest.approx(3.0)
    assert p.total_effect_pct == pytest.approx(-7.0)
    assert p.adjusted_central == pytest.approx(93.0)


def test_non_negative_floor_and_breakdown_warning():
    """A -150% total effect breaks the linear assumption: clamp + warn, never hide."""
    req = WhatIfRequest(
        target="ALT",
        base_path=flat_path(central=50.0, half=5.0, steps=1),
        shocks=[Shock(name="crash", driver="BTC", magnitude=-150.0, elasticity=1.0)],
        non_negative_floor=True,
    )
    res = apply_whatif(req)
    p = res.adjusted_path[0]
    assert p.adjusted_central == 0.0
    assert p.adjusted_lower >= 0.0
    assert any("break-down of the linear-elasticity assumption" in w for w in res.warnings)


def test_evidence_class_inherited_never_upgraded():
    live = apply_whatif(WhatIfRequest(
        target="X", base_path=flat_path(steps=1),
        shocks=[Shock(name="s", driver="BTC", magnitude=5.0, elasticity=1.0)],
        base_evidence_class=EvidenceClass.LIVE,
        base_evidence_source="telemetry:series_42",
        base_probability=0.7,
    ))
    # Computed from a live base is DERIVED, not LIVE, and never above the base.
    assert live.evidence_class is EvidenceClass.DERIVED
    assert live.evidence_source == (
        "telemetry:series_42; +futuris.scenarios.whatif@v1-prototype shock transform"
    )
    assert live.probability_outcome == 0.7
    assert live.probability_status == "not_recomputed_by_whatif_engine"
    assert live.prediction_is_not_authorization is True

    synth = apply_whatif(WhatIfRequest(
        target="X", base_path=flat_path(steps=1),
        shocks=[Shock(name="s", driver="BTC", magnitude=5.0, elasticity=1.0)],
    ))
    assert synth.evidence_class is EvidenceClass.SYNTHETIC
    assert synth.probability_outcome is None


def test_assumptions_are_printed_on_the_output():
    req = WhatIfRequest(
        target="BTCUSDT",
        base_path=flat_path(steps=2),
        shocks=[Shock(name="btc_drop", driver="BTC", magnitude=-20.0, elasticity=0.5,
                      rationale="exchange outage rumour")],
    )
    res = apply_whatif(req)
    text = res.render_text()
    assert "btc_drop" in text and "-20%" in text and "0.5" in text
    assert "not estimated" in text  # elasticities declared, not estimated
    assert "probability is not recomputed" in text
    assert "WHAT-IF (prototype)" in text


def test_validation_rejects_incoherent_inputs():
    with pytest.raises(ValidationError):
        PathPoint(step=1, central=100.0, lower=110.0, upper=120.0)
    with pytest.raises(ValidationError):
        Shock(name="s", driver="BTC", magnitude=1.0, elasticity=1.0,
              decay=DecayProfile.LINEAR_DECAY)  # decay_steps missing
    with pytest.raises(ValidationError):
        WhatIfRequest(
            target="X",
            base_path=[PathPoint(step=2, central=1.0, lower=1.0, upper=1.0),
                       PathPoint(step=1, central=1.0, lower=1.0, upper=1.0)],
            shocks=[Shock(name="s", driver="BTC", magnitude=1.0, elasticity=1.0)],
        )
    with pytest.raises(ValidationError):
        WhatIfRequest(
            target="X",
            base_path=flat_path(steps=1),
            shocks=[Shock(name="dup", driver="BTC", magnitude=1.0, elasticity=1.0),
                    Shock(name="dup", driver="oil", magnitude=1.0, elasticity=1.0)],
        )


def _forecast(intervals):
    now = datetime(2026, 11, 15, tzinfo=UTC)
    return Forecast(
        target="BTCUSDT",
        as_of=now,
        horizon=timedelta(days=7),
        expires_at=now + timedelta(days=7),
        prediction=100.0,
        range_lower=90.0,
        range_upper=110.0,
        confidence=ConfidenceLevel.MEDIUM,
        model_version="heuristic:telemetry_vol_rule@v2",
        review_at=now + timedelta(days=1),
        intervals=intervals,
        probability=0.62,
        evidence_class=EvidenceClass.LIVE,
        evidence_source="telemetry:btc_series",
    )


def test_base_path_from_forecast_intervals():
    f = _forecast([
        {"step": 1, "lower": 90.0, "central": 100.0, "upper": 110.0},
        {"step": 2, "lower": 92.0, "central": 103.0, "upper": 114.0},
    ])
    points, meta = base_path_from_forecast(f)
    assert [p.central for p in points] == [100.0, 103.0]
    assert meta["path_source"] == "forecast_intervals"
    req = request_from_forecast(
        f, [Shock(name="btc", driver="BTC", magnitude=-20.0, elasticity=0.5)]
    )
    res = apply_whatif(req)
    assert res.evidence_class is EvidenceClass.DERIVED
    assert res.probability_outcome == 0.62
    assert any("base path source: forecast_intervals" in a for a in res.assumptions)


def test_base_path_from_forecast_without_intervals_is_single_step():
    f = _forecast([])
    points, meta = base_path_from_forecast(f)
    assert len(points) == 1
    assert points[0].central == 100.0
    assert meta["path_source"] == "forecast_point_estimate_single_step"


def test_base_path_from_forecast_duck_typed():
    fake = SimpleNamespace(
        intervals=[{"step": 1, "lower": 1.0, "central": 2.0, "upper": 3.0}],
        prediction=2.0, range_lower=1.0, range_upper=3.0,
        evidence_class=EvidenceClass.SYNTHETIC, evidence_source=None,
        probability=None, model_version="x", target="T",
    )
    points, _ = base_path_from_forecast(fake)
    assert points[0].central == 2.0
