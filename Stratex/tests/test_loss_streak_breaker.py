"""
tests/test_loss_streak_breaker.py
Consecutive-loss circuit breaker (2026-09-26 ledger tail):

1. LossStreakBreaker:
   - persists the streak (restart-safe: a new instance keeps the count)
   - does NOT pause before the limit, even for losses
   - pauses ALL new entries (trading_pause flag) + alerts exactly once per
     streak when CONSECUTIVE losses reach LOSS_STREAK_LIMIT — regardless of
     the amount (penny-sized losses included, which the percent-based daily
     breaker cannot see)
   - a winning trade resets the streak
   - rejects invalid config (limit < 1)
   - never triggers on unreadable PnL
2. Service wiring: the closed-trade sync path consults the breaker (guarded,
   never fatal to the monitor loop).
"""

import pytest

from testnet_engine.loss_streak_breaker import LossStreakBreaker
from trading_pause import is_trading_paused, set_trading_paused


class _RecordingAlerter:
    def __init__(self):
        self.messages = []

    def __call__(self, message: str):
        self.messages.append(message)


@pytest.fixture
def streak_env(tmp_path, monkeypatch):
    """Isolate streak + pause state files per test."""
    monkeypatch.setenv("LOSS_STREAK_BREAKER_STATE_FILE", str(tmp_path / "streak_state.json"))
    monkeypatch.setenv("TRADING_PAUSE_STATE_FILE", str(tmp_path / "pause_state.json"))
    set_trading_paused(False, actor="test_setup")
    yield
    set_trading_paused(False, actor="test_teardown")


def test_streak_counter_is_persisted_and_restart_safe(streak_env):
    breaker = LossStreakBreaker(3, alerter=_RecordingAlerter())
    breaker.check_close(-0.24)
    breaker.check_close(-0.05)
    # Simulate an engine restart: a NEW instance must keep the running streak.
    reborn = LossStreakBreaker(3, alerter=_RecordingAlerter())
    result = reborn.check_close(-0.11)
    assert result["breached"] is True
    assert result["consecutive_losses"] == 3
    assert is_trading_paused() is True


def test_losses_below_limit_do_not_pause(streak_env):
    breaker = LossStreakBreaker(5, alerter=_RecordingAlerter())
    for pnl in (-0.24, -0.048, -0.111):  # the 2026-09-26 ledger shape, pennies
        result = breaker.check_close(pnl)
        assert result["breached"] is False
    assert is_trading_paused() is False


def test_penny_streak_breaches_and_alerts_exactly_once(streak_env):
    """The exact scenario the percent breaker cannot see: six losses totalling
    less than a dollar. The streak breaker must still stop the bleeding."""
    alerter = _RecordingAlerter()
    breaker = LossStreakBreaker(5, alerter=alerter)
    for pnl in (-0.240, -0.048, -0.111, -0.117, -0.093):
        result = breaker.check_close(pnl)
    assert result["breached"] is True
    assert is_trading_paused() is True
    assert len(alerter.messages) == 1
    assert "loss-streak circuit breaker" in alerter.messages[0]
    # More losses while paused do not re-alert for the same streak level.
    breaker.check_close(-0.05)
    assert len(alerter.messages) == 1


def test_win_resets_the_streak(streak_env):
    breaker = LossStreakBreaker(3, alerter=_RecordingAlerter())
    breaker.check_close(-0.24)
    breaker.check_close(-0.05)
    result = breaker.check_close(+4.18)  # the ledger's avg winning trade
    assert result["consecutive_losses"] == 0
    assert result["breached"] is False
    # Two more losses still do not trip the 3-loss limit after the reset.
    breaker.check_close(-0.05)
    result = breaker.check_close(-0.05)
    assert result["breached"] is False
    assert is_trading_paused() is False


def test_invalid_limit_is_rejected(streak_env):
    with pytest.raises(ValueError):
        LossStreakBreaker(0)


def test_unreadable_pnl_never_trips(streak_env):
    breaker = LossStreakBreaker(1, alerter=_RecordingAlerter())
    for bad in (float("nan"), float("inf"), None, "not-a-number"):
        result = breaker.check_close(bad)
        assert result["checked"] is False
    assert is_trading_paused() is False


def test_service_wires_the_breaker_on_init(monkeypatch, streak_env):
    """The service constructor must expose a live LossStreakBreaker."""
    import config
    from testnet_engine.service import TestnetService

    monkeypatch.setattr(config, "LOSS_STREAK_LIMIT", 4)
    service = TestnetService.__new__(TestnetService)
    service._tg = lambda: None
    service._init_breakers()
    assert isinstance(service.loss_streak_breaker, LossStreakBreaker)
    assert service.loss_streak_breaker.streak_limit == 4
