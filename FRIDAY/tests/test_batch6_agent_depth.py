"""Checklists F8/F9/F13/F14/F15/F17/F18/F20/F21 (MASTER_COMPLETION_CHECKLIST) —
Batch 6, ZAI Agent 2.

Contracts locked here:
- F8 watchlist: add/remove/list intents in chat, file persistence across
  instances, casing preserved from the owner's words;
- F9 change detection: first brief → "first brief"; identical brief → "no
  change"; changed brief → only NEW lines reported;
- F8 scheduler: briefing window latches once per day, site sweep window,
  Monday-only Sentinel digest, failed delivery unlatches for retry;
- F13 web_fetch_summarize: SSRF guard refuses loopback/private/link-local/
  metadata/non-http before connect; router routes fetch phrasing to
  TOOL_EXECUTION web_fetch_summarize (never DIRECT_REASONING);
- F14/F15 site sweep: honest per-site results, healthy → one line,
  degraded → alert lines, delivery via the wired channel;
- F20 Sentinel digest: real posture/findings text rendered, honest
  unreachable report;
- F21 secret guard: pattern self-test (also run standalone), allowlist.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.core.owner_time import OWNER_TZ  # noqa: E402
from friday.proactive import agent_watch as aw  # noqa: E402


@pytest.fixture()
def store(tmp_path: Path) -> aw.WatchlistStore:
    return aw.WatchlistStore(str(tmp_path / "watch" / "watchlist.json"))


@pytest.fixture(autouse=True)
def _reset_latches():
    aw.reset_latches_for_tests()
    yield
    aw.reset_latches_for_tests()


# ---------------------------------------------------------------------------
# F8 — watchlist store + intents
# ---------------------------------------------------------------------------

class TestWatchlistStore:
    def test_add_persists_across_instances(self, store):
        entry = store.add_topic("The AI hardware race")
        fresh = aw.WatchlistStore(store._path)
        topics = fresh.topics()
        assert len(topics) == 1 and topics[0]["topic"] == "The AI hardware race"
        assert entry["brief_count"] == 0

    def test_add_is_idempotent_per_topic(self, store):
        store.add_topic("crude oil")
        store.add_topic("Crude Oil")  # case-insensitive key
        assert len(store.topics()) == 1

    def test_remove(self, store):
        store.add_topic("crude oil")
        assert store.remove_topic("crude oil") is True
        assert store.remove_topic("crude oil") is False
        assert store.topics() == []

    def test_record_brief_fingerprint(self, store):
        store.add_topic("crude oil")
        store.record_brief("crude oil", "line one about oil\nline two about demand")
        entry = store.topics()[0]
        assert entry["last_hash"] and len(entry["last_lines"]) == 2
        assert entry["brief_count"] == 1


class TestWatchlistIntents:
    def test_add_intent_extracts_topic_with_casing(self):
        assert aw.parse_watch_add("watch topic The AI Hardware Race") == "The AI Hardware Race"
        assert aw.parse_watch_add("keep an eye on crude oil prices") == "crude oil prices"
        assert aw.parse_watch_add("add to my watchlist: quantum computing") == "quantum computing"

    def test_add_intent_ignores_plain_chat(self):
        assert aw.parse_watch_add("how is the fleet doing") is None
        assert aw.parse_watch_add("what time is it") is None
        assert aw.parse_watch_add("i watched a movie yesterday") is None  # substring safety

    def test_remove_and_list_intents(self):
        assert aw.parse_watch_remove("stop watching crude oil prices") == "crude oil prices"
        assert aw.parse_watch_remove("remove from my watchlist: quantum computing") == "quantum computing"
        assert aw.is_watchlist_query("my watchlist")
        assert aw.is_watchlist_query("what's on my watchlist")
        assert not aw.is_watchlist_query("watch topic X")


# ---------------------------------------------------------------------------
# F9 — change detection through the briefing
# ---------------------------------------------------------------------------

def _deliver_collector(out: list[str]):
    async def deliver(text: str) -> bool:
        out.append(text)
        return True
    return deliver


class TestWatchlistBriefing:
    def test_first_brief_then_no_change_then_new_lines(self, store, monkeypatch):
        monkeypatch.setattr(aw, "watchlist_store", store)
        store.add_topic("crude oil")
        out: list[str] = []

        async def brief(topic: str) -> str:
            return "Demand outlook improved in Asia\nOPEC supply steady\n"

        # Day 1: first brief
        r1 = asyncio.run(aw.run_watchlist_briefing(deliver=_deliver_collector(out), brief_fn=brief))
        assert r1["topics"] == 1 and r1["delivered"]
        assert "first brief" in out[0]

        # Day 2: identical content → no change
        asyncio.run(aw.run_watchlist_briefing(deliver=_deliver_collector(out), brief_fn=brief))
        assert "no change" in out[1]

        # Day 3: changed content → only new lines
        async def brief2(topic: str) -> str:
            return "Demand outlook improved in Asia\nOPEC announced surprise cuts\n"

        asyncio.run(aw.run_watchlist_briefing(deliver=_deliver_collector(out), brief_fn=brief2))
        assert "what's new" in out[2]
        assert "surprise cuts" in out[2]
        assert "OPEC supply steady" not in out[2]

    def test_failed_brief_is_honest(self, store, monkeypatch):
        monkeypatch.setattr(aw, "watchlist_store", store)
        store.add_topic("crude oil")
        out: list[str] = []

        async def broken(topic: str):
            raise RuntimeError("intelx down")

        r = asyncio.run(aw.run_watchlist_briefing(deliver=_deliver_collector(out), brief_fn=broken))
        assert "could not get a brief" in out[0]
        assert "not guessed" in out[0]

    def test_empty_watchlist_sends_nothing(self, store, monkeypatch):
        monkeypatch.setattr(aw, "watchlist_store", store)
        out: list[str] = []

        async def brief(topic: str) -> str:
            return "unused"

        r = asyncio.run(aw.run_watchlist_briefing(deliver=_deliver_collector(out), brief_fn=brief))
        assert r["topics"] == 0 and out == []  # no noise


# ---------------------------------------------------------------------------
# scheduler windows + latches
# ---------------------------------------------------------------------------

class TestAgentWatchTick:
    def test_site_sweep_fires_in_morning_window_once(self, monkeypatch):
        fired: list[str] = []

        async def fake_sweep():
            fired.append("site")
            return {"delivered": True}

        async def noop():
            return {"delivered": True}

        morning = datetime(2026, 11, 12, 9, 0, tzinfo=OWNER_TZ)  # 09:00 IST
        r1 = asyncio.run(aw.agent_watch_tick(now=morning, site_coro_factory=fake_sweep, watch_coro_factory=noop, sentinel_coro_factory=noop))
        r2 = asyncio.run(aw.agent_watch_tick(now=morning, site_coro_factory=fake_sweep, watch_coro_factory=noop, sentinel_coro_factory=noop))
        assert fired == ["site"]  # once per day
        assert r1["site"]["delivered"] and r2["site"] is None

    def test_watch_briefing_fires_in_evening_window(self):
        fired: list[str] = []

        async def fake_watch():
            fired.append("watch")
            return {"delivered": True}

        async def noop():
            return {"delivered": True}

        evening = datetime(2026, 11, 12, 18, 0, tzinfo=OWNER_TZ)  # 18:00 IST
        asyncio.run(aw.agent_watch_tick(now=evening, site_coro_factory=noop, watch_coro_factory=fake_watch, sentinel_coro_factory=noop))
        assert fired == ["watch"]

    def test_nothing_outside_windows(self):
        async def boom():  # must never be called
            raise AssertionError("no pass should run outside its window")

        noon = datetime(2026, 11, 12, 13, 30, tzinfo=OWNER_TZ)  # between windows
        r = asyncio.run(aw.agent_watch_tick(now=noon, site_coro_factory=boom, watch_coro_factory=boom, sentinel_coro_factory=boom))
        assert r == {"watch": None, "site": None, "sentinel": None}

    def test_sentinel_digest_monday_only(self):
        fired: list[str] = []

        async def fake_sentinel():
            fired.append("sentinel")
            return {"delivered": True}

        async def noop():
            return {"delivered": True}

        monday = datetime(2026, 11, 16, 10, 0, tzinfo=OWNER_TZ)  # a Monday
        tuesday = datetime(2026, 11, 17, 10, 0, tzinfo=OWNER_TZ)  # 09:30+ on Tuesday: site may fire; sentinel must not
        asyncio.run(aw.agent_watch_tick(now=monday, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=fake_sentinel))
        aw.reset_latches_for_tests()
        asyncio.run(aw.agent_watch_tick(now=tuesday, site_coro_factory=noop, watch_coro_factory=noop, sentinel_coro_factory=fake_sentinel))
        assert fired == ["sentinel"]  # Monday only, not Tuesday

    def test_failed_delivery_unlatches_for_retry(self):
        calls: list[int] = []

        async def flaky():
            calls.append(1)
            return {"delivered": len(calls) >= 2}  # fails first, succeeds second

        async def noop():
            return {"delivered": True}

        evening = datetime(2026, 11, 12, 18, 0, tzinfo=OWNER_TZ)
        asyncio.run(aw.agent_watch_tick(now=evening, site_coro_factory=noop, watch_coro_factory=flaky, sentinel_coro_factory=noop))
        asyncio.run(aw.agent_watch_tick(now=evening, site_coro_factory=noop, watch_coro_factory=flaky, sentinel_coro_factory=noop))
        assert len(calls) == 2  # retried after the failed delivery


# ---------------------------------------------------------------------------
# F14/F15 — site health sweep
# ---------------------------------------------------------------------------

class TestSiteHealthSweep:
    def test_healthy_fleet_one_line(self, monkeypatch):
        out: list[str] = []

        async def healthy_probe(url: str):
            return True, 200, "200 in 0.12s"

        async def fake_cortex():
            return {"reply": "Cortex: all good"}

        import friday.ecosystem.fleet_client as fc

        class FakeClient:
            async def request_cortex_web_ops(self):
                return {"reply": "Cortex summary line"}

            async def aclose(self):
                pass

        monkeypatch.setattr(fc, "FleetClient", FakeClient)
        r = asyncio.run(aw.run_site_health_sweep(deliver=_deliver_collector(out), probe_fn=healthy_probe))
        assert r["healthy"] == r["checked"] == len(aw.GATEWAY_ROUTES)
        assert len(out) == 1 and "healthy" in out[0]

    def test_degraded_site_alerts(self, monkeypatch):
        out: list[str] = []

        async def mixed_probe(url: str):
            ok = "sentinel" not in url
            return ok, (200 if ok else 0), ("200 in 0.1s" if ok else "unreachable (ConnectError)")

        import friday.ecosystem.fleet_client as fc

        class FakeClient:
            async def request_cortex_web_ops(self):
                return {"reply": "Cortex summary"}

            async def aclose(self):
                pass

        monkeypatch.setattr(fc, "FleetClient", FakeClient)
        r = asyncio.run(aw.run_site_health_sweep(deliver=_deliver_collector(out), probe_fn=mixed_probe))
        assert r["degraded"] == ["sentinel: unreachable (ConnectError)"]
        assert "DEGRADED" in out[0] and "sentinel" in out[0]


# ---------------------------------------------------------------------------
# F20 — Sentinel digest
# ---------------------------------------------------------------------------

class TestSentinelDigest:
    def test_renders_real_posture_and_findings(self):
        out: list[str] = []

        async def fake_sentinel():
            return (
                {"reply": "Posture score 87/100. Critical: 0. Read-only surface."},
                {"reply": "2 open findings: 1 medium (TLS-2026), 1 low (banner)."},
            )

        r = asyncio.run(aw.run_sentinel_digest(deliver=_deliver_collector(out), sentinel_fn=fake_sentinel))
        assert r["delivered"]
        assert "87/100" in out[0] and "TLS-2026" in out[0]

    def test_unreachable_is_honest(self):
        out: list[str] = []

        async def broken():
            raise RuntimeError("sentinel down")

        r = asyncio.run(aw.run_sentinel_digest(deliver=_deliver_collector(out), sentinel_fn=broken))
        assert r["delivered"]
        assert "could not reach" in out[0] and "not guessed" in out[0]


# ---------------------------------------------------------------------------
# F13 — SSRF guard + tool
# ---------------------------------------------------------------------------

class TestSSRFGuard:
    @pytest.fixture()
    def tool(self):
        from friday.tools.builtin.web_fetch_summarize import WebFetchSummarizeTool

        return WebFetchSummarizeTool()

    def test_refuses_loopback(self, tool):
        result = tool.execute(url="http://127.0.0.1:8008/health")
        assert result.is_error and "won't fetch" in result.content
        assert result.metadata.get("ssrf_blocked") is True

    def test_refuses_localhost_name(self, tool):
        result = tool.execute(url="http://localhost:10000/api")
        assert result.is_error and "local hostname" in result.content

    def test_refuses_private_range(self, tool):
        result = tool.execute(url="http://10.0.0.121/service")
        assert result.is_error and "forbidden address" in result.content

    def test_refuses_link_local_metadata(self, tool):
        result = tool.execute(url="http://169.254.169.254/latest/meta-data/")
        assert result.is_error

    def test_refuses_non_http_scheme(self, tool):
        result = tool.execute(url="file:///etc/passwd")
        assert result.is_error and "not allowed" in result.content

    def test_refuses_odd_port(self, tool):
        result = tool.execute(url="https://example.com:8443/x")
        assert result.is_error and "port" in result.content

    def test_empty_url_is_an_error(self, tool):
        result = tool.execute(url="")
        assert result.is_error and "need a URL" in result.content


class TestFetchSummarizeRouting:
    @pytest.fixture()
    def router(self):
        from friday.routing.capability_router import CapabilityRouter

        return CapabilityRouter()

    def test_fetch_phrasing_reaches_tool_execution(self, router):
        decision = router.route_request("summarize this page https://example.com/article")
        assert decision.selected_capability.value == "TOOL_EXECUTION"
        assert "web_fetch_summarize" in ([t for c in decision.candidate_evaluations for t in (c.required_tools or [])])

    def test_what_does_this_page_say_routes_to_tool(self, router):
        decision = router.route_request("what does this article say? https://example.com/x")
        assert decision.selected_capability.value == "TOOL_EXECUTION"

    def test_plain_chat_stays_conversational(self, router):
        decision = router.route_request("hey how are you doing today")
        assert decision.selected_capability.value != "TOOL_EXECUTION" or "web_fetch_summarize" not in ([t for c in decision.candidate_evaluations for t in (c.required_tools or [])])

    def test_no_regression_on_existing_keyword_sets(self, router):
        # spot-check the neighbors: research/fleet/security still route correctly
        def tools(text: str) -> list[str]:
            d = router.route_request(text)
            return [t for c in d.candidate_evaluations for t in (c.required_tools or [])]

        assert "intelx_research" in tools("research the crypto market")
        assert "get_fleet_status" in tools("how's the fleet?")
        assert "sentinel_security" in tools("what's my security posture")


# ---------------------------------------------------------------------------
# F21 — secret guard
# ---------------------------------------------------------------------------

class TestSecretGuard:
    def test_self_test_passes(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "guard_secrets_pre_push.py"), "--self-test"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "PASS" in proc.stdout

    def test_scan_finds_planted_token(self, tmp_path):
        import subprocess

        planted = tmp_path / "leaked.txt"
        planted.write_text("token = '9050935840:AAHnotRealButShapedRight0123456789012345'\n")
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "guard_secrets_pre_push.py"), "--scan", str(planted)],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 1
        assert "telegram-bot-token" in proc.stdout


# ---------------------------------------------------------------------------
# F17/F18 — workflow files exist and are well-formed
# ---------------------------------------------------------------------------

class TestWorkflowConfigs:
    def test_dependabot_config_exists(self):
        import yaml

        cfg = yaml.safe_load((REPO / ".github" / "dependabot.yml").read_text())
        assert cfg["version"] == 2
        ecosystems = {u["package-ecosystem"] for u in cfg["updates"]}
        assert "github-actions" in ecosystems and "pip" in ecosystems

    def test_health_digest_workflow_valid_yaml(self):
        import yaml

        wf = yaml.safe_load((REPO / ".github" / "workflows" / "agent-health-digest.yml").read_text())
        assert "schedule" in wf[True] or "schedule" in wf.get(True, wf.get("on", {}))
        jobs = wf["jobs"]
        assert "digest" in jobs

    def test_pre_push_hook_present_and_executable(self):
        hook = REPO / ".githooks" / "pre-push"
        assert hook.exists() and hook.stat().st_mode & 0o111
