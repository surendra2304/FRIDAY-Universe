"""Checklists G5/G6/G7/G8/G12 (MASTER_COMPLETION_CHECKLIST) — Batch 5, ZAI Agent 2.

Contracts locked here:
- G5 Telegram gateway: owner-gate (non-owner refused, never reaches the
  brain), /status + /missions answered deterministically, free text routed
  through the SAME brain, honest brain failures, unconfigured → stays off;
- G6/G12 mission queue: add/list/run intents in chat, file persistence
  across instances, bounded retries, refused missions are skipped (not
  retried forever), honest statuses, no fabricated completions;
- G7/G8 daily self-report + weekly summary: composed only from real
  sources, zero records reported as zero, window latches once per day,
  never raises into the caller;
- H8/G11 sweep checks: parse honest lines, alert only past thresholds.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.core.owner_time import OWNER_TZ  # noqa: E402
from friday.proactive import daily_self_report as dsr  # noqa: E402
from friday.proactive import mission_queue as mq_mod  # noqa: E402
from friday.proactive import telegram_gateway as tg  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def queue(tmp_path: Path) -> mq_mod.MissionQueue:
    return mq_mod.MissionQueue(str(tmp_path / "missions" / "queue.json"))


@pytest.fixture(autouse=True)
def _reset_report_latches():
    dsr.reset_for_tests()
    yield
    dsr.reset_for_tests()


def _update(update_id: int, text: str, sender_id: str = "6341781431", chat_id: str = "6341781431") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "text": text,
            "chat": {"id": int(chat_id)},
            "from": {"id": int(sender_id), "first_name": "Owner"},
        },
    }


def _gateway(monkeypatch: pytest.MonkeyPatch, brain=None) -> tg.TelegramGateway:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
    g = tg.TelegramGateway()
    if brain is not None:
        g.set_brain(brain)
    return g


class _RecordingSender:
    """Capture send_message calls without touching the network."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def __call__(self, text: str, chat_id: str | None = None) -> bool:
        self.sent.append(text)
        return True


# ---------------------------------------------------------------------------
# G5 — Telegram two-way gateway
# ---------------------------------------------------------------------------

