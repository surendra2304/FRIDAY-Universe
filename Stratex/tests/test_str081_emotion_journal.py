"""TASK-STR-081: emotion-aware trade journal — tests.

The journal module is stdlib-only and hermetic: tests build synthetic trades
in-memory and run the real checked-in demo ledger through the same code.
Ledger expectations below are the module's observed output on that fixed
ledger (64 fills, 2026-09-09..2026-09-26); the ledger is checked in, so the
numbers are deterministic. Set STR081_LEDGER to run the ledger leg against
a different copy; CI uses the checked-in file.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from journal import emotion  # noqa: E402

STRATEX_DIR = Path(__file__).resolve().parents[1]
LEDGER = Path(os.environ.get("STR081_LEDGER", STRATEX_DIR / "testnet_trade_ledger.jsonl"))


def _trade(
    symbol="ATOMUSDT",
    ts="2026-09-10T14:00:00Z",
    net=-1.0,
    gross=-1.0,
    fees=0.04,
    qty=50.0,
    entry=1.8,
    order_id="1",
    reason="LOSS",
):
    return emotion.Trade(
        symbol=symbol,
        timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00")),
        net_pnl=net,
        gross_pnl=gross,
        fees=fees,
        quantity=qty,
        entry_price=entry,
        exit_price=entry,
        order_id=order_id,
        exit_reason=reason,
    )


def _ts(base, minutes=0):
    return (datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)).isoformat()


# --- parsing ---------------------------------------------------------------

def test_trade_from_dict_testnet_shape():
    trade = emotion.trade_from_dict({
        "symbol": "SOLUSDT", "order_id": "4199450694", "action": "BUY", "direction": "SHORT",
        "quantity": 1.84, "exit_price": 103.17, "gross_pnl": 0.5696, "net_pnl": 0.4937,
        "fees": 0.0759, "timestamp": "2026-09-09T15:52:32.268000Z",
        "exit_reason": "WIN", "strategy": "SUPERTREND", "entry_price": 103.4796,
    })
    assert trade.symbol == "SOLUSDT"
    assert trade.is_win
    assert trade.notional == pytest.approx(1.84 * 103.4796)
    assert not trade.is_fee_dominated_loss


def test_trade_from_dict_fill_ledger_shape():
    trade = emotion.trade_from_dict({
        "strategy": "SUPERTREND", "engine": "daemon", "venue": "binance", "symbol": "XRPUSDT",
        "side": "SELL", "entry_price": 1.4, "exit_price": 1.36, "qty": 100.0,
        "gross_pnl": 4.0, "fees": 0.08, "net_pnl": 3.92, "exit_reason": "WIN",
        "timestamp": "2026-09-10T13:05:43Z",
    })
    assert trade.is_win and trade.quantity == 100.0 and trade.fees == 0.08


def test_trade_from_dict_rejects_missing_fields():
    with pytest.raises(ValueError):
        emotion.trade_from_dict({"timestamp": "2026-09-10T13:05:43Z", "net_pnl": 1.0})
    with pytest.raises(ValueError):
        emotion.trade_from_dict({"symbol": "XRPUSDT", "timestamp": "not-a-date", "net_pnl": 1.0})
    with pytest.raises(ValueError):
        emotion.trade_from_dict({"symbol": "XRPUSDT", "timestamp": "2026-09-10T13:05:43Z"})


def test_load_jsonl_skips_bad_rows(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        '{"symbol": "XRPUSDT", "timestamp": "2026-09-10T13:05:43Z", "net_pnl": 1.0}\n'
        "not json\n"
        '{"symbol": "XRPUSDT", "timestamp": "2026-09-10T13:06:43Z"}\n'
        "\n"
        '{"symbol": "DOGEUSDT", "timestamp": "2026-09-10T13:07:43Z", "net_pnl": -0.5}\n',
        encoding="utf-8",
    )
    trades, skipped = emotion.load_jsonl(path)
    assert len(trades) == 2 and skipped == 2
    assert [t.symbol for t in trades] == ["XRPUSDT", "DOGEUSDT"]


# --- per-trade emotion tags -------------------------------------------------

def test_fee_churn_tag_only_when_loss_is_the_fee():
    assert any(t.tag == "fee_churn" for t in emotion.analyse_trade(_trade(gross=-0.01, net=-0.05), None, 100.0))
    assert not any(
        t.tag == "fee_churn" for t in emotion.analyse_trade(_trade(gross=-1.0, net=-1.04), None, 100.0)
    )


def test_size_outlier_tag_at_3x_median():
    assert any(t.tag == "size_outlier" for t in emotion.analyse_trade(_trade(qty=200.0, entry=1.8), None, 100.0))
    assert not any(t.tag == "size_outlier" for t in emotion.analyse_trade(_trade(qty=100.0, entry=1.8), None, 100.0))


def test_quick_reentry_after_loss():
    prev = _trade(ts="2026-09-10T14:00:00Z", net=-2.0)
    assert any(
        t.tag == "quick_reentry_after_loss"
        for t in emotion.analyse_trade(_trade(ts="2026-09-10T14:05:00Z"), prev, 100.0)
    )
    assert not any(
        t.tag == "quick_reentry_after_loss"
        for t in emotion.analyse_trade(_trade(ts="2026-09-10T14:30:00Z"), prev, 100.0)
    )
    prev_win = _trade(ts="2026-09-10T14:00:00Z", net=2.0, reason="WIN")
    assert not any(
        t.tag == "quick_reentry_after_loss"
        for t in emotion.analyse_trade(_trade(ts="2026-09-10T14:05:00Z"), prev_win, 100.0)
    )


def test_same_second_batch_is_one_decision_not_reentry():
    prev = _trade(ts="2026-09-10T14:00:00Z", net=-2.0)
    tags = emotion.analyse_trade(_trade(ts="2026-09-10T14:00:00Z"), prev, 100.0)
    assert not any(t.tag in ("quick_reentry_after_loss", "same_symbol_after_loss") for t in tags)


def test_same_symbol_after_loss_and_scale_up_after_win():
    prev = _trade(symbol="DOGEUSDT", ts="2026-09-10T14:00:00Z", net=-1.0)
    tags = emotion.analyse_trade(_trade(symbol="DOGEUSDT", ts="2026-09-10T14:10:00Z"), prev, 100.0)
    assert any(t.tag == "same_symbol_after_loss" for t in tags)
    prev_win = _trade(symbol="DOGEUSDT", ts="2026-09-10T14:00:00Z", net=1.0, reason="WIN", qty=50.0, entry=1.0)
    tags = emotion.analyse_trade(_trade(ts="2026-09-10T14:05:00Z", qty=100.0, entry=1.0), prev_win, 100.0)
    assert any(t.tag == "scale_up_after_win" for t in tags)


# --- patterns on synthetic trades ------------------------------------------

def test_collapse_simultaneous_batch():
    trades = [_trade(ts="2026-09-10T14:00:00Z", order_id="1", net=-1.0),
              _trade(ts="2026-09-10T14:00:00Z", order_id="2", net=-2.0, symbol="XRPUSDT"),
              _trade(ts="2026-09-10T14:00:06Z", order_id="3", net=5.0, symbol="SOLUSDT", reason="WIN")]
    events = emotion.collapse_events(trades)
    assert len(events) == 2
    assert events[0].net_pnl == pytest.approx(-3.0) and not events[0].is_win
    assert events[1].is_win
    # the 2026-09-10 13:05 batch spans 3.9s and collapses to one event
    batch = [_trade(ts="2026-09-10T13:05:40Z", order_id="a", net=7.23, reason="WIN"),
             _trade(ts="2026-09-10T13:05:42Z", order_id="b", net=1.81, symbol="ETHUSDT", reason="WIN"),
             _trade(ts="2026-09-10T13:05:43Z", order_id="c", net=24.04, symbol="XRPUSDT", reason="WIN")]
    assert len(emotion.collapse_events(batch)) == 1


def test_overtrading_burst_threshold():
    trades = [_trade(ts=_ts(0, m), order_id=str(m)) for m in range(0, 64, 8)]
    assert any(p["pattern"] == "OVERTRADING_BURST" for p in emotion.detect_patterns(trades))
    trades = [_trade(ts=_ts(0, m), order_id=str(m)) for m in range(0, 56, 8)]
    assert not any(p["pattern"] == "OVERTRADING_BURST" for p in emotion.detect_patterns(trades))


def test_loss_streak_episode_and_day_gap_break():
    trades = [_trade(ts=_ts(0, h * 60), order_id=str(h)) for h in range(5)]
    patterns = emotion.detect_patterns(trades)
    assert [p for p in patterns if p["pattern"] == "LOSS_STREAK"][0]["count"] == 5
    trades = [_trade(ts=_ts(0, h * 60), order_id=str(h)) for h in range(4)]
    assert not any(p["pattern"] == "LOSS_STREAK" for p in emotion.detect_patterns(trades))
    trades = [_trade(ts=_ts(0, h * 60), order_id=str(h)) for h in range(5)]
    trades.append(_trade(ts=_ts(0, 5 * 60 + 60 * 30), order_id="late"))
    streaks = [p for p in emotion.detect_patterns(trades) if p["pattern"] == "LOSS_STREAK"]
    assert len(streaks) == 1 and streaks[0]["count"] == 5


def test_symbol_chase_needs_consecutive_same_symbol_losses():
    trades = [_trade(symbol="DOGEUSDT", ts=_ts(0, m), order_id=str(m)) for m in (0, 10, 20)]
    assert any(p["pattern"] == "SYMBOL_CHASE" for p in emotion.detect_patterns(trades))
    trades = [
        _trade(symbol="DOGEUSDT", ts=_ts(0, 0), order_id="1"),
        _trade(symbol="DOGEUSDT", ts=_ts(0, 10), order_id="2", net=1.0, reason="WIN"),
        _trade(symbol="DOGEUSDT", ts=_ts(0, 20), order_id="3"),
        _trade(symbol="DOGEUSDT", ts=_ts(0, 30), order_id="4"),
    ]
    assert not any(p["pattern"] == "SYMBOL_CHASE" for p in emotion.detect_patterns(trades))


def test_fee_churn_run_and_fixation():
    trades = [
        _trade(symbol="DOGEUSDT", ts=_ts(0, m), order_id=str(m), gross=-0.01, net=-0.05)
        for m in (0, 30, 60)
    ]
    assert any(p["pattern"] == "FEE_CHURN_RUN" for p in emotion.detect_patterns(trades))
    trades = [
        _trade(symbol="DOGEUSDT", ts=_ts(0, 0), order_id="1"),
        _trade(symbol="DOGEUSDT", ts=_ts(0, 60), order_id="2"),
        _trade(symbol="XRPUSDT", ts=_ts(0, 120), order_id="3", net=5.0, reason="WIN"),
        _trade(symbol="XRPUSDT", ts=_ts(0, 180), order_id="4", net=5.0, reason="WIN"),
    ]
    patterns = emotion.detect_patterns(trades)
    assert any(p["pattern"] == "SYMBOL_FIXATION" and p.get("symbol") == "DOGEUSDT" for p in patterns)
    assert not any(p.get("symbol") == "XRPUSDT" for p in patterns if p["pattern"] == "SYMBOL_FIXATION")


def test_empty_period_is_ok():
    summary = emotion.summarise_period([], "empty")
    assert summary["trades"] == 0 and summary["patterns"] == []
    assert summary["risk"]["level"] == "OK"


# --- the real journal period -------------------------------------------------

def test_real_ledger_period_aggregates():
    if not LEDGER.exists():
        pytest.skip("checked-in demo ledger absent")
    trades, skipped = emotion.load_jsonl(LEDGER)
    assert len(trades) == 64 and skipped == 0
    summary = emotion.summarise_period(trades, "real")
    assert (summary["wins"], summary["losses"]) == (17, 47)
    assert summary["win_rate"] == pytest.approx(0.2656)
    assert summary["net_pnl"] == pytest.approx(22.7084)
    assert summary["gross_pnl"] == pytest.approx(27.5523)
    assert summary["fees"] == pytest.approx(4.8437)
    assert summary["avg_win"] == pytest.approx(4.18)
    assert summary["avg_loss"] == pytest.approx(-1.0288)
    assert summary["profit_factor"] == pytest.approx(1.4697)
    assert summary["median_notional"] == pytest.approx(99.54)
    assert summary["max_win"] == pytest.approx(24.0438)
    assert summary["max_loss"] == pytest.approx(-17.8784)
    assert summary["trades_per_day"] == {
        "2026-09-09": 24, "2026-09-10": 26, "2026-09-12": 9, "2026-09-26": 5,
    }
    assert summary["net_by_symbol"]["ATOMUSDT"] == pytest.approx(-7.7162)
    assert summary["net_by_symbol"]["XRPUSDT"] == pytest.approx(20.3423)


def test_real_ledger_tags_and_patterns():
    if not LEDGER.exists():
        pytest.skip("checked-in demo ledger absent")
    trades, _ = emotion.load_jsonl(LEDGER)
    summary = emotion.summarise_period(trades, "real")
    assert summary["emotion_tag_counts"] == {
        "fee_churn": 18,
        "size_outlier": 8,
        "quick_reentry_after_loss": 7,
        "same_symbol_after_loss": 2,
        "scale_up_after_win": 3,
    }
    assert len(summary["tagged_trades"]) == 31
    kinds = [p["pattern"] for p in summary["patterns"]]
    assert len(summary["patterns"]) == 17
    assert kinds.count("LOSS_STREAK") == 4
    assert max(p["count"] for p in summary["patterns"] if p["pattern"] == "LOSS_STREAK") == 13
    assert kinds.count("FEE_CHURN_RUN") == 2
    assert kinds.count("OVERTRADING_BURST") == 4
    assert kinds.count("OVERTRADING_BURST_10MIN") == 2
    assert kinds.count("SIMULTANEOUS_EXIT") == 1
    assert kinds.count("SYMBOL_CHASE") == 2
    assert kinds.count("SYMBOL_FIXATION") == 1
    assert kinds.count("SIZE_OUTLIERS") == 1
    assert summary["risk"]["level"] == "HIGH"
    assert "13 events" in summary["risk"]["reason"]
    assert len(summary["risk"]["flags"]) == len(summary["patterns"])
    assert len(set(summary["risk"]["flags"])) == len(summary["risk"]["flags"])
    assert "FEE_CHURN_2026-09-10_10" in summary["risk"]["flags"]
    assert "SYMBOL_CHASE_DOGEUSDT_2026-09-10_14:10_5" in summary["risk"]["flags"]
    # the 2026-09-09 batch collapses to one decision event, so that day's
    # loss episode is 7 events, not 8 fills
    assert "LOSS_STREAK_2026-09-09_14:30_7" in summary["risk"]["flags"]


def test_render_markdown_contains_period_risk_and_patterns():
    if not LEDGER.exists():
        pytest.skip("checked-in demo ledger absent")
    trades, _ = emotion.load_jsonl(LEDGER)
    summary = emotion.summarise_period(trades, "2026-09-09..2026-09-26 demo")
    text = emotion.render_markdown(summary)
    assert "2026-09-09..2026-09-26 demo" in text
    assert "Risk: HIGH" in text
    assert "LOSS_STREAK" in text and "FEE_CHURN_RUN" in text
    assert "ATOMUSDT: -7.72" in text
    assert json.dumps(summary)  # summary is JSON-serializable for the risk gate
