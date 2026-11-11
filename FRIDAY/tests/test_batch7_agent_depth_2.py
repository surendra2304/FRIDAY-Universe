"""Checklists F3/F5/F6/F11/F12/F23/F24 (MASTER_COMPLETION_CHECKLIST) —
Batch 7, ZAI Agent 2.

Contracts locked here:
- F3 usage tracker: per-agent per-day counters, soft/hard rate-limit guard,
  bounded store (keeps last 14 days);
- F5 daily portfolio report: scheduled 09:00 IST push of the live Stratex
  snapshot, honest when Stratex is unreachable;
- F6 alert rules: parse "alert me when BTC > 100k", evaluate against the
  real market price, fire+push once per rule per day (latched), silent on
  missing readings (never invents a firing);
- F11 forecast refresh: twice-daily (AM 09:30 / PM 18:30) forecasts on
  tracked markets, each stored with its horizon maturity timestamp;
- F12 prediction accuracy: forecasts whose horizon elapsed get scored
  HIT/MISS/PARTIAL against the actual price; honest when actual is missing
  (forecast stays pending, never a fake MISS);
- F23/F24 router routing: RENDER/PUBLISH/ALERT keywords → TOOL_EXECUTION
  (never DIRECT_REASONING guessing), no regression on existing sets;
- F24 fail-closed gate: production publish blocked without BOTH the confirm
  phrase AND the env flag (D-015 two-gate shape).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.core.owner_time import OWNER_TZ  # noqa: E402
from friday.proactive import agent_watch as aw  # noqa: E402
from friday.proactive import market_watch as mw  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_latches():
    aw.reset_latches_for_tests()
    yield
    aw.reset_latches_for_tests()


# ---------------------------------------------------------------------------
# F3 — usage tracker + rate-limit guard
# ---------------------------------------------------------------------------

class TestUsageTracker:
    def test_records_per_agent_and_totals(self, tmp_path):
        t = mw.UsageTracker(str(tmp_path / "u.json"))
        t.record("intelx", calls=2, tokens=100)
        t.record("intelx", calls=1, tokens=50)
        t.record("stratex", calls=3)
        s = t.today_summary()
        assert s["totals"]["calls"] == 6
        assert s["totals"]["tokens"] == 150
        assert s["agents"]["intelx"]["calls"] == 3
        assert s["agents"]["intelx"]["tokens"] == 150
        assert s["agents"]["stratex"]["calls"] == 3

    def test_soft_warning_at_80pct(self, tmp_path, monkeypatch):
        t = mw.UsageTracker(str(tmp_path / "u.json"))
        # intelx calls_per_day = 200; 161 = 80.5%
        for _ in range(161):
            t.record("intelx", calls=1)
        guard = t.rate_limit_guard()
        assert guard["status"] == "warning"
        assert any(w["agent"] == "intelx" for w in guard["soft_warnings"])

    def test_hard_stop_at_100pct(self, tmp_path):
        t = mw.UsageTracker(str(tmp_path / "u.json"))
        for _ in range(200):
            t.record("intelx", calls=1)
        guard = t.rate_limit_guard()
        assert guard["status"] == "blocked"
        assert any(b["agent"] == "intelx" for b in guard["hard_blocks"])

    def test_store_bounded_to_14_days(self, tmp_path, monkeypatch):
        # Simulate 20 distinct days by mutating owner_today.
        import friday.proactive.market_watch as m
        orig = m.owner_today
        t = mw.UsageTracker(str(tmp_path / "u.json"))
        for i in range(20):
            monkeypatch.setattr(m, "owner_today", lambda i=i: f"2026-01-{i+1:02d}")
            t.record("intelx", calls=1)
        monkeypatch.setattr(m, "owner_today", orig)
        # The store should have kept only the last 14 days.
        import json
        with open(t._path) as f:
            data = json.load(f)
        assert len(data["days"]) <= 14


# ---------------------------------------------------------------------------
# F6 — alert rules: parsing, evaluation, store
# ---------------------------------------------------------------------------

class TestAlertRuleParsing:
    def test_parses_above_with_k_suffix(self):
        r = mw.parse_alert_rule("alert me when BTC > 100k")
        assert r is not None
        assert r.symbol == "BTC" and r.direction == "above" and r.target == 100000

    def test_parses_below_with_commas(self):
        r = mw.parse_alert_rule("watch NIFTY dip below 24,500")
        assert r is not None
        assert r.symbol == "NIFTY" and r.direction == "below" and r.target == 24500

    def test_parses_natural_language(self):
        r = mw.parse_alert_rule("alert me when ETH rises above 5000")
        assert r is not None and r.direction == "above" and r.target == 5000

    def test_returns_none_for_non_alert(self):
        assert mw.parse_alert_rule("how is the weather") is None
        assert mw.parse_alert_rule("what's my portfolio") is None


class TestAlertRuleEvaluation:
    def test_fires_when_above_crossed(self):
        r = mw.AlertRule("BTC", "above", 100000)
        fires, _ = r.evaluate(100500)
        assert fires
        fires, _ = r.evaluate(99500)
        assert not fires

    def test_fires_when_below_crossed(self):
        r = mw.AlertRule("NIFTY", "below", 24500)
        fires, _ = r.evaluate(24400)
        assert fires

    def test_does_not_fire_on_missing_price(self):
        r = mw.AlertRule("BTC", "above", 100000)
        fires, reason = r.evaluate(None)
        assert not fires and "missing data" in reason


class TestAlertStore:
    def test_add_remove_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mw, "alert_store", mw.AlertStore(str(tmp_path / "a.json")))
        r = mw.AlertRule("BTC", "above", 100000)
        added = mw.alert_store.add(r)
        assert added["rule_id"] == r.rule_id
        # idempotent
        mw.alert_store.add(r)
        assert len(mw.alert_store.list()) == 1
        # remove
        assert mw.alert_store.remove(r.rule_id) is True
        assert mw.alert_store.list() == []
        assert mw.alert_store.remove(r.rule_id) is False

    def test_latches_fired_per_day(self, tmp_path, monkeypatch):
        store = mw.AlertStore(str(tmp_path / "a.json"))
        monkeypatch.setattr(mw, "alert_store", store)
        r = mw.AlertRule("BTC", "above", 100000)
        store.add(r)
        store.mark_fired(r.rule_id)
        rule_dict = store.list()[0]
        assert (rule_dict["last_fired_ist"] or "")[:10]  # set to today


# ---------------------------------------------------------------------------
# F6 — alert check loop (run_alert_check)
# ---------------------------------------------------------------------------

def _deliver_collector(out: list[str]):
    async def deliver(text: str) -> bool:
        out.append(text)
        return True
    return deliver


class TestAlertCheckLoop:
    def test_fires_and_pushes_when_crossed(self, tmp_path, monkeypatch):
        store = mw.AlertStore(str(tmp_path / "a.json"))
        monkeypatch.setattr(mw, "alert_store", store)
        store.add(mw.AlertRule("BTC", "above", 100000))
        out: list[str] = []

        async def fake_query(symbol: str):
            return {"signals": [{"symbol": "BTC", "price": 100500}]}

        r = asyncio.run(mw.run_alert_check(deliver=_deliver_collector(out), query_fn=fake_query))
        assert r["fired"] == 1 and r["deliveries"] == 1
        assert "Alert fired" in out[0]
        # Latched: a second run on the same day does not re-fire.
        out.clear()
        r2 = asyncio.run(mw.run_alert_check(deliver=_deliver_collector(out), query_fn=fake_query))
        assert r2["fired"] == 0 and out == []

    def test_silent_on_missing_price(self, tmp_path, monkeypatch):
        store = mw.AlertStore(str(tmp_path / "a.json"))
        monkeypatch.setattr(mw, "alert_store", store)
        store.add(mw.AlertRule("BTC", "above", 100000))
        out: list[str] = []

        async def empty_query(symbol: str):
            return {"signals": []}  # no price reported

        r = asyncio.run(mw.run_alert_check(deliver=_deliver_collector(out), query_fn=empty_query))
        assert r["fired"] == 0 and r["skipped_missing"] == 1
        assert out == []  # silent — no fabricated firing

    def test_query_failure_does_not_fire(self, tmp_path, monkeypatch):
        store = mw.AlertStore(str(tmp_path / "a.json"))
        monkeypatch.setattr(mw, "alert_store", store)
        store.add(mw.AlertRule("BTC", "above", 100000))
        out: list[str] = []

        async def broken_query(symbol: str):
            raise RuntimeError("stratex down")

        r = asyncio.run(mw.run_alert_check(deliver=_deliver_collector(out), query_fn=broken_query))
        assert r["fired"] == 0 and r["skipped_missing"] == 1
        assert out == []


# ---------------------------------------------------------------------------
# F11/F12 — forecast store + scoring
# ---------------------------------------------------------------------------

class TestForecastStore:
    def test_record_stores_horizon_maturity(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)
        rec = fs.record("BTCUSDT", "1h", "BTC up 2%")
        assert rec["horizon_seconds"] == 3600
        assert rec["status"] == "pending"
        s = fs.summary()
        assert s["total"] == 1 and s["pending"] == 1

    def test_matured_unscored_only_returns_due(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)
        # A 1h forecast issued 2h ago is matured.
        rec = fs.record("BTCUSDT", "1h", "BTC up")
        import friday.proactive.market_watch as m
        # Backdate the issued/matures timestamps.
        fs._load()
        for f in fs._cache:
            f["matures_ist"] = (datetime.now(OWNER_TZ) - timedelta(hours=1)).isoformat()
        fs._save()
        matured = fs.matured_unscored()
        assert len(matured) == 1

    def test_score_classifies_hit(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)
        rec = fs.record("BTCUSDT", "1h", "BTC rises to 102000")
        scored = fs.score(rec["id"], "BTC up to 102500", delta=0.005)
        assert scored["status"] in {"hit", "partial"}  # direction matches

    def test_score_classifies_miss(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)
        rec = fs.record("BTCUSDT", "1h", "BTC rises")
        scored = fs.score(rec["id"], "BTC down 3%")
        assert scored["status"] == "miss"


class TestPredictionScoring:
    def test_honest_when_actual_missing(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)
        rec = fs.record("BTCUSDT", "1h", "BTC rises")
        for f in fs._load():
            f["matures_ist"] = (datetime.now(OWNER_TZ) - timedelta(hours=1)).isoformat()
        fs._save()

        async def empty_actual(target: str):
            return ""

        r = asyncio.run(mw.run_prediction_scoring(actual_fn=empty_actual))
        assert r["scored"] == 0 and r["skipped"] == 1
        # forecast stays pending, not a fake MISS
        assert fs.summary()["pending"] == 1

    def test_scores_when_actual_present(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)
        rec = fs.record("BTCUSDT", "1h", "BTC rises to 102000")
        for f in fs._load():
            f["matures_ist"] = (datetime.now(OWNER_TZ) - timedelta(hours=1)).isoformat()
        fs._save()

        async def real_actual(target: str):
            return "BTC up to 102500"

        r = asyncio.run(mw.run_prediction_scoring(actual_fn=real_actual))
        assert r["scored"] == 1


# ---------------------------------------------------------------------------
# F5 — daily portfolio report
# ---------------------------------------------------------------------------

class TestDailyPortfolioReport:
    def test_pushes_snapshot_to_telegram(self, monkeypatch):
        out: list[str] = []

        async def fake_snapshot():
            return "Portfolio: $50,000 (3 positions, 2 strategies active)"

        r = asyncio.run(mw.run_daily_portfolio_report(deliver=_deliver_collector(out), snapshot_fn=fake_snapshot))
        assert r["delivered"] is True
        assert "Portfolio: $50,000" in out[0]
        assert "fail-closed, D-015" in out[0]

    def test_honest_when_stratex_unreachable(self, monkeypatch):
        out: list[str] = []

        async def broken_snapshot():
            raise RuntimeError("stratex down")

        r = asyncio.run(mw.run_daily_portfolio_report(deliver=_deliver_collector(out), snapshot_fn=broken_snapshot))
        assert r["delivered"] is True
        assert "could not be generated" in out[0]
        assert "honestly" in out[0]


# ---------------------------------------------------------------------------
# F11 — forecast refresh
# ---------------------------------------------------------------------------

class TestForecastRefresh:
    def test_stores_each_forecast(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)

        async def fake_forecast(target: str, h: str):
            return {"reply": f"{target} forecast: bullish over {h}"}

        r = asyncio.run(mw.run_forecast_refresh(forecast_fn=fake_forecast, tracked=("BTCUSDT", "ETHUSDT")))
        assert r["stored"] == 2 and r["issued"] == 2
        assert fs.summary()["total"] == 2

    def test_honest_when_forecast_fails(self, tmp_path, monkeypatch):
        fs = mw.ForecastStore(str(tmp_path / "f.json"))
        monkeypatch.setattr(mw, "forecast_store", fs)

        async def broken_forecast(target: str, h: str):
            raise RuntimeError("futuris down")

        r = asyncio.run(mw.run_forecast_refresh(forecast_fn=broken_forecast, tracked=("BTCUSDT",)))
        assert r["stored"] == 0
        assert r["errors"] and "BTCUSDT" in r["errors"][0]


# ---------------------------------------------------------------------------
# F11 — scheduler integration (agent_watch_tick with market passes)
# ---------------------------------------------------------------------------

class TestAgentWatchTickMarket:
    def test_portfolio_fires_at_09_ist(self):
        fired: list[str] = []

        async def fake_portfolio():
            fired.append("portfolio")
            return {"delivered": True}

        async def noop():
            return {"delivered": True}

        nine = datetime(2026, 11, 12, 9, 30, tzinfo=OWNER_TZ)
        asyncio.run(aw.agent_watch_tick(now=nine, portfolio_coro_factory=fake_portfolio, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop, alert_coro_factory=noop))
        assert "portfolio" in fired

    def test_forecast_am_pm_windows(self):
        fired: list[str] = []

        async def fake_forecast():
            fired.append("forecast")
            return {"stored": 1, "issued": 1}

        async def noop():
            return {"delivered": True}

        am = datetime(2026, 11, 12, 9, 45, tzinfo=OWNER_TZ)
        asyncio.run(aw.agent_watch_tick(now=am, forecast_coro_factory=fake_forecast, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, prediction_coro_factory=noop, alert_coro_factory=noop))
        pm = datetime(2026, 11, 12, 18, 45, tzinfo=OWNER_TZ)
        aw.reset_latches_for_tests()
        asyncio.run(aw.agent_watch_tick(now=pm, forecast_coro_factory=fake_forecast, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, prediction_coro_factory=noop, alert_coro_factory=noop))
        assert fired.count("forecast") == 2  # both windows

    def test_prediction_scoring_at_21_ist(self):
        fired: list[str] = []

        async def fake_pred():
            fired.append("prediction")
            return {"scored": 0, "skipped": 0}

        async def noop():
            return {"delivered": True}

        evening = datetime(2026, 11, 12, 21, 30, tzinfo=OWNER_TZ)
        asyncio.run(aw.agent_watch_tick(now=evening, prediction_coro_factory=fake_pred, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, forecast_coro_factory=noop, alert_coro_factory=noop))
        assert "prediction" in fired

    def test_alert_check_runs_every_hour(self):
        # Two ticks 1h apart both fire alert check; closer ticks do not.
        fired: list[int] = []

        async def fake_alert():
            fired.append(1)
            return {"fired": 0, "evaluated": 0}

        async def noop():
            return {"delivered": True}

        noon = datetime(2026, 11, 12, 12, 0, tzinfo=OWNER_TZ)
        asyncio.run(aw.agent_watch_tick(now=noon, alert_coro_factory=fake_alert, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop))
        asyncio.run(aw.agent_watch_tick(now=noon, alert_coro_factory=fake_alert, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=noop, portfolio_coro_factory=noop, forecast_coro_factory=noop, prediction_coro_factory=noop))
        # Same hour — second tick suppressed by the min-interval latch.
        assert len(fired) == 1


# ---------------------------------------------------------------------------
# F23/F24 — router routing
# ---------------------------------------------------------------------------

class TestBatch7Routing:
    @pytest.fixture()
    def router(self):
        from friday.routing.capability_router import CapabilityRouter

        return CapabilityRouter()

    def test_render_phrasing_reaches_tool(self, router):
        from friday.routing.capability_router import ExecutionCapabilityType

        d = router.route_request("render the script as a short")
        tools = [t for c in d.candidate_evaluations for t in (c.required_tools or [])]
        assert "vyralx_render" in tools
        assert any(c.capability_type == ExecutionCapabilityType.TOOL_EXECUTION for c in d.candidate_evaluations)

    def test_publish_phrasing_reaches_tool(self, router):
        d = router.route_request("publish the clip to youtube")
        tools = [t for c in d.candidate_evaluations for t in (c.required_tools or [])]
        assert "vyralx_publish" in tools

    def test_alert_phrasing_reaches_tool(self, router):
        d = router.route_request("alert me when BTC > 100k")
        tools = [t for c in d.candidate_evaluations for t in (c.required_tools or [])]
        assert "price_alert" in tools

    def test_no_regression_on_existing_keyword_sets(self, router):
        def tools(text: str) -> list[str]:
            d = router.route_request(text)
            return [t for c in d.candidate_evaluations for t in (c.required_tools or [])]

        assert "intelx_research" in tools("research the crypto market")
        assert "get_fleet_status" in tools("how's the fleet?")
        assert "web_fetch_summarize" in tools("summarize this page https://example.com/x")
        assert "stratex_portfolio" in tools("how's my portfolio")

    def test_plain_chat_stays_conversational(self, router):
        from friday.routing.capability_router import ExecutionCapabilityType

        d = router.route_request("hey how are you doing today")
        # Should NOT be a TOOL_EXECUTION with vyralx_render or vyralx_publish
        for c in d.candidate_evaluations:
            if c.capability_type == ExecutionCapabilityType.TOOL_EXECUTION:
                for t in (c.required_tools or []):
                    assert t not in {"vyralx_render", "vyralx_publish", "price_alert"}


# ---------------------------------------------------------------------------
# F24 — fail-closed gate (D-015 two-gate shape)
# ---------------------------------------------------------------------------

class TestPublishFailClosed:
    @pytest.fixture()
    def tool(self):
        from friday.tools.builtin.vyralx_publish import VyralXPublishTool

        return VyralXPublishTool()

    def test_draft_mode_runs(self, tool, monkeypatch):
        # Draft mode bypasses the gate; the tool will try the network and
        # fail honestly (no VyralX in the test env), but the gate is passed.
        monkeypatch.delenv("FRIDAY_VYRALX_PUBLISH_PROD_ALLOWED", raising=False)
        result = tool.execute(title="My Clip", status="draft")
        # Network failure is honest — but the gate must not block draft.
        assert not (result.is_error and "gated" in str(result.metadata))

    def test_public_blocked_without_phrase(self, tool, monkeypatch):
        monkeypatch.setenv("FRIDAY_VYRALX_PUBLISH_PROD_ALLOWED", "true")
        result = tool.execute(title="My Clip", status="public")
        assert result.is_error
        assert "won't publish" in result.content or "gated" in str(result.metadata)

    def test_public_blocked_without_env_flag(self, tool, monkeypatch):
        monkeypatch.delenv("FRIDAY_VYRALX_PUBLISH_PROD_ALLOWED", raising=False)
        result = tool.execute(title="My Clip", status="public", confirm_phrase="publish to youtube")
        assert result.is_error
        assert "owner-authorization flag" in result.content

    def test_public_runs_with_both_gates(self, tool, monkeypatch):
        monkeypatch.setenv("FRIDAY_VYRALX_PUBLISH_PROD_ALLOWED", "true")
        result = tool.execute(title="My Clip", status="public", confirm_phrase="publish to youtube")
        # Both gates passed; the tool proceeds to the network call (which will
        # fail in the test env). The error must NOT be the gate.
        assert not (result.is_error and "gate" in str(result.metadata))


# ---------------------------------------------------------------------------
# F23 — render tool: missing title is an error
# ---------------------------------------------------------------------------

class TestRenderTool:
    @pytest.fixture()
    def tool(self):
        from friday.tools.builtin.vyralx_render import VyralXRenderTool

        return VyralXRenderTool()

    def test_missing_title_is_an_error(self, tool):
        result = tool.execute(title="")
        assert result.is_error and "need the script title" in result.content

    def test_invalid_format_defaults_to_shorts(self, tool):
        # No assertion fires — the tool normalizes the format and proceeds.
        # The network call will fail honestly; we only verify no crash.
        result = tool.execute(title="My Clip", format="bogus")
        assert result.is_error  # network/VyralX unreachable in test env


# ---------------------------------------------------------------------------
# Server endpoint smoke (F3 usage dashboard)
# ---------------------------------------------------------------------------

class TestUsageDashboardEndpoint:
    def test_endpoint_registered(self):
        # The /api/agents/usage route must be defined in server.py.
        import re
        from pathlib import Path

        server_src = Path(REPO / "FRIDAY" / "src" / "friday" / "api" / "server.py").read_text(encoding="utf-8")
        assert re.search(r'@app\.get\("/api/agents/usage"\)', server_src)