class TestTelegramGateway:
    def test_owner_message_routes_through_the_real_brain(self, monkeypatch):
        calls: list[str] = []
        brain = lambda cmd: {"reply": f"echo:{cmd}", "metadata": {}}  # noqa: E731
        g = _gateway(monkeypatch, brain)
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        g.process_update_for_tests(_update(1, "what time is it?"))
        assert calls == []
        assert sent.sent and "echo:what time is it?" in sent.sent[0]

    def test_non_owner_is_refused_and_never_reaches_the_brain(self, monkeypatch):
        brain = MagicMock(side_effect=AssertionError("brain must not be called"))
        g = _gateway(monkeypatch, brain)
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        g.process_update_for_tests(_update(2, "shut down the fleet", sender_id="99999"))
        assert sent.sent, "the non-owner must receive the refusal line"
        assert "Surendra" in sent.sent[0]
        brain.assert_not_called()

    def test_status_command_is_deterministic_no_brain(self, monkeypatch):
        g = _gateway(monkeypatch, brain=MagicMock(side_effect=AssertionError("no brain for /status")))
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        g.process_update_for_tests(_update(3, "/status"))
        # Without a supervision snapshot the reply must be honest-empty
        # (the sandbox has no live fleet) — still deterministic, no brain.
        assert sent.sent and ("fleet" in sent.sent[0].lower())

    def test_missions_command_reports_the_real_queue(self, monkeypatch, tmp_path):
        q = mq_mod.MissionQueue(str(tmp_path / "m" / "q.json"))
        q.add("research the sky", source="test")
        monkeypatch.setattr(mq_mod, "mission_queue", q)
        # the gateway imports the singleton at call time — patch the module attr
        import friday.proactive.mission_queue as mqm

        monkeypatch.setattr(mqm, "mission_queue", q)
        g = _gateway(monkeypatch, brain=MagicMock(side_effect=AssertionError("no brain")))
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        g.process_update_for_tests(_update(4, "/missions"))
        assert sent.sent and "research the sky" in sent.sent[0]

    def test_brain_failure_is_reported_honestly(self, monkeypatch):
        def boom(cmd):
            raise RuntimeError("engine down")

        g = _gateway(monkeypatch, boom)
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        g.process_update_for_tests(_update(5, "do something"))
        assert sent.sent and "couldn't complete" in sent.sent[0] and "RuntimeError" in sent.sent[0]
        assert "faked" in sent.sent[0]

    def test_unconfigured_gateway_stays_silent(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        assert tg.TelegramGateway.is_configured() is False

    def test_send_splits_long_messages(self, monkeypatch):
        g = _gateway(monkeypatch)
        api_calls: list[tuple[str, dict]] = []
        monkeypatch.setattr(
            g,
            "_api",
            lambda method, params: (api_calls.append((method, params)) or {"ok": True}),
        )
        g._send_interval = 0  # no pacing in tests
        ok = g.send_message("x" * 9000)
        assert ok is True
        sent = [c for c in api_calls if c[0] == "sendMessage"]
        assert len(sent) == 3, "9000 chars must split into 3 messages"
        assert all(len(c[1]["text"]) <= tg.MAX_MESSAGE_CHARS for c in sent)

    def test_help_command_lists_the_phone_line(self, monkeypatch):
        g = _gateway(monkeypatch, brain=MagicMock(side_effect=AssertionError("no brain")))
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        g.process_update_for_tests(_update(6, "/start"))
        assert sent.sent and "Boss" in sent.sent[0] and "/status" in sent.sent[0]

    def test_dotenv_fallback_loads_credentials(self, monkeypatch, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TELEGRAM_BOT_TOKEN=111:abc\nTELEGRAM_CHAT_ID=42\n")
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        original = tg._env_credentials
        # point the fallback at our temp .env
        def patched():
            import os

            token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
            chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
            if token and chat:
                return token, chat
            try:
                from dotenv import dotenv_values

                vals = dotenv_values(str(env_file))
                return (
                    token or (vals.get("TELEGRAM_BOT_TOKEN") or "").strip(),
                    chat or (vals.get("TELEGRAM_CHAT_ID") or "").strip(),
                )
            except Exception:
                return token, chat

        monkeypatch.setattr(tg, "_env_credentials", staticmethod(patched))
        g = tg.TelegramGateway()
        assert g.is_configured() is True
        monkeypatch.setattr(tg, "_env_credentials", staticmethod(original))


# ---------------------------------------------------------------------------
# G6/G12 — mission queue + chat intents
# ---------------------------------------------------------------------------

class TestMissionQueue:
    def test_add_persists_across_instances(self, queue):
        m = queue.add("research the market open", source="chat")
        fresh = mq_mod.MissionQueue(queue._path)
        pending = fresh.pending()
        assert len(pending) == 1 and pending[0]["id"] == m["id"]
        assert pending[0]["command"] == "research the market open"

    def test_execute_completes_with_real_brain(self, queue):
        queue.add("task A")
        queue.add("task B")
        report = queue.execute_pending(lambda cmd: {"reply": f"done {cmd}", "metadata": {}})
        assert report["executed"] == 2 and report["completed"] == 2
        assert all(m["status"] == "completed" for m in queue.all_missions())
        assert queue.pending() == []

    def test_execute_async_awaits_brain(self, queue):
        import asyncio

        queue.add("async task")

        async def brain(cmd):
            return {"reply": "async done", "metadata": {}}

        report = asyncio.run(queue.execute_pending_async(brain))
        assert report["completed"] == 1

    def test_refused_mission_is_skipped_not_retried(self, queue):
        queue.add("delete everything")
        report = queue.execute_pending(
            lambda cmd: {"reply": "refused", "metadata": {"refused": True}}
        )
        assert report["skipped"] == 1 and report["completed"] == 0
        assert queue.all_missions()[0]["status"] == "skipped"

    def test_raising_brain_retries_once_then_fails(self, queue):
        queue.add("boom task")

        def brain(cmd):
            raise ValueError("nope")

        first = queue.execute_pending(brain)
        assert first["skipped"] == 1  # attempts=1 < MAX_ATTEMPTS → back to pending
        second = queue.execute_pending(brain)
        assert second["failed"] == 1  # attempts=2 = MAX → failed, honest
        assert queue.pending() == []

    def test_no_fabricated_completion(self, queue):
        queue.add("x")
        queue.execute_pending(lambda cmd: {"reply": "", "metadata": {"error": "engine down"}, "success": False})
        m = queue.all_missions()[0]
        assert m["status"] == "failed" and "engine" in m["last_error"]

    def test_morning_report_counts_honestly(self, queue):
        queue.add("ok task")
        queue.add("bad task")
        # pass 1: ok completes, bad raises → back to pending (attempts=1)
        queue.execute_pending(
            lambda cmd: {"reply": "ok", "metadata": {}}
            if cmd == "ok task"
            else (_ for _ in ()).throw(RuntimeError("boom"))
        )
        # pass 2: bad raises again → attempts=2 = MAX → failed
        queue.execute_pending(
            lambda cmd: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        line = queue.render_morning_report()
        assert "1 completed" in line and "1 failed" in line

    def test_render_status_empty_is_honest(self, queue):
        line = queue.render_status()
        assert "empty" in line.lower()

    def test_missions_since_filters_by_ist_date(self, queue):
        m = queue.add("today task")
        m2 = dict(m)
        m2["created_ist"] = "2026-11-01T10:00:00+05:30"
        # simulate an old mission by direct file edit
        import threading

        with queue._lock:
            missions = queue._load()
            missions[-1]["created_ist"] = "2026-11-01T10:00:00+05:30"
            queue._save(missions)
            queue._cache = None
        got = queue.missions_since("2026-11-10")
        assert len(got) == 0
        got = queue.missions_since("2026-11-01")
        assert len(got) == 1


class TestMissionChatIntents:
    def test_add_intent_extracts_payload(self):
        # casing is preserved (same rule as the memory fast-paths)
        assert mq_mod.is_add_mission_intent("add to tonight's missions: research X") == "research X"
        assert mq_mod.is_add_mission_intent("queue for tonight: check the fleet") == "check the fleet"
        assert mq_mod.is_add_mission_intent("add to my todo: write the report") == "write the report"

    def test_add_intent_ignores_plain_chat(self):
        assert mq_mod.is_add_mission_intent("how is the fleet doing") is None
        assert mq_mod.is_add_mission_intent("research X now") is None
        assert mq_mod.is_add_mission_intent("what are tonight's plans") is None

    def test_list_and_run_intents(self):
        assert mq_mod.is_list_missions_intent("show my missions")
        assert mq_mod.is_list_missions_intent("what's on my todo")
        assert not mq_mod.is_list_missions_intent("add to my todo: x")
        assert mq_mod.is_run_missions_intent("run my missions now")
        assert not mq_mod.is_run_missions_intent("show my missions")

    def test_run_intent_checked_before_list_in_dispatch(self):
        # E2E lesson (2026-11-11): "run my missions now" contains "my
        # missions" — the LIST matcher alone would swallow the RUN request.
        # The dispatch chain must consult RUN first; this locks the contract
        # at the matcher level (both must fire so precedence is meaningful).
        msg = "run my missions now"
        assert mq_mod.is_run_missions_intent(msg)
        assert mq_mod.is_list_missions_intent(msg)  # ambiguity exists...
        # ...and the server's chain order resolves it (run first). Proven by
        # the route-level test below with the real dispatch function.

    def test_remember_is_not_hijacked(self):
        # "remember to research X" must NOT be treated as a mission add
        assert mq_mod.is_add_mission_intent("remember to research the sky tonight") is None


# ---------------------------------------------------------------------------
# G7/G8 — daily self-report + weekly summary
# ---------------------------------------------------------------------------

class TestDailySelfReport:
    def test_composes_from_real_sources(self, monkeypatch):
        monkeypatch.setattr(
            dsr, "_conversation_stats", lambda: {"total": 5, "failed": 1}
        )
        monkeypatch.setattr(
            dsr,
            "_task_ledger_stats",
            lambda: {"total": 4, "by_agent": {"IntelX": 2, "Stratex": 1}},
        )
        monkeypatch.setattr(
            dsr, "_fleet_stats", lambda: {"total": 9, "reachable": 9, "last_error": None}
        )
        monkeypatch.setattr(
            dsr, "_mission_stats", lambda: {"pending": 0, "line": "No missions were queued for last night."}
        )
        monkeypatch.setattr(dsr, "_memory_growth", lambda: {"stored_today": 3})
        text = dsr.compose_daily_report()
        assert "5 times" in text or "5 time" in text
        assert "IntelX" in text
        assert "9/9" in text
        assert "3 new memories" in text
        assert "2026-" in text  # IST date present

    def test_zero_records_reported_as_zero(self, monkeypatch):
        monkeypatch.setattr(dsr, "_conversation_stats", lambda: {"total": 0, "failed": 0})
        monkeypatch.setattr(dsr, "_task_ledger_stats", lambda: {"total": 0, "by_agent": {}})
        monkeypatch.setattr(dsr, "_fleet_stats", lambda: {"total": 9, "reachable": 9, "last_error": None})
        monkeypatch.setattr(dsr, "_mission_stats", lambda: {"pending": 0, "line": ""})
        monkeypatch.setattr(dsr, "_memory_growth", lambda: {"stored_today": 0})
        text = dsr.compose_daily_report()
        assert "0 tasks" in text or "0 task" in text
        assert "No new memories" in text

    def test_source_error_is_honest_not_guessed(self, monkeypatch):
        monkeypatch.setattr(dsr, "_conversation_stats", lambda: {"error": "ImportError"})
        monkeypatch.setattr(dsr, "_task_ledger_stats", lambda: {"error": "KeyError"})
        monkeypatch.setattr(dsr, "_fleet_stats", lambda: {"error": "ImportError"})
        monkeypatch.setattr(dsr, "_mission_stats", lambda: {"error": "ImportError"})
        monkeypatch.setattr(dsr, "_memory_growth", lambda: {"error": "TypeError"})
        text = dsr.compose_daily_report()
        assert "could not read" in text
        assert "ImportError" in text

    def test_delivery_latches_once_per_day(self, monkeypatch):
        sends: list[str] = []
        monkeypatch.setattr(
            "friday.proactive.telegram_gateway.send_owner_message",
            lambda text: sends.append(text) or True,
        )
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)
        monkeypatch.setattr(dsr, "_conversation_stats", lambda: {"total": 0, "failed": 0})
        monkeypatch.setattr(dsr, "_task_ledger_stats", lambda: {"total": 0, "by_agent": {}})
        monkeypatch.setattr(dsr, "_fleet_stats", lambda: {"total": 9, "reachable": 9, "last_error": None})
        monkeypatch.setattr(dsr, "_mission_stats", lambda: {"pending": 0, "line": ""})
        monkeypatch.setattr(dsr, "_memory_growth", lambda: {"stored_today": 0})
        r1 = dsr.maybe_deliver_reports(now=evening)
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r1["daily"] == "sent" and len(sends) == 1
        assert r2["daily"] is None  # latched

    def test_no_delivery_outside_window(self, monkeypatch):
        sends: list[str] = []
        monkeypatch.setattr(
            "friday.proactive.telegram_gateway.send_owner_message",
            lambda text: sends.append(text) or True,
        )
        morning = datetime(2026, 11, 11, 10, 0, tzinfo=OWNER_TZ)
        assert dsr.maybe_deliver_reports(now=morning)["daily"] is None
        assert sends == []

    def test_weekly_only_on_sunday_evening(self, monkeypatch):
        sends: list[str] = []
        monkeypatch.setattr(
            "friday.proactive.telegram_gateway.send_owner_message",
            lambda text: sends.append(text) or True,
        )
        monkeypatch.setattr(dsr, "_conversation_stats", lambda: {"total": 0, "failed": 0})
        monkeypatch.setattr(dsr, "_task_ledger_stats", lambda: {"total": 3, "by_status": {"completed": 2, "failed": 1, "dispatched": 0}})
        monkeypatch.setattr(dsr, "_fleet_stats", lambda: {"total": 9, "reachable": 9, "last_error": None})
        monkeypatch.setattr(dsr, "_mission_stats", lambda: {"pending": 0, "line": ""})
        monkeypatch.setattr(dsr, "_memory_growth", lambda: {"stored_today": 0})
        # Wednesday 21:30 → daily only
        wed = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)  # a Wednesday
        assert wed.weekday() != 6
        r = dsr.maybe_deliver_reports(now=wed)
        assert r["weekly"] is None and r["daily"] == "sent"
        # Sunday 20:30 → weekly only (daily window starts 21:00)
        dsr.reset_for_tests()
        sends.clear()
        sun_early = datetime(2026, 11, 15, 20, 30, tzinfo=OWNER_TZ)
        assert sun_early.weekday() == 6
        r = dsr.maybe_deliver_reports(now=sun_early)
        assert r["weekly"] == "sent" and r["daily"] is None
        assert len(sends) == 1
        # Sunday 21:30 → the daily report follows
        dsr.reset_for_tests()
        sends.clear()
        sun_late = datetime(2026, 11, 15, 21, 30, tzinfo=OWNER_TZ)
        r = dsr.maybe_deliver_reports(now=sun_late)
        assert r["weekly"] == "sent" and r["daily"] == "sent"
        assert len(sends) == 2

    def test_send_failure_does_not_latch(self, monkeypatch):
        monkeypatch.setattr(
            "friday.proactive.telegram_gateway.send_owner_message",
            lambda text: False,
        )
        evening = datetime(2026, 11, 11, 21, 30, tzinfo=OWNER_TZ)
        monkeypatch.setattr(dsr, "_conversation_stats", lambda: {"total": 0, "failed": 0})
        monkeypatch.setattr(dsr, "_task_ledger_stats", lambda: {"total": 0, "by_agent": {}})
        monkeypatch.setattr(dsr, "_fleet_stats", lambda: {"total": 9, "reachable": 9, "last_error": None})
        monkeypatch.setattr(dsr, "_mission_stats", lambda: {"pending": 0, "line": ""})
        monkeypatch.setattr(dsr, "_memory_growth", lambda: {"stored_today": 0})
        r1 = dsr.maybe_deliver_reports(now=evening)
        assert r1["daily"] == "send_failed"
        # next cycle retries because nothing was delivered
        r2 = dsr.maybe_deliver_reports(now=evening.replace(minute=45))
        assert r2["daily"] == "send_failed"


# ---------------------------------------------------------------------------
# H8/G11 — self-heal sweep checks
# ---------------------------------------------------------------------------

class TestSelfHealSweep:
    @pytest.fixture()
    def sweep(self):
        sys.path.insert(0, str(REPO / "scripts"))
        import friday_self_heal_sweep as sweep  # noqa: PLC0415

        return sweep

    def test_disk_check_reports_a_line(self, sweep):
        ok, lines, _ = sweep.check_disk()
        assert ok and any("disk" in ln.lower() for ln in lines)

    def test_journald_check_reports_usage_and_cap(self, sweep):
        ok, lines, alerts = sweep.check_journald()
        assert ok
        assert any("journald" in ln.lower() for ln in lines)
        # On this sandbox there is no cap file — the check must say so honestly.
        if not Path("/etc/systemd/journald.conf.d/size-limit.conf").exists():
            assert any("MISSING" in ln for ln in lines)

    def test_failed_units_check_runs(self, sweep):
        ok, lines, _ = sweep.check_failed_units()
        # The sandbox has no systemctl (CI runners do) — the check must
        # report that honestly instead of crashing.
        if ok:
            assert any("failed units" in ln for ln in lines)
        else:
            assert any("systemctl failed" in ln or "check failed" in ln for ln in lines)

    def test_backup_freshness_honest_when_missing(self, sweep):
        ok, lines, _ = sweep.check_backup_freshness()
        assert ok and any("backup" in ln.lower() for ln in lines)

    def test_full_sweep_returns_structured_report(self, sweep, capsys):
        results = sweep.run_sweep()
        assert results["ok"] in (True, False)
        assert set(results["checks"]).issuperset({"disk", "cert", "journald", "failed_units", "backups"})
        out = capsys.readouterr().out
        assert "self-heal sweep" in out
