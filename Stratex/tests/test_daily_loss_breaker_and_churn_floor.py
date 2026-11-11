"""
tests/test_daily_loss_breaker_and_churn_floor.py
2026-11-11 incident protections (see Stratex/docs/INCIDENT_2026-11-11_LOSSES.md):

1. DailyLossBreaker:
   - captures day-start equity and persists it (restart-safe)
   - does NOT pause when day PnL is above the limit
   - pauses ALL new entries (trading_pause flag) + alerts exactly once per day
     when day PnL breaches -DAILY_LOSS_LIMIT_PCT
   - rejects invalid config (limit outside (0, 0.50])
   - never triggers on unreadable equity
2. ProfitabilityGate anti-churn floor:
   - rejects signals whose SL or TP distance < max(MIN_BRACKET_PCT, 5x friction)
   - accepts the same signal once the bracket clears the floor
"""

import json

import pytest

import config
from testnet_engine.daily_loss_breaker import DailyLossBreaker
from testnet_engine.profitability_gate import ProfitabilityGate
from trading_pause import is_trading_paused, set_trading_paused


class _RecordingAlerter:
    def __init__(self):
        self.messages = []

    def __call__(self, message: str):
        self.messages.append(message)


@pytest.fixture
def breaker_env(tmp_path, monkeypatch):
    """Isolate breaker + pause state files per test."""
    monkeypatch.setenv("DAILY_LOSS_BREAKER_STATE_FILE", str(tmp_path / "breaker_state.json"))
    monkeypatch.setenv("TRADING_PAUSE_STATE_FILE", str(tmp_path / "pause_state.json"))
    set_trading_paused(False, actor="test_setup")
    yield
    set_trading_paused(False, actor="test_teardown")


def test_breaker_rejects_invalid_limit():
    with pytest.raises(ValueError):
        DailyLossBreaker(0.0)
    with pytest.raises(ValueError):
        DailyLossBreaker(0.75)


def test_breaker_no_trip_within_limit(breaker_env):
    alerter = _RecordingAlerter()
    breaker = DailyLossBreaker(0.03, alerter=alerter)

    result = breaker.check(10_000.0)
    assert result["checked"] is True
    assert result["day_start_equity"] == 10_000.0
    assert result["breached"] is False

    # Down 2% (within the 3% limit): still trading
    result = breaker.check(9_800.0)
    assert result["breached"] is False
    assert is_trading_paused() is False
    assert alerter.messages == []


def test_breaker_trips_and_pauses_on_limit_breach(breaker_env):
    alerter = _RecordingAlerter()
    breaker = DailyLossBreaker(0.03, alerter=alerter)

    breaker.check(10_000.0)
    result = breaker.check(9_650.0)  # -3.5%: breach

    assert result["breached"] is True
    assert result["paused"] is True
    assert is_trading_paused() is True
    assert len(alerter.messages) == 1
    assert "circuit breaker" in alerter.messages[0]


def test_breaker_alerts_once_per_day_but_stays_paused(breaker_env):
    alerter = _RecordingAlerter()
    breaker = DailyLossBreaker(0.03, alerter=alerter)

    breaker.check(10_000.0)
    breaker.check(9_500.0)   # breach
    breaker.check(9_400.0)   # deeper breach, same day
    breaker.check(9_450.0)   # partial recovery, still breached

    assert len(alerter.messages) == 1, "must alert exactly once per day"
    assert is_trading_paused() is True


def test_breaker_day_start_equity_persists_across_restart(breaker_env):
    alerter = _RecordingAlerter()
    breaker = DailyLossBreaker(0.03, alerter=alerter)
    breaker.check(10_000.0)

    # "Restart": a fresh breaker instance must reuse the persisted baseline,
    # not treat the (lower) current equity as the new day-start.
    breaker2 = DailyLossBreaker(0.03, alerter=_RecordingAlerter())
    result = breaker2.check(9_700.0)  # -3.0% vs persisted baseline: breach

    assert result["day_start_equity"] == 10_000.0
    assert result["breached"] is True
    assert is_trading_paused() is True


def test_breaker_unreadable_equity_never_trips(breaker_env):
    alerter = _RecordingAlerter()
    breaker = DailyLossBreaker(0.03, alerter=alerter)
    breaker.check(10_000.0)

    result = breaker.check(float("nan"))
    assert result["checked"] is False
    assert is_trading_paused() is False
    assert alerter.messages == []


def test_gate_rejects_churn_risk_bracket(monkeypatch, breaker_env):
    from research_phase9.cost_engine import CostEngine

    gate = ProfitabilityGate(cost_engine=CostEngine.get_futures_maker_config())  # deployed bot runs FUTURES (8 bps)
    monkeypatch.setattr(config, "MIN_BRACKET_PCT", 0.0030, raising=False)

    class _Sig:
        strategy_type = "RULE_BASED"
        win_rate_prior = 0.431
        confidence = 0.431

    # entry 100, SL 99.85 (0.15%), TP 100.45 (0.45%): SL leg below the 0.30% floor
    accepted, metrics = gate.evaluate_signal(
        "BTCUSDT", "BUY", 100.0, 99.85, 100.45, _Sig()
    )
    assert accepted is False
    assert metrics["reason"] == "CHURN_RISK_BRACKET"


def test_gate_accepts_bracket_clearing_the_floor(monkeypatch, breaker_env):
    from research_phase9.cost_engine import CostEngine

    gate = ProfitabilityGate(cost_engine=CostEngine.get_futures_maker_config())  # deployed bot runs FUTURES (8 bps)
    monkeypatch.setattr(config, "MIN_BRACKET_PCT", 0.0030, raising=False)

    class _Sig:
        strategy_type = "RULE_BASED"
        win_rate_prior = 0.431  # factory_winner_1's honest prior
        confidence = 0.431

    # entry 100, SL 99.0 (1.0%), TP 102.0 (2.0%): both legs clear every floor
    # (floor = max(0.30%, 5x0.08%) = 0.40% under futures friction)
    accepted, metrics = gate.evaluate_signal(
        "BTCUSDT", "BUY", 100.0, 99.0, 102.0, _Sig()
    )
    assert accepted is True, f"wide bracket must pass: {metrics}"
    assert metrics["decision"] == "ACCEPTED"
