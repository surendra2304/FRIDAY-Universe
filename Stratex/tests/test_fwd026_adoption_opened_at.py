"""
tests/test_fwd026_adoption_opened_at.py — TASK-STR-FWD-026.

Pins the adoption time-exit clock contract:

1. Restart adoption RESTORES position_opened_at from the tag stream's
   original entry timestamp (the earliest fingerprint-matching tag),
   not the adoption instant. Pre-fix, adopt_existing_positions stamped
   now_ms, so the judged dow_effect max_bars=5 time exit re-anchored
   to every daemon restart (live evidence 2026-11-19: the book entered
   2026-11-17, judged exit 2026-11-22T00:00Z, computed 2026-11-23
   after that morning's restart — and would slip again on the next).
2. Re-adoption is idempotent: the same book adopted by two successive
   daemon generations yields the same opened_at.
3. A dow position whose RESTORED age crosses max_bars fires its time
   exit on the daemon's own evaluation path
   (run_daemon._manage_forward_time_exits), while a younger restored
   position is left alone.
4. A position with NO tag/timestamp in the stream falls back to the
   adoption instant — and logs that fallback at WARNING, never silently.
"""

import logging
import time
import types
from datetime import datetime, timezone

import pytest

from measurement import fill_ledger as fl
from autonomy.multi_venue_engine import MultiVenueEngine

# The live book's BTCUSDT dow_effect entry (book audit 2026-11-19).
ENTRY_TS = datetime(2026, 11, 17, 0, 2, 47, tzinfo=timezone.utc).timestamp()
VENUE = "binance_futures"
BTC_KEY = f"{VENUE}:BTCUSDT"
ETH_KEY = f"{VENUE}:ETHUSDT"


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_FILL_LEDGER_FILE", str(tmp_path / "fills.jsonl"))
    monkeypatch.setenv("STRATEX_POSITION_TAGS_FILE", str(tmp_path / "tags.jsonl"))
    monkeypatch.setenv("STRATEX_MEASUREMENT_ALERTS_FILE", str(tmp_path / "alerts.json"))
    return tmp_path


def _pos(symbol="BTCUSDT", side="LONG", qty=0.0014, entry=64812.8):
    return types.SimpleNamespace(
        symbol=symbol, side=side, quantity=qty, entry_price=entry,
        mark_price=entry, unrealized_pnl=0.0,
    )


class _Adapter:
    base_url = "https://demo-fapi.binance.com"

    def __init__(self, positions):
        self._positions = positions
        self.orders = []
        self.cancelled = []

    def get_positions_or_none(self):
        return list(self._positions)

    def place_order(self, symbol, side, order_type, quantity, **kw):
        self.orders.append((symbol, side, order_type, quantity))
        return {"orderId": 1}

    def cancel_protective_orders(self, symbol):
        self.cancelled.append(symbol)
        return True


def _engine(positions):
    eng = MultiVenueEngine.__new__(MultiVenueEngine)
    eng.venues = {VENUE: _Adapter(positions)}
    eng.positions = {}
    eng.position_opened_at = {}
    eng.position_strategy = {}
    eng.position_timeframe = {}
    return eng


def _dow_tag(symbol="BTCUSDT", qty=0.0014, entry=64812.8, ts=ENTRY_TS, **kw):
    row = {
        "engine": "daemon", "venue": VENUE,
        "venue_env": "https://demo-fapi.binance.com", "symbol": symbol,
        "strategy": "strategy_dow_effect", "timeframe": "1d",
        "side": "LONG", "qty": qty, "entry_price": entry,
        "order_id": "12345", "ts": ts,
    }
    row.update(kw)
    return fl.append_position_tag(row)


def test_adoption_restores_opened_at_from_tag(ledger):
    _dow_tag()
    eng = _engine([_pos()])
    assert eng.adopt_existing_positions() == 1
    assert eng.position_opened_at[BTC_KEY] == int(ENTRY_TS * 1000)


def test_adoption_is_idempotent_across_restarts(ledger):
    _dow_tag()
    first = _engine([_pos()])
    first.adopt_existing_positions()
    second = _engine([_pos()])
    second.adopt_existing_positions()
    assert first.position_opened_at[BTC_KEY] == int(ENTRY_TS * 1000)
    assert second.position_opened_at[BTC_KEY] == first.position_opened_at[BTC_KEY]


def test_earliest_tag_anchors_not_later_corrections(ledger):
    # A later adoption-correction tag for the same position carries a
    # restart-time ts; the clock must still anchor to the open record.
    _dow_tag()
    _dow_tag(ts=ENTRY_TS + 2 * 86400, note="adopted_at_startup_attribution_restored")
    eng = _engine([_pos()])
    eng.adopt_existing_positions()
    assert eng.position_opened_at[BTC_KEY] == int(ENTRY_TS * 1000)


def test_restored_age_fires_dow_time_exit_via_daemon(ledger):
    now = time.time()
    _dow_tag(ts=now - 6 * 86400 + 3600)  # BTC: 5 daily bars have elapsed
    _dow_tag(symbol="ETHUSDT", qty=0.036, entry=1816.86, ts=now - 2 * 86400)
    eng = _engine([
        _pos(),
        _pos(symbol="ETHUSDT", qty=0.036, entry=1816.86),
    ])
    assert eng.adopt_existing_positions() == 2
    # Attribution restoration is what routes both positions to the
    # daemon's dow_effect time-exit management.
    assert eng.position_strategy[BTC_KEY] == "strategy_dow_effect"
    assert eng.position_strategy[ETH_KEY] == "strategy_dow_effect"

    from autonomy.run_daemon import StratexTradingEngine

    daemon = StratexTradingEngine.__new__(StratexTradingEngine)
    daemon.engine = eng
    daemon._last_forward_manage = 0
    daemon._manage_forward_time_exits()

    adapter = eng.venues[VENUE]
    assert adapter.orders == [("BTCUSDT", "SELL", "MARKET", 0.0014)]
    assert adapter.cancelled == ["BTCUSDT"]


def test_missing_tag_falls_back_to_now_and_warns(ledger, caplog):
    eng = _engine([_pos()])
    before_ms = int(time.time() * 1000)
    with caplog.at_level(logging.WARNING, logger="multi_venue_engine"):
        assert eng.adopt_existing_positions() == 1
    after_ms = int(time.time() * 1000)
    opened = eng.position_opened_at[BTC_KEY]
    assert before_ms <= opened <= after_ms
    warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "no tag timestamp" in r.getMessage()
    ]
    assert warnings, "fallback to adoption time must be logged at WARNING"
    assert BTC_KEY in warnings[0].getMessage()
