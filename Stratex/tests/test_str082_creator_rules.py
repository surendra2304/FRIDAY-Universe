"""TASK-STR-082 leg 3: S-11 creator hard rules in the advisory gate.

Covers the three rules (source S-11, item DaFKBDwJlLZ) as added to
Stratex/advisory_gate.py:
  (a) retail traders cannot control the market, only their own risk
      — named in the rule set; enforced structurally by the
      advisory-only invariant and FORBIDDEN_PARAMS (pre-existing);
  (b) don't take debt for trading — enabling a margin/borrowing
      parameter is rejected;
  (c) learn first, then put money in — enforced by the pre-existing
      MIN_REQUIRED_TRADES check.

Everything is offline: AdvisoryGate.validate on synthetic decisions
only, no network, no orders.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from advisory_gate import AdvisoryGate

EXPECTED_RULES = [
    "Retail traders cannot control the market, only their own risk.",
    "Don't take debt for trading.",
    "Learn first, then put money in.",
]

DEBT_PARAMS = [
    "margin_enabled",
    "borrow_enabled",
    "use_margin",
    "margin_trading_enabled",
    "leverage_enabled",
]


def _decision(param, current, new, decision_id="DEC_STR082"):
    return {
        "decision_id": decision_id,
        "status": "APPROVED",
        "confidence": 0.9,
        "parameter_changes": [
            {"parameter": param, "current_value": current, "new_value": new}
        ],
    }


def test_creator_hard_rules_are_named_in_the_rule_set():
    gate = AdvisoryGate()
    assert list(gate.CREATOR_HARD_RULES) == EXPECTED_RULES
    assert set(gate.DEBT_ENABLING_PARAMS) == set(DEBT_PARAMS)
    res = gate.validate(
        _decision("adx_period", 14.0, 16.0),
        {"adx_period": 14.0},
        shadow_mode=False,
    )
    assert res.verdict == "APPLY"
    assert res.bounds_checked["creator_hard_rules"] == EXPECTED_RULES


def test_debt_enabling_parameter_rejected():
    gate = AdvisoryGate()
    res = gate.validate(
        _decision("margin_enabled", False, True),
        {"margin_enabled": False},
        shadow_mode=False,
    )
    assert res.verdict == "REJECT"
    assert "debt" in res.rejected_changes[0]["reason"]
    assert "Don't take debt for trading" in res.rejected_changes[0]["reason"]


def test_all_debt_enabling_params_rejected():
    gate = AdvisoryGate()
    for param in DEBT_PARAMS:
        res = gate.validate(
            _decision(param, False, True, decision_id=f"DEC_DEBT_{param}"),
            {param: False},
            shadow_mode=False,
        )
        assert res.verdict == "REJECT", param
        assert "debt" in res.rejected_changes[0]["reason"], param


def test_debt_enabling_string_value_rejected():
    gate = AdvisoryGate()
    res = gate.validate(
        _decision("use_margin", "disabled", "enabled"),
        {"use_margin": "disabled"},
        shadow_mode=False,
    )
    assert res.verdict == "REJECT"
    assert "debt" in res.rejected_changes[0]["reason"]


def test_debt_rule_does_not_fire_when_disabling():
    # Disabling a debt flag is not a creator-rule violation. (The
    # change itself is still governed by the pre-existing generic
    # +/-20% numeric rule, which rejects boolean True->False flips;
    # that behaviour is unchanged by STR-082.)
    gate = AdvisoryGate()
    res = gate.validate(
        _decision("margin_enabled", True, False),
        {"margin_enabled": True},
        shadow_mode=False,
    )
    assert not any("debt" in r["reason"] for r in res.rejected_changes)


def test_leverage_increase_still_rejected():
    gate = AdvisoryGate()
    res = gate.validate(
        _decision("leverage", 5, 6),
        {"leverage": 5},
        shadow_mode=False,
    )
    assert res.verdict == "REJECT"
    assert "Leverage increase rejected" in res.rejected_changes[0]["reason"]


def test_normal_parameter_still_applies():
    gate = AdvisoryGate()
    res = gate.validate(
        _decision("adx_period", 14.0, 16.0),
        {"adx_period": 14.0},
        shadow_mode=False,
    )
    assert res.verdict == "APPLY"
    assert len(res.applied_changes) == 1


def test_insufficient_trades_still_rejects_learn_first():
    # Creator hard rule (c): learn first, then put money in — the
    # MIN_REQUIRED_TRADES check is its enforcement.
    gate = AdvisoryGate()
    res = gate.validate(
        _decision("adx_period", 14.0, 16.0),
        {"adx_period": 14.0},
        shadow_mode=False,
        trade_count=5,
    )
    assert res.verdict == "REJECT"
    assert "Insufficient data" in res.rationale


def test_bounded_recommendation_rejects_debt_enabling():
    gate = AdvisoryGate()
    rec = {
        "parameter": "margin_enabled",
        "current_value": False,
        "proposed_value": True,
        "maximum_delta": 1.0,
        "evidence": "test",
        "confidence": 0.9,
        "expiry": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat(),
        "authorization_required": True,
    }
    valid, reason, _ = gate.validate_bounded_recommendation(rec)
    assert not valid
    assert "debt" in reason


def test_bounded_recommendation_debt_rule_does_not_fire_when_disabling():
    gate = AdvisoryGate()
    rec = {
        "parameter": "margin_enabled",
        "current_value": True,
        "proposed_value": False,
        "maximum_delta": 1.0,
        "evidence": "test",
        "confidence": 0.9,
        "expiry": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat(),
        "authorization_required": True,
    }
    valid, reason, _ = gate.validate_bounded_recommendation(rec)
    assert "debt" not in reason
