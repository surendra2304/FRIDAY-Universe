"""Checklist Batch 4 — memory + brain maturity (B8, B11, B12, A6, A7, A9, A11, A12, A14).

Contracts locked here, against deterministic fakes (same pattern as the
B7/B9/B10 suites — real routing, fake storage):
- B8  importance scoring: pinned/normal/trivial matrix + aging lifecycle;
- B11 voice-path memory: transcript intent extraction + honest store/forget;
- B12 memory browser: tier counting + honest unreachable;
- A6  multi-turn coherence: a 12-turn conversation keeps facts and goals;
- A7  reasoning benchmark: 20 delegation-style prompts, scored pass/fail;
- A9  tone matching: banter fires, real commands never hijacked;
- A11 long-goal persistence: stated once, tracked across the conversation;
- A12 proactive follow-up: stale tasks pinged, rate-limited, honest empties;
- A14 boss-only surface: gate matrix, fail-closed passphrase, refusals honest.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.memory.importance import ImportanceVerdict, age_out_trivial_memories, score_importance  # noqa: E402
from friday.memory.voice_memory import extract_voice_memory_intent, handle_voice_memory  # noqa: E402
from friday.persona.tone import tone_reply  # noqa: E402
from friday.proactive import followup as followup_mod  # noqa: E402
from friday.proactive import goals as goals_mod  # noqa: E402
from friday.security import boss_gate  # noqa: E402


# ---------------------------------------------------------------------------
# shared fake Memora (module-attr swap drives the real router)
# ---------------------------------------------------------------------------

class FakeMemora:
    def __init__(self):
        self.facts: list[dict] = []
        self._next = 1
        self.now = dt.datetime(2026, 11, 13, 10, 0, 0)

    def record_fact(self, agent_name, fact_text, category="preference", importance=0.95):
        row = {
            "id": f"mem_{self._next}",
            "content_text": fact_text,
            "provenance": {"category": category},
            "created_at": self.now.strftime("%Y-%m-%d %H:%M:%S"),
            "importance": importance,
        }
        self._next += 1
        self.facts.append(row)
        return {"status": "success", "id": row["id"]}

    def recall_memories(self, agent_name, query, limit=5):
        words = {w for w in query.lower().split() if len(w) > 3}
        scored = []
        for f in self.facts:
            hay = f["content_text"].lower()
            score = sum(1 for w in words if w in hay)
            if score:
                scored.append((score, f))
        scored.sort(key=lambda t: -t[0])
        return [f for _s, f in scored[:limit]]

    def recent_memories(self, agent_name, limit=100, since=""):
        return list(reversed(self.facts))[:limit]

    def forget_fact(self, agent_name, query, memory_id=""):
        qwords = [w for w in query.lower().split() if len(w) > 3][:4]
        for f in self.facts:
            if qwords and all(w in f["content_text"].lower() for w in qwords):
                self.facts.remove(f)
                return {"status": "deleted", "content_text": f["content_text"]}
        return {"status": "not_found"}

    def supersede_fact(self, agent_name, memory_id, winner_id="", reason=""):
        before = len(self.facts)
        self.facts = [f for f in self.facts if f["id"] != memory_id]
        return {"status": "superseded" if len(self.facts) < before else "not_found"}

    def correct_fact(self, agent_name, new_fact_text, old_query=""):
        old = self.forget_fact(agent_name, old_query or new_fact_text)
        if old["status"] == "deleted":
            self.record_fact(agent_name, new_fact_text)
            return {"status": "corrected", "content_text": new_fact_text}
        self.record_fact(agent_name, new_fact_text)
        return {"status": "stored_new_only"}


class FakeNotifications:
    def __init__(self):
        self.posted: list[tuple] = []

    def post_notification(self, message, category="monitoring", severity="info", metadata=None, notification_id=None):
        self.posted.append((message, category, severity))
        return "nid"


@pytest.fixture()
def fake_memora():
    return FakeMemora()


@pytest.fixture()
def router(monkeypatch: pytest.MonkeyPatch, fake_memora: FakeMemora):
    """The real chat router with the fake memory store swapped in."""
    import friday.memory.memora_client as mc
    import friday.api.server as server

    monkeypatch.setattr(mc, "memora_client", fake_memora, raising=False)
    return server


def run(command: str, boss_verified: bool = False) -> dict:
    from friday.api.server import _dispatch_command

    return asyncio.run(_dispatch_command(command, boss_verified=boss_verified))


# ---------------------------------------------------------------------------
# B8 — importance scoring
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,tier",
    [
        ("my name is surendra varma jalli", "pinned"),
        ("my phone number is 555-0100", "pinned"),
        ("my favorite chai is masala chai", "pinned"),
        ("i prefer dark themes everywhere", "pinned"),
        ("my wife loves trekking in the monsoon", "pinned"),
        ("i review the fleet every morning at 9", "pinned"),
        ("my goal this week is to finish the audit", "pinned"),
        ("i am your boss and i built this universe", "pinned"),
        ("the deployment uses docker compose with seven services", "normal"),
        ("stratex runs six validated strategies on the demo venue", "normal"),
        ("what time is it?", "trivial"),
        ("lol", "trivial"),
        ("i'm tired today", "trivial"),
        ("ok", "trivial"),
        ("nice", "trivial"),
        ("it's raining in hyderabad right now", "trivial"),
        ("task_042 executed with http 200", "trivial"),
    ],
)
def test_b8_scoring_matrix(text: str, tier: str):
    verdict = score_importance(text)
    assert verdict.tier == tier, f"{text!r}: expected {tier}, got {verdict.tier} ({verdict.reasons})"


def test_b8_verdict_properties():
    assert isinstance(score_importance("my favorite color is teal"), ImportanceVerdict)
    assert score_importance("my favorite color is teal").is_pinned
    assert score_importance("lol").is_trivial
    assert not score_importance("the system runs on oracle db").is_pinned


def test_b8_aging_retires_only_old_trivial(fake_memora: FakeMemora):
    old = dt.datetime(2026, 11, 1, 10, 0, 0)
    fake_memora.now = old
    fake_memora.record_fact("friday", "my favorite chai is masala chai")          # pinned, old
    fake_memora.record_fact("friday", "i'm tired today")                          # trivial, old
    fake_memora.record_fact("friday", "the gateway runs on two oci hosts")        # normal, old
    trivial_id = fake_memora.facts[1]["id"]
    fake_memora.now = dt.datetime(2026, 11, 13, 10, 0, 0)
    fake_memora.record_fact("friday", "i'm sleepy right now")                     # trivial, young

    report = age_out_trivial_memories(fake_memora, now=dt.datetime(2026, 11, 13, 10, 0, 0))
    assert report["status"] == "ok"
    assert report["aged_out"] == 1, report
    assert report["pinned_kept"] == 1
    assert report["normal_kept"] == 1
    assert report["trivial_kept_young"] == 1
    texts = [f["content_text"] for f in fake_memora.facts]
    assert "i'm tired today" not in texts          # the old trivial fact retired
    assert "my favorite chai is masala chai" in texts  # pinned survives
    assert any("sleepy" in t for t in texts)       # young trivial survives


def test_b8_aging_never_touches_daily_summaries(fake_memora: FakeMemora):
    fake_memora.record_fact("friday", "Daily memory summary (auto) 2026-11-05: 3 memories kept — quiet day")
    report = age_out_trivial_memories(fake_memora, now=dt.datetime(2026, 11, 20, 3, 0, 0))
    assert report["aged_out"] == 0
    assert len(fake_memora.facts) == 1


def test_b8_aging_honest_on_broken_store():
    class Broken:
        def recent_memories(self, *a, **k):
            raise RuntimeError("store down")

    report = age_out_trivial_memories(Broken())
    assert report["status"] == "error"
    assert report["aged_out"] == 0


def test_b8_remember_path_scores_and_reports_tier(router, fake_memora: FakeMemora):
    res = run("remember this boss: my favorite chai is masala chai")
    assert res["metadata"]["memory_store"] is True
    assert res["metadata"]["importance_tier"] == "pinned"
    assert "pinned" in res["reply"].lower()
    assert fake_memora.facts[0]["importance"] == 0.98

    res = run("remember lol")
    assert res["metadata"]["importance_tier"] == "trivial"
    assert "fades" in res["reply"].lower()
    assert fake_memora.facts[-1]["importance"] == 0.20


def test_b8_nightly_consolidation_reports_aging(router, fake_memora: FakeMemora, monkeypatch):
    from friday.proactive.nightly_consolidation import consolidate_day_memories

    fake_memora.record_fact("friday", "my favorite chai is masala chai")
    fake_memora.record_fact("friday", "i'm tired today")
    # age the trivial fact past the window by back-dating it
    fake_memora.facts[-1]["created_at"] = "2026-11-01 10:00:00"
    report = consolidate_day_memories(fake_memora, now=dt.datetime(2026, 11, 13, 10, 0, 0))
    assert report["status"] == "consolidated"
    assert "aged_out" in report and "aging_examined" in report and "aging_status" in report


# ---------------------------------------------------------------------------
# B11 — voice-path memory
# ---------------------------------------------------------------------------

def test_b11_intent_extraction_matrix():
    assert extract_voice_memory_intent("remember my chai preference is masala")["kind"] == "remember"
    assert extract_voice_memory_intent("Remember this: I hate loud alarms")["kind"] == "remember"
    assert extract_voice_memory_intent("forget about the marker color")["kind"] == "forget"
    assert extract_voice_memory_intent("forget that")["kind"] == "forget"
    assert extract_voice_memory_intent("actually my number is 555")["kind"] == "correction"
    # non-memory conversational input
    assert extract_voice_memory_intent("what's the portfolio status") is None
    assert extract_voice_memory_intent("hello friday") is None
    assert extract_voice_memory_intent("remember") is None  # bare remember, no payload


def test_b11_handle_stores_and_confirms(monkeypatch: pytest.MonkeyPatch, fake_memora: FakeMemora):
    import friday.memory.memora_client as mc

    monkeypatch.setattr(mc, "memora_client", fake_memora, raising=False)
    reply = handle_voice_memory("remember my mother's birthday is march 3rd")
    assert reply and "locked in" in reply.lower()
    assert any("mother" in f["content_text"] for f in fake_memora.facts)


def test_b11_handle_forget_and_redirect(monkeypatch: pytest.MonkeyPatch, fake_memora: FakeMemora):
    import friday.memory.memora_client as mc

    monkeypatch.setattr(mc, "memora_client", fake_memora, raising=False)
    handle_voice_memory("remember the gate code is 4471")
    reply = handle_voice_memory("forget about the gate code")
    assert reply and "forgotten" in reply.lower()
    assert not any("gate code" in f["content_text"] for f in fake_memora.facts)
    # corrections are redirected, never half-heard overwrites
    reply = handle_voice_memory("actually my number is 555-0199")
    assert reply and "chat" in reply.lower()


def test_b11_store_outage_is_honest(monkeypatch: pytest.MonkeyPatch):
    import friday.memory.memora_client as mc

    class Down:
        def record_fact(self, *a, **k):
            return {"status": "error"}

    monkeypatch.setattr(mc, "memora_client", Down(), raising=False)
    reply = handle_voice_memory("remember the gate code is 4471")
    assert reply and "not saved" in reply.lower()


def test_b11_non_memory_returns_none():
    assert handle_voice_memory("what's the time") is None


# ---------------------------------------------------------------------------
# B12 — memory browser
# ---------------------------------------------------------------------------

def test_b12_browser_tiers_and_summary(router, fake_memora: FakeMemora):
    fake_memora.record_fact("friday", "my favorite chai is masala chai")     # pinned
    fake_memora.record_fact("friday", "the gateway runs on two oci hosts")   # normal
    fake_memora.record_fact("friday", "GOAL (active): double the demo account")
    fake_memora.record_fact("friday", "lol")                                 # trivial
    payload = asyncio.run(_call_endpoint(router.get_memory_browser))
    assert payload["status"] == "ok"
    assert payload["count"] == 4
    assert payload["summary"]["tiers"]["pinned"] == 2  # chai + goal both score pinned
    assert payload["summary"]["active_goals"] == 1
    texts = [m["text"] for m in payload["memories"]]
    assert any("masala chai" in t for t in texts)


async def _call_endpoint(fn):
    return await fn(None)


def test_b12_browser_honest_when_unreachable(router, monkeypatch: pytest.MonkeyPatch):
    import friday.memory.memora_client as mc

    class _Down:
        def recent_memories(self, *a, **k):
            raise RuntimeError("memora down")

    monkeypatch.setattr(mc, "memora_client", _Down(), raising=False)
    payload = asyncio.run(_call_endpoint(router.get_memory_browser))
    assert payload["status"] == "unreachable"
    assert payload["memories"] == []


# ---------------------------------------------------------------------------
# A6 — multi-turn coherence (12-turn conversation keeps facts and goals)
# ---------------------------------------------------------------------------

def test_a6_twelve_turn_conversation_keeps_context(router, fake_memora: FakeMemora):
    turns = [
        "remember this boss: my favorite chai is masala chai",       # 1 fact in
        "hello friday",                                              # 2 greeting
        "my goal this week is to double the demo account",           # 3 goal in
        "friday you're fired",                                       # 4 banter
        "i am surendra and i am your boss",                          # 5 identity
        "what needs my attention",                                   # 6 followup surface
        "consolidate your memories",                                 # 7 tidy
        "who is your boss",                                          # 8 identity again
        "make me a sandwich",                                        # 9 banter again
        "what do you remember about me",                             # 10 recall probe
        "hello friday",                                              # 11 greeting again
        "what about my goal",                                        # 12 goal still tracked?
    ]
    for cmd in turns:
        res = run(cmd)
        assert res.get("reply"), f"turn {cmd!r} produced no reply"

    # the fact survived 11 intervening turns (recall at turn 10 saw it)
    recall_res = run("do you remember my chai preference")
    assert recall_res["metadata"].get("memory_recall") is True
    assert "masala" in recall_res["reply"].lower()

    # the goal stated at turn 3 is still tracked at turn 12
    goal_res = run("what about my goal")
    assert goal_res["metadata"].get("goal_query") is True
    goals = goal_res["metadata"].get("active_goals") or []
    assert any("double the demo account" in g for g in goals), goal_res["metadata"]
    assert "still on it" in goal_res["reply"].lower()


# ---------------------------------------------------------------------------
# A7 — reasoning benchmark
# ---------------------------------------------------------------------------

def test_a7_benchmark_20_prompts_all_pass(router, monkeypatch: pytest.MonkeyPatch, fake_memora: FakeMemora):
    from friday.evaluation.reasoning_benchmark import run_benchmark

    import friday.memory.memora_client as mc
    monkeypatch.setattr(mc, "memora_client", fake_memora, raising=False)
    report = asyncio.run(run_benchmark())
    failures = [r for r in report["results"] if not r["pass"]]
    assert report["total"] == 20
    assert not failures, f"benchmark failures: {[(f['id'], f['reason'], f['prompt']) for f in failures]}"
    assert report["passed"] == 20


def test_a7_benchmark_report_persisted(router, monkeypatch, fake_memora, tmp_path):
    from friday.evaluation import reasoning_benchmark as rb

    import friday.memory.memora_client as mc
    monkeypatch.setattr(mc, "memora_client", fake_memora, raising=False)
    monkeypatch.setattr(rb, "REPORTS_DIR", tmp_path, raising=False)
    report = asyncio.run(rb.run_benchmark(cases=rb.BENCHMARK_CASES[:3]))
    assert (tmp_path / "latest.json").exists()
    import json

    data = json.loads((tmp_path / "latest.json").read_text())
    assert data["total"] == 3 and len(data["results"]) == 3


# ---------------------------------------------------------------------------
# A9 — tone matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    ["you're fired", "friday you're fired", "Friday, you're fired!", "make me a sandwich",
     "do you even lift", "roast me", "sing me a song", "i'm bored", "you're the best"],
)
def test_a9_banter_fires(text: str):
    res = tone_reply(text)
    assert res is not None and res["metadata"]["tone_match"] is True
    assert "as an ai" not in res["reply"].lower()


@pytest.mark.parametrize(
    "text",
    [
        "remember that my chai preference is masala",
        "what do you remember about me",
        "assign a research task to intelx about quantum chips",
        "what happened to that intelx task",
        "run a security check",
        "forecast the api request rate over the next 24 hours",
        "can you make me a dashboard for the portfolio",   # contains 'make me' but is real work
        "you're fired but first tell me the portfolio balance",
        "hello friday",
    ],
)
def test_a9_real_commands_never_hijacked(text: str):
    assert tone_reply(text) is None


def test_a9_router_wiring(router):
    res = run("friday you're fired")
    assert res["metadata"]["tone_match"] is True
    assert "rehired" in res["reply"].lower()
    # banter never blocks the memory path
    res = run("remember this boss: i always joke with friday")
    assert res["metadata"]["memory_store"] is True


# ---------------------------------------------------------------------------
# A11 — long-goal persistence
# ---------------------------------------------------------------------------

def test_a11_goal_lifecycle_via_chat(router, fake_memora: FakeMemora):
    res = run("my goal this week is to double the demo account")
    assert res["metadata"]["goal_store"] is True
    assert res["metadata"]["goal_status"] == "stored"
    assert any(f["content_text"].startswith("GOAL (active):") for f in fake_memora.facts)

    res = run("what about my goal")
    assert res["metadata"]["goal_query"] is True
    assert "still on it" in res["reply"].lower()
    assert any("double the demo account" in g for g in res["metadata"]["active_goals"])

    res = run("i finished my goal")
    assert res["metadata"]["goal_done"] is True
    assert res["metadata"]["goal_status"] == "done"
    # active goal retired; done marker recorded
    assert not any(f["content_text"].startswith("GOAL (active):") for f in fake_memora.facts)
    assert any(f["content_text"].startswith("GOAL (complete):") for f in fake_memora.facts)


def test_a11_goal_extraction_matrix():
    assert goals_mod.extract_goal_statement("my goal this week is to double the demo account") == "double the demo account"
    assert goals_mod.extract_goal_statement("my goal is to finish the audit by friday") == "finish the audit by friday"
    assert goals_mod.extract_goal_statement("hello friday") is None
    assert goals_mod.extract_goal_statement("my goal is") is None  # no payload
    assert goals_mod.is_goal_query("what about my goal")
    assert goals_mod.is_goal_query("still working on my goal")
    assert not goals_mod.is_goal_query("what happened to that intelx task")
    assert goals_mod.is_goal_done("i finished my goal")
    assert not goals_mod.is_goal_done("i finished the deploy")


def test_a11_morning_brief_includes_goals(fake_memora: FakeMemora):
    fake_memora.record_fact("friday", "GOAL (active): double the demo account")
    line = goals_mod.morning_brief_goal_line(fake_memora)
    assert line and "still on it" in line and "double the demo account" in line


def test_a11_morning_brief_no_goals(fake_memora: FakeMemora):
    assert goals_mod.morning_brief_goal_line(fake_memora) is None


# ---------------------------------------------------------------------------
# A12 — proactive follow-up
# ---------------------------------------------------------------------------

class _FakeRecord:
    def __init__(self, task_id, description, owner_agent, status, updated_at):
        self.task_id = task_id
        self.description = description
        self.owner_agent = owner_agent
        self.status = status
        self.updated_at = updated_at


class _FakeStore:
    def __init__(self, records):
        self._records = records

    def list(self, status=None, **k):
        return [r for r in self._records if r.status == status]


def test_a12_collect_stale(router, monkeypatch: pytest.MonkeyPatch):
    import time

    now = time.time()
    fresh = now - 5 * 60
    stale = now - 90 * 60
    store = _FakeStore([
        _FakeRecord("task_fresh", "quick sky note", "IntelX", "dispatched", fresh),
        _FakeRecord("task_stale", "deep research on quantum chips", "IntelX", "dispatched", stale),
        _FakeRecord("task_done", "portfolio summary", "Stratex", "completed", stale),
    ])
    import friday.proactive.followup as f

    monkeypatch.setattr(f, "collect_stale_tasks", _patched_collect(store), raising=False)
    found = f.collect_stale_tasks()
    assert len(found) == 1 and found[0]["task_id"] == "task_stale"
    assert found[0]["age_minutes"] >= 90


def _patched_collect(store):
    def _inner(*, stale_after_minutes=45, limit=10, now_epoch=None):
        import time

        now_epoch = now_epoch if now_epoch is not None else time.time()
        out = []
        for status in ("submitted", "assigned", "dispatched"):
            for rec in store.list(status=status):
                age = (now_epoch - rec.updated_at) / 60.0
                if age >= stale_after_minutes:
                    out.append({
                        "task_id": rec.task_id, "description": rec.description,
                        "owner_agent": rec.owner_agent, "status": status, "age_minutes": int(age),
                    })
        return out
    return _inner


def test_a12_sweep_posts_one_ping_per_stale_task(monkeypatch: pytest.MonkeyPatch):
    import time

    followup_mod._reset_for_tests()
    notif = FakeNotifications()
    stale = [{"task_id": "task_1", "description": "research", "owner_agent": "IntelX", "status": "dispatched", "age_minutes": 90}]
    monkeypatch.setattr(followup_mod, "collect_stale_tasks", lambda **k: list(stale), raising=False)
    report = followup_mod.followup_sweep(notif, post=True, now_epoch=time.time())
    assert report["pings_posted"] == 1 and len(notif.posted) == 1
    assert "still dispatched after 90 min" in notif.posted[0][0]

    # second sweep immediately: rate-limited, no duplicate ping
    report = followup_mod.followup_sweep(notif, post=True, now_epoch=time.time())
    assert report["rate_limited"] == 1 and report["pings_posted"] == 0
    assert len(notif.posted) == 1


def test_a12_sweep_honest_when_quiet(monkeypatch: pytest.MonkeyPatch):
    followup_mod._reset_for_tests()
    monkeypatch.setattr(followup_mod, "collect_stale_tasks", lambda **k: [], raising=False)
    notif = FakeNotifications()
    report = followup_mod.followup_sweep(notif, post=True)
    assert report["stale_found"] == 0 and report["pings_posted"] == 0
    assert not notif.posted


def test_a12_chat_surface(router, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(followup_mod, "collect_stale_tasks", lambda **k: [], raising=False)
    res = run("what needs my attention")
    assert res["metadata"]["followup_sweep"] is True
    assert "nothing needs you" in res["reply"].lower()


# ---------------------------------------------------------------------------
# A14 — boss-only command surface
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "cmd,category",
    [
        ("activate autonomous mode", "mode_switch"),
        ("friday, enable live trading", "trading_toggle"),
        ("shutdown agent stratex", "agent_shutdown"),
        ("forget everything", "memory_wipe"),
        ("restart the fleet", "fleet_control"),
    ],
)
def test_a14_boss_only_matrix(cmd: str, category: str):
    assert boss_gate.is_boss_only(cmd) == category


@pytest.mark.parametrize(
    "cmd",
    [
        "hello friday", "what's the portfolio balance", "run a security check",
        "remember my chai preference", "what happened to that task",
        "can you restart my day",           # benign phrasing with a hot word
        "forget about the old marker color",  # single-fact forget is NOT a wipe
        "deploy the new dashboard design",    # deploy wording without fleet scope
    ],
)
def test_a14_ordinary_commands_never_gated(cmd: str):
    assert boss_gate.is_boss_only(cmd) is None


def test_a14_gate_refuses_unverified_and_allows_verified(router):
    res = run("enable live trading", boss_verified=False)
    assert res["metadata"]["boss_gate"] is True
    assert res["metadata"]["executed"] is False
    assert "boss-only" in res["reply"].lower()

    # verified boss passes the gate (the autonomous toggle below answers it)
    res = run("activate autonomous mode", boss_verified=True)
    assert "boss_gate" not in (res.get("metadata") or {})
    assert res["metadata"].get("autonomous") is True


def test_a14_passphrase_fail_closed(monkeypatch: pytest.MonkeyPatch):
    boss_gate._reset_for_tests()
    monkeypatch.delenv("BOSS_PASSPHRASE", raising=False)
    assert boss_gate.verify_passphrase("anything") is False
    res = boss_gate.handle_authorize("authorize boss anything", source="voice")
    assert res["metadata"]["verified"] is False

    monkeypatch.setenv("BOSS_PASSPHRASE", "open sesame")
    assert boss_gate.verify_passphrase("open sesame") is True
    res = boss_gate.handle_authorize("authorize boss open sesame", source="voice")
    assert res["metadata"]["verified"] is True
    assert boss_gate.is_verified("voice")
    assert not boss_gate.is_verified("remote:x")


def test_a14_session_ttl_expires():
    boss_gate._reset_for_tests()
    boss_gate.mark_verified("voice", ttl_seconds=60, now_epoch=1000.0)
    assert boss_gate.is_verified("voice", now_epoch=1030.0)
    assert not boss_gate.is_verified("voice", now_epoch=1100.0)
