"""Tests for TASK-IG2-STR-16 risk_governor (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.risk_governor import (
    DEFAULT_MAX_HEAT_PCT,
    DEFAULT_RISK_PER_TRADE_PCT,
    RiskGovernor,
)

EQ = 100_000.0  # per-trade cap 100.0, heat cap 2000.0 at the defaults


def test_defaults_mirror_fwd006_fractions():
    # Parity is a documentation claim about the decided package, so pin it.
    assert DEFAULT_RISK_PER_TRADE_PCT == 0.001
    assert DEFAULT_MAX_HEAT_PCT == 0.02
    g = RiskGovernor(EQ)
    assert g.risk_per_trade_pct == 0.001
    assert g.max_heat_pct == 0.02
    assert g.max_trades_per_engine is None


def test_validation():
    for bad in (
        lambda: RiskGovernor(0),
        lambda: RiskGovernor(-5),
        lambda: RiskGovernor(EQ, risk_per_trade_pct=0),
        lambda: RiskGovernor(EQ, risk_per_trade_pct=1.5),
        lambda: RiskGovernor(EQ, max_heat_pct=-0.1),
        lambda: RiskGovernor(EQ, max_heat_pct=1.5),
        lambda: RiskGovernor(EQ, max_trades_per_engine=0),
        lambda: RiskGovernor(EQ, max_trades_per_engine=-2),
        lambda: RiskGovernor(EQ, max_trades_per_engine=2.5),
        lambda: RiskGovernor(EQ, on_breach="not-callable"),
    ):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")


def test_per_trade_cap():
    g = RiskGovernor(EQ)
    assert g.check_trade("a", 100.0) == (True, "ok")  # exactly at cap: allowed
    assert g.check_trade("a", 100.01) == (False, "per_trade_cap")
    assert g.approve_trade("a", 100.01) is False
    assert g.trades_taken("a") == 0  # a rejection books nothing
    assert g.approve_trade("a", 100.0) is True
    assert g.trades_taken("a") == 1
    assert g.open_risk("a") == 100.0


def test_invalid_risk_rejected_without_state_change():
    g = RiskGovernor(EQ)
    for bad_amount in (0, -1.0):
        assert g.check_trade("a", bad_amount) == (False, "invalid_risk")
        assert g.approve_trade("a", bad_amount) is False
    assert g.trades_taken("a") == 0
    assert g.open_risk() == 0.0


def test_heat_cap_is_shared_across_engines_and_frees_on_close():
    g = RiskGovernor(EQ)
    # 20 trades of 100.0 fill the 2000.0 heat cap exactly.
    for i in range(20):
        assert g.approve_trade("e%d" % (i % 2), 100.0) is True
    assert g.heat() == 0.02
    assert g.check_trade("e0", 100.0) == (False, "heat_cap")
    assert g.approve_trade("e0", 100.0) is False
    # Closing frees heat; the same trade is then allowed.
    assert g.register_close("e0", 100.0) == 100.0
    assert g.approve_trade("e0", 100.0) is True


def test_trade_count_cap_breach_callback_fires_once_and_latches():
    events = []
    g = RiskGovernor(EQ, max_trades_per_engine=2, on_breach=events.append)
    assert g.approve_trade("x", 10.0) is True
    assert g.approve_trade("x", 10.0) is True
    assert g.trades_remaining("x") == 0
    assert g.check_trade("x", 10.0) == (False, "trade_count_cap")
    assert g.approve_trade("x", 10.0) is False  # the breaching attempt
    assert g.is_blocked("x") is True
    assert len(events) == 1
    assert events[0]["engine"] == "x"
    assert events[0]["kind"] == "trade_count_cap"
    assert events[0]["trades_taken"] == 2
    assert events[0]["cap"] == 2
    assert g.breaches == events
    # Latched: further attempts are engine_blocked and never re-fire.
    assert g.check_trade("x", 10.0) == (False, "engine_blocked")
    assert g.approve_trade("x", 10.0) is False
    assert len(events) == 1
    assert g.trades_taken("x") == 2


def test_count_cap_is_per_engine_not_global():
    g = RiskGovernor(EQ, max_trades_per_engine=1)
    assert g.approve_trade("a", 10.0) is True
    assert g.approve_trade("a", 10.0) is False
    assert g.is_blocked("a") is True
    assert g.is_blocked("b") is False
    assert g.approve_trade("b", 10.0) is True


def test_uncapped_engine_never_blocks():
    g = RiskGovernor(EQ)
    for _ in range(50):
        assert g.approve_trade("u", 10.0) is True
        g.register_close("u", 10.0)
    assert g.trades_taken("u") == 50
    assert g.trades_remaining("u") is None
    assert g.is_blocked("u") is False
    assert g.breaches == []


def test_reset_engine_clears_latch_and_allows_a_new_breach():
    events = []
    g = RiskGovernor(EQ, max_trades_per_engine=1, on_breach=events.append)
    assert g.approve_trade("x", 10.0) is True
    assert g.approve_trade("x", 10.0) is False
    assert g.is_blocked("x") is True
    g.reset_engine("x")
    assert g.is_blocked("x") is False
    assert g.trades_taken("x") == 0
    assert g.open_risk("x") == 0.0
    assert g.approve_trade("x", 10.0) is True
    assert g.approve_trade("x", 10.0) is False
    assert len(events) == 2  # history is kept; the new session breaches anew
    g.reset_engine("never-seen")  # no-op, must not raise


def test_register_close_semantics():
    g = RiskGovernor(EQ)
    assert g.approve_trade("a", 80.0) is True
    assert g.register_close("a", 30.0) == 30.0
    assert g.open_risk("a") == 50.0
    assert g.register_close("a", 999.0) == 50.0  # never releases more than open
    assert g.open_risk("a") == 0.0
    for bad_call in (
        lambda: g.register_close("ghost", 1.0),
        lambda: g.register_close("a", -1.0),
    ):
        try:
            bad_call()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")


def test_check_trade_does_not_mutate():
    g = RiskGovernor(EQ, max_trades_per_engine=1)
    for _ in range(3):
        assert g.check_trade("a", 10.0) == (True, "ok")
    assert g.trades_taken("a") == 0
    assert g.open_risk() == 0.0
    assert g.snapshot()["engines"] == {}


def test_breach_callback_exception_propagates():
    def boom(_event):
        raise RuntimeError("hook failed")

    g = RiskGovernor(EQ, max_trades_per_engine=1, on_breach=boom)
    assert g.approve_trade("x", 10.0) is True
    try:
        g.approve_trade("x", 10.0)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected the callback's RuntimeError to propagate")
    # The breach itself was still recorded before the hook ran.
    assert g.is_blocked("x") is True
    assert len(g.breaches) == 1


def test_snapshot_shape():
    g = RiskGovernor(EQ, max_trades_per_engine=5)
    assert g.approve_trade("b", 50.0) is True
    assert g.approve_trade("a", 25.0) is True
    snap = g.snapshot()
    assert snap["equity"] == EQ
    assert snap["max_trades_per_engine"] == 5
    assert snap["heat"] == 75.0 / EQ
    assert list(snap["engines"]) == ["a", "b"]  # sorted by engine name
    assert snap["engines"]["a"] == {
        "trades": 1, "open_risk": 25.0, "blocked": False}
    assert snap["breaches"] == []


def test_research_only_no_io_or_production_imports():
    src = Path(__file__).resolve().parents[1].joinpath(
        "risk_governor.py").read_text(encoding="utf-8")
    for forbidden in ("run_daemon", "ccxt", "requests", "socket",
                      "subprocess", "os.environ", "place_order", "urllib"):
        assert forbidden not in src, forbidden
