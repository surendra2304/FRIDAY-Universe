"""TASK-STR-FWD-018 — lane signal-visibility diagnostic fix.

Finding (2026-11-18, code + production journal + production env):
the three FORWARD_TEST lane modules (strategy_adx_ema_bare,
strategy_bollinger_trend, strategy_shock_breakout) were wired
2026-11-15 and appear in the daemon's governance summary as an
armed forward_test lane — but the production
STRATEX_STRATEGY_ALLOWLIST names only strategy_adx_ema,
strategy_dow_effect, strategy_ichimoku_trend and
strategy_sleeve_shock_breakout. The scan loop skips any discovered
module missing from a non-empty allowlist BEFORE evaluation, with
no log line. Journal evidence (Stratex-Daemon, --since 2026-11-15):
0 evaluation lines for each lane strategy vs 17,251 each for
strategy_ichimoku_trend / strategy_dow_effect; "Signal detected"
lines only for strategy_dow_effect (330) and
strategy_sleeve_shock_breakout (22). The lane was never evaluated,
so it could never signal or fill.

Fix pinned here: _log_governance_summary now logs a WARNING naming
every governed (VALIDATED or FORWARD_TEST) strategy that a
non-empty allowlist excludes, so an allowlist/governance mismatch
is loud at startup instead of invisible for days. The allowlist
semantics themselves are unchanged (it remains an operator
control); the deploy-side remedy — adding the lane module names to
STRATEX_STRATEGY_ALLOWLIST — is recorded in the PR body.
"""

from __future__ import annotations

import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import autonomy.run_daemon as run_daemon

LANE = ["strategy_adx_ema_bare", "strategy_bollinger_trend", "strategy_shock_breakout"]
VALIDATED = ["strategy_dow_effect", "strategy_ichimoku_trend", "strategy_sleeve_shock_breakout"]
# The production allowlist as found on Server 1 on 2026-11-18.
PRODUCTION_ALLOWLIST = {
    "strategy_adx_ema",
    "strategy_dow_effect",
    "strategy_ichimoku_trend",
    "strategy_sleeve_shock_breakout",
}


class _FakeRegistry:
    def snapshot(self):
        specs = [SimpleNamespace(name=n, status="VALIDATED") for n in VALIDATED]
        specs += [SimpleNamespace(name=n, status="FORWARD_TEST") for n in LANE]
        specs += [SimpleNamespace(name="strategy_adx_ema", status="OBSERVE_ONLY")]
        return specs

    def demo_venues(self):
        return frozenset({"binance_futures", "oanda"})


def _engine_with_allowlist(monkeypatch, allowlist):
    monkeypatch.setattr(run_daemon, "strategy_registry", _FakeRegistry())
    engine = run_daemon.StratexTradingEngine.__new__(run_daemon.StratexTradingEngine)
    engine.strategy_allowlist = set(allowlist)
    return engine


def _warnings(caplog):
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING and "Governance WARNING" in r.getMessage()
    ]


def test_production_allowlist_warns_and_names_the_lane(monkeypatch, caplog):
    """The 2026-11-15..18 incident, reproduced: the warning must fire
    and name exactly the three lane modules."""
    engine = _engine_with_allowlist(monkeypatch, PRODUCTION_ALLOWLIST)
    with caplog.at_level(logging.WARNING):
        engine._log_governance_summary()
    msgs = _warnings(caplog)
    assert len(msgs) == 1
    for name in LANE:
        assert name in msgs[0]
    for name in VALIDATED:
        assert name not in msgs[0]


def test_complete_allowlist_no_warning(monkeypatch, caplog):
    engine = _engine_with_allowlist(monkeypatch, set(VALIDATED) | set(LANE))
    with caplog.at_level(logging.WARNING):
        engine._log_governance_summary()
    assert _warnings(caplog) == []


def test_empty_allowlist_no_warning(monkeypatch, caplog):
    """Empty allowlist = denylist mode: everything governed is
    evaluated, so nothing is blocked and nothing may warn."""
    engine = _engine_with_allowlist(monkeypatch, set())
    with caplog.at_level(logging.WARNING):
        engine._log_governance_summary()
    assert _warnings(caplog) == []


def test_governance_info_line_still_logged(monkeypatch, caplog):
    engine = _engine_with_allowlist(monkeypatch, PRODUCTION_ALLOWLIST)
    with caplog.at_level(logging.INFO):
        engine._log_governance_summary()
    infos = [r.getMessage() for r in caplog.records if "Governance (config_strategy)" in r.getMessage()]
    assert len(infos) == 1
    assert "strategy_bollinger_trend" in infos[0]
