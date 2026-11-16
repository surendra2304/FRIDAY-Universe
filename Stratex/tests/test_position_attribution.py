"""
tests/test_position_attribution.py — TASK-STR-FWD-008.

Pins the position-tag adoption contract:

1. Restart adoption RESTORES attribution for a position the daemon
   itself opened (its open tag is in the tag stream): position_strategy
   / position_timeframe are set again, so a later close books to the
   strategy — never to UNATTRIBUTED, and never to nobody (the
   reconciler's FWD-007 guard leaves unattributed positions to an
   owning engine that, for daemon opens, does not exist).
2. Exactly ONE corrective tag is appended, and only when the newest
   tag does not already carry the restored strategy (a second restart
   must not spam the stream).
3. Another engine's tag is NOT restored into the daemon (FWD-007: the
   owning engine books its own closes) and not re-tagged either.
4. A position the fill ledger already closed is never re-tagged, even
   when the broker still reports it (the trade-470 failure mode: 31
   adopted_at_startup / untracked_detected re-tags after the close).
5. A genuinely foreign position (no tags at all) still gets exactly
   one visible UNATTRIBUTED adoption tag — and no duplicates on the
   next restart.
"""

import types

import pytest

from measurement import fill_ledger as fl
from autonomy.multi_venue_engine import MultiVenueEngine

T0 = 1_794_845_076.0  # 2026-11-16T16:04:36Z — the live TRXUSDT open


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_FILL_LEDGER_FILE", str(tmp_path / "fills.jsonl"))
    monkeypatch.setenv("STRATEX_POSITION_TAGS_FILE", str(tmp_path / "tags.jsonl"))
    monkeypatch.setenv("STRATEX_MEASUREMENT_ALERTS_FILE", str(tmp_path / "alerts.json"))
    return tmp_path


def _pos(symbol="TRXUSDT", side="SHORT", qty=521.0, entry=0.3052):
    return types.SimpleNamespace(
        symbol=symbol, side=side, quantity=qty, entry_price=entry,
        mark_price=entry, unrealized_pnl=0.0,
    )


class _Adapter:
    base_url = "https://demo-fapi.binance.com"

    def __init__(self, positions):
        self._positions = positions

    def get_positions_or_none(self):
        return list(self._positions)


def _engine(positions):
    eng = MultiVenueEngine.__new__(MultiVenueEngine)
    eng.venues = {"binance_futures": _Adapter(positions)}
    eng.positions = {}
    eng.position_opened_at = {}
    eng.position_strategy = {}
    eng.position_timeframe = {}
    return eng


def _tag(**kw):
    row = {
        "engine": "daemon", "venue": "binance_futures",
        "venue_env": "https://demo-fapi.binance.com", "symbol": "TRXUSDT",
        "strategy": "strategy_ichimoku_trend", "timeframe": "4h",
        "side": "SHORT", "qty": 521.0, "entry_price": 0.3052,
        "order_id": "1172178175", "ts": T0,
    }
    row.update(kw)
    return fl.append_position_tag(row)


def _fill(**kw):
    row = {
        "strategy": "strategy_ichimoku_trend", "engine": "daemon",
        "venue": "binance_futures", "symbol": "TRXUSDT", "side": "SHORT",
        "qty": 521.0, "entry_price": 0.3052, "exit_price": 0.3000,
        "gross_pnl": 2.7, "fees": 0.1, "fees_source": "broker",
        "net_pnl": 2.6, "exit_reason": "BROKER_CLOSE",
        "entry_time": T0, "exit_time": T0 + 3600.0, "order_id": "999",
    }
    row.update(kw)
    return fl.append_fill(row)


def test_adoption_restores_daemon_attribution(ledger):
    _tag()  # the daemon's own open tag
    _tag(strategy="UNATTRIBUTED", timeframe="", order_id="",
         note="adopted_at_startup", ts=T0 + 1487.0)  # pre-fix re-tag
    eng = _engine([_pos()])
    assert eng.adopt_existing_positions() == 1
    key = "binance_futures:TRXUSDT"
    assert eng.position_strategy[key] == "strategy_ichimoku_trend"
    assert eng.position_timeframe[key] == "4h"
    tags = fl.read_position_tags()
    assert len(tags) == 3  # exactly one corrective tag appended
    assert tags[-1]["strategy"] == "strategy_ichimoku_trend"
    assert tags[-1]["note"] == "adopted_at_startup_attribution_restored"
    assert tags[-1]["order_id"] == "1172178175"


