"""TASK-STR-FWD-016: sleeve timeframe precedence + deferred entry.

Evidence base (sleeve-conflict analysis, coordinator workspace): 13
contradiction-guard lines in ~21.6h of the S1 daemon journal, every one
"2 symbol(s)", every conflict sleeve SELL (1wk) x dow BUY (1d) on
BTCUSDT/BNBUSDT; the sleeve leg at 0 lifetime executions; dow's BTC/BNB
longs opened anyway in the 2026-11-17 05:32 IST cycle.

Covered behaviour:
  (a) sleeve (1w) vs a lower-timeframe opposing side -> the sleeve side
      survives, the opposing side is dropped for that symbol-cycle, and
      the resolution is journalled per symbol with both strategies,
      both sides, both timeframes (plus the kept aggregate line).
  (b) every other conflict shape keeps the pre-FWD-016 delete-both
      behaviour exactly: non-sleeve conflicts; a sleeve side whose
      opponent carries any weekly signal; the sleeve strategy name at
      a non-weekly timeframe.
  (c) same-direction confluence is untouched (no Conflict lines at all).
  (d) a sleeve candidate blocked by an existing open position is
      deferred, not consumed: it retries on later cycles while its
      weekly bucket is still the last closed bucket, never preempts
      the open position, fills through the real _execute_signal once
      the symbol frees up, and expires — journalled — when the bucket
      rolls over unfilled. A cycle that never scanned the symbol
      neither retries nor expires the entry.
  (e) has_open_position still blocks non-sleeve strategies at the
      execution gate exactly as before, and non-sleeve candidates are
      never deferred.

Fully offline: fake engine (the FWD-012 harness shape), daemon built
with __new__ and injected attributes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from types import SimpleNamespace  # noqa: E402

from autonomy import run_daemon as rd  # noqa: E402
from autonomy.run_daemon import StratexTradingEngine  # noqa: E402

V = "binance_demo_fapi"
SYM = "BTCUSDT"
SLEEVE = rd.SLEEVE_SHOCK_STRATEGY
DOW = "strategy_dow_effect"
ICHI = "strategy_ichimoku_tk_cloud"
BUCKET = "2026-11-09 00:00:00+00:00"
NEXT_BUCKET = "2026-11-16 00:00:00+00:00"


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def info(self, msg, *a):
        self.lines.append(str(msg))

    def warning(self, msg, *a):
        self.lines.append(str(msg))

    def error(self, msg, *a):
        self.lines.append(str(msg))

    def debug(self, msg, *a):
        pass


@pytest.fixture()
def logs(monkeypatch):
    log = _Log()
    monkeypatch.setattr(rd, "logger", log)
    return log.lines


@pytest.fixture()
def _no_pause(monkeypatch):
    # _execute_signal imports these locally and fails CLOSED if they
    # raise, so pin them off in their home modules.
    import panic_state
    import trading_pause

    monkeypatch.setattr(trading_pause, "is_trading_paused", lambda: False)
    monkeypatch.setattr(panic_state, "is_panic_active", lambda: False)
    monkeypatch.setattr(panic_state, "is_kill_switch_locked", lambda: False)


class _Engine:
    """Fake execution engine: flat market at 100, everything filled."""

    def __init__(self):
        self.orders: list[dict] = []
        self.positions: dict = {}
        self.position_strategy: dict = {}
        self.open_positions: set[tuple[str, str]] = set()
        self.can_open = True

    def can_open_position(self, venue):
        return (self.can_open, "limit" if not self.can_open else "")

    def has_open_position(self, venue, symbol):
        return (venue, symbol) in self.open_positions

    def symbol_in_cooldown(self, venue, symbol):
        return False

    def get_ticker(self, venue, symbol):
        return SimpleNamespace(last=100.0, bid=99.99, ask=100.01)

    def get_candles(self, venue, symbol, timeframe, limit=120):
        return [
            {
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1.0,
            }
            for _ in range(30)
        ]

    def get_venue_equity(self, venue):
        return 10_000.0

    def get_free_margin(self, venue):
        return 1_000_000.0

    def place_order(self, **kwargs):
        self.orders.append(kwargs)
        self.open_positions.add((kwargs["venue"], kwargs["symbol"]))
        return SimpleNamespace(
            success=True,
            order_id="fwd016-test",
            status="FILLED",
            venue=kwargs["venue"],
            symbol=kwargs["symbol"],
            side=kwargs["side"],
            quantity=kwargs["quantity"],
            filled_quantity=kwargs["quantity"],
            avg_fill_price=100.0,
            price=100.0,
        )


def _daemon(engine) -> StratexTradingEngine:
    d = StratexTradingEngine.__new__(StratexTradingEngine)
    d.engine = engine
    d.min_stop_pct = 0.005
    d.max_stop_pct = 0.15  # production env value (STRATEX_MAX_STOP_PCT)
    d.risk_per_trade = 0.001
    d.max_heat_pct = 0.02
    d.max_position_pct = 0.10
    d.adx_threshold = 0.0
    d.fee_rate_roundtrip = 0.0008
    d.friction_rate_roundtrip = 0.0016
    d.min_expectancy_r = 0.10
    d.strategy_priors = {SLEEVE: 0.4267, DOW: 0.5227}
    return d


def _sig(name, side, tf, **extra):
    result = {"side": side, "rr_ratio": 2.0, "win_rate_prior": 0.5}
    result.update(extra)
    return (name, result, tf)


def _entry(venue, symbol, side, *sigs):
    return (venue, symbol, side, list(sigs), {s[0] for s in sigs})


def _payload(name, side, tf, **extra):
    payload = {"side": side, "sl_dist": 20.0, "tp_dist": 40.0}
    payload.update(extra)
    payload.update(
        {"strategy": name, "venue": V, "symbol": SYM, "timeframe": tf}
    )
    return payload


def _defer(d, engine, side="SELL"):
    """Seed a deferred sleeve entry the way the execution loop would."""
    engine.open_positions.add((V, SYM))
    d._sleeve_deferral_state()[1][(V, SYM)] = BUCKET
    sigs = [_sig(SLEEVE, side, "1w", sl_dist=22.0, tp_dist=44.0)]
    assert d._maybe_defer_sleeve_candidate(V, SYM, sigs) is True
    deferred, _ = d._sleeve_deferral_state()
    assert (V, SYM) in deferred
    return deferred


# ---------------------------------------------------------------------------
# (a) timeframe precedence: sleeve over the lower-timeframe opposing side
# ---------------------------------------------------------------------------


def test_precedence_sleeve_sell_survives_dow_buy_dropped_and_journalled(logs):
    d = _daemon(_Engine())
    sleeve = _entry(V, SYM, "SELL", _sig(SLEEVE, "SELL", "1w"))
    dow = _entry(V, SYM, "BUY", _sig(DOW, "BUY", "1d"))
    out = d._resolve_contradictions([sleeve, dow])
    assert out == [sleeve]
    per_symbol = [ln for ln in logs if f"Conflict {V}:{SYM}" in ln]
    assert len(per_symbol) == 1
    line = per_symbol[0]
    assert SLEEVE in line and DOW in line
    assert "SELL" in line and "BUY" in line
    assert "1w" in line and "1d" in line
    assert f"precedence-dropped-{DOW}" in line
    # Aggregate line kept, prefix unchanged from the pre-FWD-016 guard.
    assert any(
        ln.startswith("[STRATEX] Conflict: 1 symbol(s) produced both")
        for ln in logs
    )


def test_precedence_sleeve_buy_survives_dow_sell_dropped(logs):
    d = _daemon(_Engine())
    sleeve = _entry(V, SYM, "BUY", _sig(SLEEVE, "BUY", "1w"))
    dow = _entry(V, SYM, "SELL", _sig(DOW, "SELL", "1d"))
    out = d._resolve_contradictions([dow, sleeve])
    assert out == [sleeve]
    assert any(f"precedence-dropped-{DOW}" in ln for ln in logs)


# ---------------------------------------------------------------------------
# (b) every other conflict shape keeps delete-both exactly
# ---------------------------------------------------------------------------


def test_non_sleeve_conflict_still_deletes_both(logs):
    d = _daemon(_Engine())
    ichi = _entry(V, SYM, "SELL", _sig(ICHI, "SELL", "4h"))
    dow = _entry(V, SYM, "BUY", _sig(DOW, "BUY", "1d"))
    assert d._resolve_contradictions([ichi, dow]) == []
    line = next(ln for ln in logs if f"Conflict {V}:{SYM}" in ln)
    assert ICHI in line and DOW in line and "both dropped" in line
    assert "precedence" not in line


def test_sleeve_vs_weekly_opponent_still_deletes_both(logs):
    # The exemption is timeframe precedence: an opposing WEEKLY signal
    # is not lower-timeframe, so the conflict keeps delete-both.
    d = _daemon(_Engine())
    sleeve = _entry(V, SYM, "SELL", _sig(SLEEVE, "SELL", "1w"))
    weekly = _entry(V, SYM, "BUY", _sig(ICHI, "BUY", "1w"))
    assert d._resolve_contradictions([sleeve, weekly]) == []
    assert any("both dropped" in ln for ln in logs)


def test_sleeve_name_at_lower_timeframe_gets_no_precedence(logs):
    # Scoped to the sleeve at its judged timeframe only: the strategy
    # name on a 4h signal does not trigger the exemption.
    d = _daemon(_Engine())
    sleeve_4h = _entry(V, SYM, "SELL", _sig(SLEEVE, "SELL", "4h"))
    dow = _entry(V, SYM, "BUY", _sig(DOW, "BUY", "1d"))
    assert d._resolve_contradictions([sleeve_4h, dow]) == []
    assert any("both dropped" in ln for ln in logs)


def test_sleeve_vs_mixed_timeframe_opposition_deletes_both(logs):
    # Opposing side carrying ANY weekly signal is not "exclusively
    # lower-timeframe" — no precedence.
    d = _daemon(_Engine())
    sleeve = _entry(V, SYM, "SELL", _sig(SLEEVE, "SELL", "1w"))
    mixed = _entry(
        V, SYM, "BUY", _sig(DOW, "BUY", "1d"), _sig(ICHI, "BUY", "1w")
    )
    assert d._resolve_contradictions([sleeve, mixed]) == []
    assert any("both dropped" in ln for ln in logs)


# ---------------------------------------------------------------------------
# (c) same-direction confluence untouched
# ---------------------------------------------------------------------------


def test_same_direction_confluence_untouched(logs):
    d = _daemon(_Engine())
    dow = _entry(V, SYM, "BUY", _sig(DOW, "BUY", "1d"))
    ichi = _entry(V, SYM, "BUY", _sig(ICHI, "BUY", "4h"))
    sleeve_other = _entry(V, "ETHUSDT", "SELL", _sig(SLEEVE, "SELL", "1w"))
    out = d._resolve_contradictions([dow, ichi, sleeve_other])
    assert out == [dow, ichi, sleeve_other]
    assert not any("Conflict" in ln for ln in logs)


def test_no_conflict_passthrough(logs):
    d = _daemon(_Engine())
    assert d._resolve_contradictions([]) == []
    single = _entry(V, SYM, "SELL", _sig(SLEEVE, "SELL", "1w"))
    assert d._resolve_contradictions([single]) == [single]
    assert logs == []


# ---------------------------------------------------------------------------
# (d) deferred entry: capture, retry within the bucket, expiry at rollover
# ---------------------------------------------------------------------------


def test_deferral_created_only_when_position_blocks(logs):
    engine = _Engine()
    d = _daemon(engine)
    sigs = [_sig(SLEEVE, "SELL", "1w", sl_dist=22.0, tp_dist=44.0)]
    # No open position -> the block was another gate; nothing deferred.
    assert d._maybe_defer_sleeve_candidate(V, SYM, sigs) is False
    # Position open but the symbol's bucket was never observed.
    engine.open_positions.add((V, SYM))
    assert d._maybe_defer_sleeve_candidate(V, SYM, sigs) is False
    # Position open + bucket observed -> deferred and journalled.
    d._sleeve_deferral_state()[1][(V, SYM)] = BUCKET
    assert d._maybe_defer_sleeve_candidate(V, SYM, sigs) is True
    deferred, _ = d._sleeve_deferral_state()
    entry = deferred[(V, SYM)]
    assert entry["bucket"] == BUCKET
    assert entry["payload"]["strategy"] == SLEEVE
    assert entry["payload"]["sl_dist"] == 22.0
    assert any("Sleeve deferred:" in ln and SYM in ln for ln in logs)


def test_non_sleeve_candidate_never_deferred(logs):
    engine = _Engine()
    engine.open_positions.add((V, SYM))
    d = _daemon(engine)
    d._sleeve_deferral_state()[1][(V, SYM)] = BUCKET
    sigs = [_sig(DOW, "BUY", "1d", sl_dist=20.0, tp_dist=40.0)]
    assert d._maybe_defer_sleeve_candidate(V, SYM, sigs) is False
    deferred, _ = d._sleeve_deferral_state()
    assert deferred == {}


def test_deferred_retry_waits_while_position_open(logs):
    engine = _Engine()
    d = _daemon(engine)
    deferred = _defer(d, engine)
    calls: list = []
    d._execute_signal = lambda *a: calls.append(a) or True
    results = {"executed": 0}
    d._retry_deferred_sleeve_entries(results)
    # Never preempts: no execution attempt while the position is open.
    assert calls == []
    assert results["executed"] == 0
    assert (V, SYM) in deferred


def test_deferred_entry_expires_at_bucket_rollover(logs):
    engine = _Engine()
    d = _daemon(engine)
    deferred = _defer(d, engine)
    engine.open_positions.clear()  # even with the symbol free...
    d._sleeve_deferral_state()[1][(V, SYM)] = NEXT_BUCKET  # ...rollover wins
    calls: list = []
    d._execute_signal = lambda *a: calls.append(a) or True
    results = {"executed": 0}
    d._retry_deferred_sleeve_entries(results)
    assert calls == []
    assert deferred == {}
    assert any(
        "Sleeve deferred expired:" in ln and BUCKET in ln for ln in logs
    )


def test_deferred_entry_survives_unscanned_cycle(logs):
    engine = _Engine()
    d = _daemon(engine)
    deferred = _defer(d, engine)
    engine.open_positions.clear()
    # A cycle whose scan never observed this symbol: no evidence of
    # rollover, so the entry must neither fire nor expire.
    d._sleeve_deferral_state()[1].clear()
    calls: list = []
    d._execute_signal = lambda *a: calls.append(a) or True
    d._retry_deferred_sleeve_entries({"executed": 0})
    assert calls == []
    assert (V, SYM) in deferred
    assert not any("expired" in ln for ln in logs)


def test_deferred_sleeve_fills_through_real_execute_signal(logs, _no_pause):
    engine = _Engine()
    d = _daemon(engine)
    deferred = _defer(d, engine)
    # The blocking position closes; the bucket is still current.
    engine.open_positions.clear()
    results = {"executed": 0}
    d._retry_deferred_sleeve_entries(results)
    assert results["executed"] == 1
    assert len(engine.orders) == 1
    order = engine.orders[0]
    assert order["symbol"] == SYM
    assert order["side"] == "SELL"
    assert order["strategy_name"] == SLEEVE
    assert deferred == {}
    assert any("Sleeve deferred filled:" in ln for ln in logs)


# ---------------------------------------------------------------------------
# (e) the open-position gate itself is unchanged for everyone
# ---------------------------------------------------------------------------


def test_open_position_still_blocks_execution_for_all(logs, _no_pause):
    engine = _Engine()
    engine.open_positions.add((V, SYM))
    d = _daemon(engine)
    assert d._execute_signal(V, SYM, _payload(DOW, "BUY", "1d"), "1d") is False
    # Precedence lives at the guard, not the position gate: the sleeve
    # is blocked identically here — the deferral is what rescues it.
    assert (
        d._execute_signal(
            V, SYM, _payload(SLEEVE, "SELL", "1w", sl_dist=22.0, tp_dist=44.0),
            "1w",
        )
        is False
    )
    assert engine.orders == []
