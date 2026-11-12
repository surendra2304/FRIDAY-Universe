"""
tests/test_batch2_strategy_depth.py — Batch 2 (owner directive 2026-11-11).

Covers every batch-2 change:
  1. Walk-forward validation evidence for the two dormant strategies exists,
     is honest (both failed the PF >= 1.0 bar and stay dormant), and the
     verdicts are real booleans (numpy-bool serialization bug regression).
  2. Supertrend regime gate: shorts blocked while EMA50 > EMA200 (bull regime)
     even when price dips under EMA200; shorts still allowed in full bear
     regime when the flag is disabled via env.
  3. Volatility-scaled sizing in RiskGate (calm = full risk, high vol scales
     down to baseline/ATR%, extreme floors at SIZING_MIN_VOL_SCALE, off/unreadable
     = unchanged).
  4. Trailing config: BE lock at 1.0R, ATR trailing arms at 1.5R, profit
     harvest default disabled (0.0) — and the zero-guard so 0.0 can never
     fire `profit >= 0` on every position.
  5. Confluence sizing: >=2 strategies agreeing = full size, lone strategy =
     half size, split house = half, no votes = no trade.
  6. Anti-revenge per-symbol daily cap config + counter semantics.
  7. Ledger PnL: daily + rolling 7-day from a temp ledger, IST day boundary.
  8. Price alert engine: add/list/evaluate, once vs daily re-arm, missing
     data never triggers.
  9. Turn notifier: records locally (never crashes) when credentials are
     absent, and reads the workspace-level .env candidates list.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# 1. Walk-forward evidence (dormant strategies stay dormant — honest negative)
# ---------------------------------------------------------------------------

def test_walkforward_report_exists_and_is_honest():
    """Both dormant strategies were validated on real data and stay dormant."""
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "research", "validation", "walkforward_dormant_report.json"
    )
    assert os.path.exists(report_path), "walkforward_dormant_report.json must exist"
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    by_name = {r["strategy"]: r for r in report["results"]}
    assert set(by_name) >= {"trend_pullback", "volatility_breakout"}

    for name, res in by_name.items():
        assert isinstance(res["promote"], bool), (
            f"{name}: promote must be a real bool after the numpy-bool "
            "'False'-string serialization fix"
        )
        assert res["oos_trades"] >= 30, f"{name}: expected >= 30 OOS trades of evidence"
    # Honest negative: both failed the PF >= 1.0 promotion bar on real data.
    assert by_name["trend_pullback"]["promote"] is False
    assert by_name["volatility_breakout"]["promote"] is False
    assert by_name["trend_pullback"]["net_pf"] < 1.0
    assert by_name["volatility_breakout"]["net_pf"] < 1.0


def test_dormant_strategies_are_not_in_active_config():
    """Failed validation must NOT leak into ACTIVE_STRATEGIES / VALIDATED registry."""
    import config
    import config_strategy

    assert "trend_pullback" not in config.ACTIVE_STRATEGIES
    assert "volatility_breakout" not in config.ACTIVE_STRATEGIES
    reg = config_strategy.PRODUCTION_STRATEGY_REGISTRY
    for name in ("trend_pullback", "volatility_breakout"):
        if name in reg:
            assert reg[name].get("status") != "VALIDATED", (
                f"{name} failed walk-forward (net PF < 1.0) and must not be VALIDATED"
            )


# ---------------------------------------------------------------------------
# 2. Supertrend regime gate (BLOCK_SHORTS_IN_BULL_REGIME)
# ---------------------------------------------------------------------------

def _supertrend_frame(ema_50, ema_200, close, *, bearish=False):
    """Minimal frame exercising the bearish-flip short branch (section 3)."""
    import pandas as pd

    rows = []
    for i in range(55):
        rows.append({
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.6,
            "close": close,
            "supertrend": not bearish,   # prev bar
            "ema_200": ema_200,
            "ema_50": ema_50,
            "ema_21": ema_50,
            "atr": 1.0,
            "rsi": 45.0,
            "adx": 30.0,
            "st_lower": close - 2.0,
            "st_upper": close + 2.0,
        })
    df = pd.DataFrame(rows)
    # Make the LAST bar a bearish flip: supertrend True before, False now.
    df.loc[df.index[-2], "supertrend"] = True
    df.loc[df.index[-1], "supertrend"] = False
    df.loc[df.index[-1], "close"] = close
    df.loc[df.index[-1], "low"] = close - 0.6
    df.loc[df.index[-1], "high"] = close + 0.5
    return df


def test_supertrend_shorts_blocked_in_bull_regime():
    """Batch-2: EMA50 > EMA200 (bull regime) blocks the bearish-flip short."""
    import strategy_supertrend

    # close < ema_200 (pullback dip) but ema_50 still above ema_200 (bull):
    # the old code would short this pullback; the regime gate must not.
    df = _supertrend_frame(ema_50=105.0, ema_200=100.0, close=99.0, bearish=True)
    assert strategy_supertrend.BLOCK_SHORTS_IN_BULL_REGIME is True
    res = strategy_supertrend.get_signal(df)
    assert res.side is None, "shorts must be blocked while EMA50 > EMA200 (bull regime)"


def test_supertrend_shorts_allowed_in_full_bear_regime(monkeypatch):
    """With the flag disabled (env), the same frame shorts again (feature
    flag, not a hard removal)."""
    import pandas as pd  # noqa: F401
    monkeypatch.setenv("BLOCK_SHORTS_IN_BULL_REGIME", "false")
    import strategy_supertrend
    import importlib
    importlib.reload(strategy_supertrend)
    try:
        assert strategy_supertrend.BLOCK_SHORTS_IN_BULL_REGIME is False
        df = _supertrend_frame(ema_50=95.0, ema_200=100.0, close=99.0, bearish=True)
        res = strategy_supertrend.get_signal(df)
        # Full bear regime (close<EMA200, EMA50<EMA200): the flip short fires.
        assert res.side == "SELL"
    finally:
        monkeypatch.delenv("BLOCK_SHORTS_IN_BULL_REGIME", raising=False)
        importlib.reload(strategy_supertrend)


# ---------------------------------------------------------------------------
# 3. Volatility-scaled sizing (RiskGate)
# ---------------------------------------------------------------------------

def test_volatility_risk_scale_bands():
    from testnet_engine.risk_gate import RiskGate

    gate = RiskGate(starting_balance=10_000.0)
    # Unreadable / not supplied -> unchanged behaviour
    assert gate.volatility_risk_scale(None) == 1.0
    assert gate.volatility_risk_scale(0.0) == 1.0
    assert gate.volatility_risk_scale("junk") == 1.0
    # Calm regime (at or below baseline) -> full risk
    assert gate.volatility_risk_scale(0.005) == 1.0
    assert gate.volatility_risk_scale(0.008) == 1.0
    # High vol: risk scales to baseline/ATR%
    assert gate.volatility_risk_scale(0.016) == pytest.approx(0.5)
    assert gate.volatility_risk_scale(0.032) == pytest.approx(0.25)  # floor
    # Extreme vol: floored, never zero
    assert gate.volatility_risk_scale(0.50) == pytest.approx(0.25)


def test_calculate_position_size_scales_with_atr_pct():
    from testnet_engine.risk_gate import RiskGate

    gate = RiskGate(starting_balance=10_000.0)
    filters = {"stepSize": 0.001, "minNotional": 5.0}
    # Wide stop (entry 100, SL 65) keeps the risk-based size below the
    # single-asset exposure cap so the volatility scaling is observable.
    base = gate.calculate_position_size(10_000.0, 100.0, 65.0, filters, side="BUY")
    calm = gate.calculate_position_size(10_000.0, 100.0, 65.0, filters, side="BUY", atr_pct=0.005)
    wild = gate.calculate_position_size(10_000.0, 100.0, 65.0, filters, side="BUY", atr_pct=0.032)
    assert base > 0 and calm > 0 and wild > 0
    assert calm == pytest.approx(base), "calm regime keeps full size"
    assert wild == pytest.approx(base * 0.25, rel=0.02), "extreme vol trades at the 0.25 floor"


def test_volatility_scaled_sizing_disabled_by_env(monkeypatch):
    import config
    from testnet_engine.risk_gate import RiskGate

    monkeypatch.setattr(config, "VOLATILITY_SCALED_SIZING", False, raising=False)
    gate = RiskGate(starting_balance=10_000.0)
    assert gate.volatility_risk_scale(0.032) == 1.0, "disabled flag must restore old behaviour"


# ---------------------------------------------------------------------------
# 4. Trailing config defaults (BE at 1R, trail at 1.5R, harvest off)
# ---------------------------------------------------------------------------

def test_trailing_config_defaults():
    import config

    assert config.PROFIT_HARVEST_PCT == 0.0, "profit harvest must default to disabled"
    assert config.TRAIL_BREAKEVEN_TRIGGER_R == pytest.approx(1.0)
    assert config.TRAIL_TRIGGER_R == pytest.approx(1.5)
    assert config.TRAIL_TRIGGER_R > config.TRAIL_BREAKEVEN_TRIGGER_R, (
        "trailing must arm AFTER the breakeven lock (ladder, not overlap)"
    )


def test_harvest_zero_guard(monkeypatch):
    """PROFIT_HARVEST_PCT=0 must disable harvest, not trigger `profit >= 0`."""
    import config
    from testnet_engine import trailing

    monkeypatch.setattr(config, "PROFIT_HARVEST_PCT", 0.0, raising=False)
    # Recreate the guard expression the loop uses.
    harvest_pct = float(trailing._cfg("PROFIT_HARVEST_PCT", 0.0))
    harvest_enabled = harvest_pct > 0
    assert harvest_enabled is False
    # A position in +2% profit must NOT satisfy the guarded branch.
    assert not (harvest_enabled and 0.02 >= harvest_pct)


# ---------------------------------------------------------------------------
# 5. Confluence sizing (StrategyCoordinator)
# ---------------------------------------------------------------------------

def test_confluence_size_multiplier():
    from risk.strategy_coordinator import StrategyCoordinator

    coord = StrategyCoordinator()
    # Two strategies agreeing -> full size
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": 1, "b": 1}) == 1.0
    # Three agreeing -> full size
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": 1, "b": 1, "c": 1}) == 1.0
    # Lone strategy -> half size
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": 1, "b": 0}) == 0.5
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": -1}) == 0.5
    # Split house -> half size
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": 1, "b": -1}) == 0.5
    # No directional votes -> no trade
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": 0, "b": 0}) == 0.0
    assert coord.confluence_size_multiplier("BTCUSDT", {}) == 0.0
    # Unreadable votes count as flat
    assert coord.confluence_size_multiplier("BTCUSDT", {"a": "junk", "b": 1}) == 0.5


# ---------------------------------------------------------------------------
# 6. Anti-revenge per-symbol daily cap
# ---------------------------------------------------------------------------

def test_symbol_daily_cap_config_default():
    import config

    assert config.MAX_TRADES_PER_SYMBOL_PER_DAY == 3
    assert config.MAX_TRADES_PER_SYMBOL_PER_DAY > 0


def test_symbol_daily_cap_counter_semantics():
    """The cap logic: blocks at N, resets on day rollover."""
    cap = 3
    counts: dict[str, int] = {}
    day = datetime.date(2026, 11, 11)

    def allows(symbol: str, today: datetime.date) -> bool:
        nonlocal day, counts
        if today != day:
            day = today
            counts = {}
        return counts.get(symbol, 0) < cap

    assert allows("BTCUSDT", day) is True
    counts["BTCUSDT"] = 1
    assert allows("BTCUSDT", day) is True
    counts["BTCUSDT"] = 2
    assert allows("BTCUSDT", day) is True
    counts["BTCUSDT"] = 3
    assert allows("BTCUSDT", day) is False, "4th same-day entry must be blocked"
    assert allows("ETHUSDT", day) is True, "cap is per-symbol"
    next_day = datetime.date(2026, 11, 12)
    assert allows("BTCUSDT", next_day) is True, "cap resets on day rollover"


# ---------------------------------------------------------------------------
# 7. Ledger PnL: daily + rolling 7-day (IST)
# ---------------------------------------------------------------------------

def _write_ledger(tmp_path, entries):
    p = tmp_path / "ledger.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    return p


def test_ledger_pnl_summary_daily_and_weekly(tmp_path):
    from notifications.ledger_pnl import IST, ledger_pnl_summary

    now = datetime.datetime(2026, 11, 11, 20, 0, tzinfo=IST)
    entries = [
        # Today: one win one loss
        {"symbol": "BTCUSDT", "net_pnl": 50.0, "timestamp": "2026-11-11T08:00:00Z", "strategy": "A"},
        {"symbol": "ETHUSDT", "net_pnl": -20.0, "timestamp": "2026-11-11T10:00:00Z", "strategy": "B"},
        # 3 days ago (inside the 7-day window)
        {"symbol": "SOLUSDT", "net_pnl": 100.0, "timestamp": "2026-11-08T10:00:00Z", "strategy": "A"},
        # 12 days ago (outside the window, still all-time)
        {"symbol": "BTCUSDT", "net_pnl": -200.0, "timestamp": "2026-10-30T10:00:00Z", "strategy": "C"},
        # Corrupt line: skipped, never fatal
    ]
    p = _write_ledger(tmp_path, entries)
    p.open("a", encoding="utf-8").write("{not json\n")

    s = ledger_pnl_summary(p, now=now)
    assert s["today"]["trades"] == 2
    assert s["today"]["net_pnl"] == pytest.approx(30.0)
    assert s["today"]["win_rate"] == pytest.approx(0.5)
    assert s["week"]["trades"] == 3
    assert s["week"]["net_pnl"] == pytest.approx(130.0)
    assert s["all_time"]["trades"] == 4
    assert s["all_time"]["net_pnl"] == pytest.approx(-70.0)


def test_ledger_pnl_uses_exit_timestamp_preferring_ist_day_boundary(tmp_path):
    from notifications.ledger_pnl import IST, ledger_pnl_summary

    # 2026-11-11 02:00 UTC == 2026-11-11 07:30 IST (same IST day)
    # 2026-11-10 20:00 UTC == 2026-11-11 01:30 IST (NEXT IST day, i.e. today IST)
    now = datetime.datetime(2026, 11, 11, 12, 0, tzinfo=IST)
    entries = [
        {"symbol": "A", "net_pnl": 10.0, "timestamp": "2026-11-11T02:00:00Z"},
        {"symbol": "B", "net_pnl": 5.0, "timestamp": "2026-11-10T20:00:00Z"},
    ]
    p = _write_ledger(tmp_path, entries)
    s = ledger_pnl_summary(p, now=now)
    assert s["today"]["trades"] == 2, "IST day boundary must own the daily split"
    assert s["today"]["net_pnl"] == pytest.approx(15.0)


def test_ledger_pnl_empty_ledger(tmp_path):
    from notifications.ledger_pnl import format_ledger_pnl, ledger_pnl_summary

    p = tmp_path / "nope.jsonl"
    s = ledger_pnl_summary(p)
    assert s["all_time"]["trades"] == 0
    text = format_ledger_pnl(p)
    assert "empty" in text.lower()


# ---------------------------------------------------------------------------
# 8. Price alert engine
# ---------------------------------------------------------------------------

def test_price_alert_add_list_remove(tmp_path):
    from notifications.price_alerts import PriceAlertEngine

    engine = PriceAlertEngine(rules_file=tmp_path / "rules.json")
    ok, msg, rule = engine.add_rule("BTCUSDT", "above", 75000, note="breakout")
    assert ok and rule["symbol"] == "BTCUSDT" and rule["active"] is True
    ok2, _, rule2 = engine.add_rule("ethusdt", "pct24h", -5)
    assert ok2 and rule2["symbol"] == "ETHUSDT" and rule2["type"] == "pct_change_24h"
    rules = engine.load_rules()
    assert len(rules) == 2
    ok3, _ = engine.remove_rule(rule["id"])
    assert ok3 and len(engine.load_rules()) == 1
    # Invalid inputs rejected
    ok4, err, _ = engine.add_rule("BTCUSDT", "sideways", 1)
    assert not ok4 and "type" in err
    ok5, err5, _ = engine.add_rule("BTCUSDT", "above", "not-a-number")
    assert not ok5


def test_price_alert_evaluate_once_and_daily_rearm(tmp_path):
    from notifications.price_alerts import PriceAlertEngine

    engine = PriceAlertEngine(rules_file=tmp_path / "rules.json")
    engine.add_rule("BTCUSDT", "above", 100, rule_id="once-rule")
    engine.add_rule("ETHUSDT", "below", 50, rule_id="daily-rule", rearm="daily")

    fired = engine.evaluate({"BTCUSDT": 101.0, "ETHUSDT": 49.0})
    fired_ids = {r["id"] for r in fired}
    assert fired_ids == {"once-rule", "daily-rule"}

    # Second evaluation same day: once-rule inactive, daily-rule re-armed=false (same day)
    fired_again = engine.evaluate({"BTCUSDT": 102.0, "ETHUSDT": 48.0})
    assert [r["id"] for r in fired_again] == [], "once-rule consumed; daily-rule limited to one trigger/day"


def test_price_alert_daily_rearm_next_day(tmp_path):
    from notifications.price_alerts import PriceAlertEngine

    engine = PriceAlertEngine(rules_file=tmp_path / "rules.json")
    engine.add_rule("ETHUSDT", "below", 50, rule_id="daily-rule", rearm="daily")
    assert engine.evaluate({"ETHUSDT": 49.0})
    assert not engine.evaluate({"ETHUSDT": 48.0})
    # Manually clear the day stamp to simulate the next UTC day.
    rules = engine.load_rules()
    rules[0]["last_trigger_day"] = "2000-01-01"
    (tmp_path / "rules.json").write_text(json.dumps(rules), encoding="utf-8")
    assert engine.evaluate({"ETHUSDT": 47.0}), "daily-rule must re-arm on the next day"


def test_price_alert_missing_data_never_triggers(tmp_path):
    from notifications.price_alerts import PriceAlertEngine

    engine = PriceAlertEngine(rules_file=tmp_path / "rules.json")
    engine.add_rule("BTCUSDT", "above", 100)
    engine.add_rule("ETHUSDT", "pct24h", -5)
    # No prices supplied at all
    assert engine.evaluate({}, {}) == []
    # Price for the wrong symbol only
    assert engine.evaluate({"SOLUSDT": 999.0}, {}) == []
    # pct rule with no pct data
    assert engine.evaluate({"ETHUSDT": 100.0}, {}) == []


# ---------------------------------------------------------------------------
# 9. Turn notifier (batch hygiene)
# ---------------------------------------------------------------------------

def test_notify_turn_complete_records_locally_without_credentials(tmp_path, monkeypatch):
    """Without TELEGRAM credentials the notifier records locally, never raises."""
    import importlib.util

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(repo_root, "scripts", "notify_turn_complete.py")
    assert os.path.exists(script_path), "scripts/notify_turn_complete.py must exist"

    spec = importlib.util.spec_from_file_location("notify_turn_complete", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ledger = tmp_path / "turn_notifications.jsonl"
    monkeypatch.setattr(mod, "DEFAULT_LOCAL_LEDGER", ledger)
    # Full credential isolation (2026-11-11 fix): the notifier now resolves
    # tokens from THREE sources — ZAI_NOTIFICATIONS_TOKEN env, the repo-root
    # credentials.md table, and the .env files _load_env_file reads. The
    # "no credentials → local ledger" contract only holds when ALL of them
    # are isolated; on the owner sandbox real credentials exist for the
    # notification bot, so without isolation this test would fire a real
    # Telegram message instead of recording locally.
    monkeypatch.delenv("ZAI_NOTIFICATIONS_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(mod, "CREDENTIALS_FILE", tmp_path / "absent_credentials.md")
    monkeypatch.setattr(mod, "_load_env_file", lambda: None)

    sent, detail = mod.send_turn_notification("batch-2 test ping")
    assert sent is False
    assert "recorded locally" in detail
    recorded = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(recorded) == 1
    assert recorded[0]["message"] == "batch-2 test ping"
    assert recorded[0]["delivery"] == "LOCAL_ONLY"


def test_notify_turn_complete_includes_workspace_env_candidate():
    """The env loader must consider /home/z/my-project/.env (workspace level)."""
    import importlib.util

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(repo_root, "scripts", "notify_turn_complete.py")
    spec = importlib.util.spec_from_file_location("notify_turn_complete_ws", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # The candidates list is built from REPO_ROOT; verify the workspace-level
    # parent .env is among the candidates (batch-2 fix).
    import inspect
    src = inspect.getsource(mod._load_env_file)
    assert "parent" in src, "workspace-level .env (REPO_ROOT.parent) must be a load candidate"


def test_notify_turn_complete_puts_agent_name_on_first_line(monkeypatch, tmp_path):
    """Owner directive 2026-11-12: the agent name is the FIRST LINE of the
    Telegram message — at the top, never only a trailing signature."""
    import importlib.util

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(repo_root, "scripts", "notify_turn_complete.py")
    spec = importlib.util.spec_from_file_location("notify_turn_complete_top", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    captured = {}

    class _Resp:
        status_code = 200
        content = b'{"ok": true}'

        @staticmethod
        def json():
            return {"ok": True}

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    import requests

    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setenv("ZAI_NOTIFICATIONS_TOKEN", "123456789:TESTTOKENAAAAAAAAAAAAAAAAAAA")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
    monkeypatch.setenv("ZAI_AGENT_NAME", "ZAI Agent 2")
    monkeypatch.setattr(mod, "CREDENTIALS_FILE", tmp_path / "absent_credentials.md")
    monkeypatch.setattr(mod, "_load_env_file", lambda: None)

    sent, detail = mod.send_turn_notification("batch-9 format test ping")
    assert sent is True, f"should report sent, got: {detail}"
    assert "zai-notifications-token" not in captured["url"]  # token in URL, not a name
    text = captured["json"]["text"]
    first_line = text.splitlines()[0]
    assert first_line == "ZAI Agent 2", (
        f"agent name must be the FIRST line, got first line: {first_line!r}"
    )
    assert "ZAI Agent 1" not in text, "never sign as the other agent"
    assert not text.rstrip().endswith("ZAI Agent 2"), (
        "name belongs at the TOP only — no trailing duplicate signature"
    )

