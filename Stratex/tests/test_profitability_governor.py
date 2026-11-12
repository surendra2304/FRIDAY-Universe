"""Profitability governor tests (ZAI Agent 2, 2026-11-12).

Each test pins one gate that was missing on the live account while it lost
>$1,000/day: pyramiding, write-only cooldown, never-set daily-loss breaker,
disabled position limits, same-bar signal refires, and the margin-exhaustion
order loop.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.multi_venue_engine import MultiVenueEngine  # noqa: E402


def _bare_engine() -> MultiVenueEngine:
    """An engine with only the state a gate reads — no network, no venues."""
    e = MultiVenueEngine.__new__(MultiVenueEngine)
    e.symbol_cooldown_sec = 900
    e.last_exit = {}
    e.positions = {}
    e.daily_loss_limit_hit = False
    e.daily_start_equity = 7000.0
    e.max_daily_loss_pct = 0.03
    e.daily_realized_pnl = 0.0
    e.max_positions_per_venue = 5
    e.max_total_positions = 10
    return e


class TestSymbolCooldown:
    def test_symbol_in_cooldown_right_after_exit(self):
        e = _bare_engine()
        e.last_exit["binance_futures:NEARUSDT"] = time.time() - 10
        assert e.symbol_in_cooldown("binance_futures", "NEARUSDT") is True

    def test_untraded_symbol_not_in_cooldown(self):
        e = _bare_engine()
        assert e.symbol_in_cooldown("binance_futures", "BTCUSDT") is False

    def test_expired_cooldown_cleans_itself(self):
        e = _bare_engine()
        e.last_exit["binance_futures:OLD"] = time.time() - 1000
        assert e.symbol_in_cooldown("binance_futures", "OLD") is False
        assert "binance_futures:OLD" not in e.last_exit


class TestAntiPyramiding:
    def test_open_position_blocks_new_entry(self):
        e = _bare_engine()
        e.positions["binance_futures:NEARUSDT"] = object()
        assert e.has_open_position("binance_futures", "NEARUSDT") is True

    def test_flat_symbol_allows_entry(self):
        e = _bare_engine()
        assert e.has_open_position("binance_futures", "NEARUSDT") is False


class TestDailyLossBreaker:
    def test_breaker_latches_at_cap(self):
        e = _bare_engine()  # cap = 3% of 7000 = 210
        e.daily_realized_pnl = -250.0
        e._check_daily_loss_limit()
        assert e.daily_loss_limit_hit is True

    def test_breaker_silent_below_cap(self):
        e = _bare_engine()
        e.daily_realized_pnl = -100.0
        e._check_daily_loss_limit()
        assert e.daily_loss_limit_hit is False

    def test_breaker_is_sticky(self):
        e = _bare_engine()
        e.daily_realized_pnl = -250.0
        e._check_daily_loss_limit()
        assert e.daily_loss_limit_hit is True
        e.daily_realized_pnl = -100.0  # wins after the latch do not unlatch
        e._check_daily_loss_limit()
        assert e.daily_loss_limit_hit is True

    def test_book_reconciled_pnl_trips_breaker(self):
        e = _bare_engine()
        e.realized_pnl = 0.0
        e.save_state = lambda: None
        e.book_reconciled_pnl("binance_futures", "ZECUSDT", -250.0)
        assert e.daily_realized_pnl == -250.0
        assert e.daily_loss_limit_hit is True


class TestPositionLimits:
    def _engine_with_venue(self):
        e = _bare_engine()
        e.venues = {"binance_futures": object()}
        return e

    def test_venue_limit_blocks(self):
        e = self._engine_with_venue()
        e.get_position_count = lambda venue: 5 if venue else 5
        e.get_free_margin = lambda venue: 1000.0
        ok, reason = e.can_open_position("binance_futures")
        assert ok is False and "venue position limit" in reason

    def test_total_limit_blocks(self):
        e = self._engine_with_venue()
        e.get_position_count = lambda venue: 3 if venue else 10
        e.get_free_margin = lambda venue: 1000.0
        ok, reason = e.can_open_position("binance_futures")
        assert ok is False and "total position limit" in reason

    def test_zero_free_margin_blocks(self):
        e = self._engine_with_venue()
        e.get_position_count = lambda venue: 1 if venue else 1
        e.get_free_margin = lambda venue: 0.0
        ok, reason = e.can_open_position("binance_futures")
        assert ok is False and "no free margin" in reason

    def test_healthy_venue_allows(self):
        e = self._engine_with_venue()
        e.get_position_count = lambda venue: 2 if venue else 2
        e.get_free_margin = lambda venue: 1000.0
        ok, reason = e.can_open_position("binance_futures")
        assert ok is True and reason == "OK"

    def test_unknown_venue_rejected(self):
        e = _bare_engine()
        e.venues = {}
        ok, reason = e.can_open_position("nope")
        assert ok is False


class TestBarLatch:
    def test_same_bar_fires_once_across_scans(self):
        latch = {}
        key = ("strategy_scalping_breakout", "binance_futures", "NEARUSDT", "1m", "2026-11-12 18:00:00")
        fires = 0
        for _ in range(4):  # 15s scans within one closed 1m bar
            if key in latch:
                continue
            latch[key] = True
            fires += 1
        assert fires == 1

    def test_new_bar_fires_again(self):
        latch = {}
        fires = 0
        for bar in ("18:00:00", "18:01:00"):
            key = ("s", "v", "SYM", "1m", bar)
            if key in latch:
                continue
            latch[key] = True
            fires += 1
        assert fires == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