def test_second_restart_restores_without_new_tag(ledger):
    _tag()
    _tag(strategy="UNATTRIBUTED", timeframe="", order_id="",
         note="adopted_at_startup", ts=T0 + 1487.0)
    _engine([_pos()]).adopt_existing_positions()
    before = fl.read_position_tags()
    eng2 = _engine([_pos()])
    eng2.adopt_existing_positions()
    assert eng2.position_strategy["binance_futures:TRXUSDT"] == "strategy_ichimoku_trend"
    assert fl.read_position_tags() == before  # stream unchanged


def test_foreign_position_gets_one_unattributed_tag(ledger):
    eng = _engine([_pos(symbol="ETHUSDT", side="LONG", qty=0.5, entry=2000.0)])
    eng.adopt_existing_positions()
    assert "binance_futures:ETHUSDT" not in eng.position_strategy
    tags = fl.read_position_tags()
    assert len(tags) == 1
    assert tags[0]["strategy"] == "UNATTRIBUTED"
    assert tags[0]["note"] == "adopted_at_startup"
    # Next restart: already described -> no duplicate tag.
    _engine([_pos(symbol="ETHUSDT", side="LONG", qty=0.5, entry=2000.0)]
            ).adopt_existing_positions()
    assert len(fl.read_position_tags()) == 1


def test_other_engines_tag_is_not_restored(ledger):
    _tag(engine="testnet_engine", strategy="bb_reversion", timeframe="",
         order_id="662723789")
    eng = _engine([_pos()])
    eng.adopt_existing_positions()
    # FWD-007: not the daemon's trade — no restore, no re-tag.
    assert "binance_futures:TRXUSDT" not in eng.position_strategy
    assert len(fl.read_position_tags()) == 1


def test_closed_position_is_never_retagged(ledger):
    # Trade-470 shape: only UNATTRIBUTED sightings exist, and the fill
    # ledger already booked the close. The broker still reports it.
    _tag(venue="oanda", symbol="USDJPY", strategy="UNATTRIBUTED",
         timeframe="", side="LONG", qty=15.0, entry_price=159.691,
         order_id="", note="untracked_detected", ts=T0)
    _fill(venue="oanda", symbol="USDJPY", strategy="strategy_sleeve_tsmom2_dual",
          engine="oanda_sleeve", side="LONG", qty=15.0, entry_price=159.691,
          exit_price=159.691, net_pnl=0.0, exit_time=T0 + 15 * 3600.0)
    eng = MultiVenueEngine.__new__(MultiVenueEngine)
    eng.venues = {"oanda": _Adapter([_pos(symbol="USDJPY", side="LONG",
                                           qty=15.0, entry=159.691)])}
    eng.positions, eng.position_opened_at = {}, {}
    eng.position_strategy, eng.position_timeframe = {}, {}
    eng.adopt_existing_positions()
    assert len(fl.read_position_tags()) == 1  # nothing appended
    assert "oanda:USDJPY" not in eng.position_strategy


def test_daemon_tag_but_already_closed_is_not_restored(ledger):
    _tag()
    _fill()  # closed an hour after the open tag
    eng = _engine([_pos()])  # stale broker read still shows it
    eng.adopt_existing_positions()
    assert "binance_futures:TRXUSDT" not in eng.position_strategy
    assert len(fl.read_position_tags()) == 1


def test_fingerprint_mismatch_does_not_restore(ledger):
    _tag()
    eng = _engine([_pos(qty=999.0)])  # different size: a different position
    eng.adopt_existing_positions()
    assert "binance_futures:TRXUSDT" not in eng.position_strategy


def test_position_closed_in_ledger_units(ledger):
    assert fl.position_closed_in_ledger("binance_futures", "TRXUSDT") is False
    _tag()
    assert fl.position_closed_in_ledger(
        "binance_futures", "TRXUSDT", side="SHORT", qty=521.0,
        entry_price=0.3052) is False
    _fill()
    assert fl.position_closed_in_ledger(
        "binance_futures", "TRXUSDT", side="SHORT", qty=521.0,
        entry_price=0.3052) is True
    # A fill that exited BEFORE the reference open does not close it.
    assert fl.position_closed_in_ledger(
        "binance_futures", "TRXUSDT", since_ts=T0 + 7200.0) is False
