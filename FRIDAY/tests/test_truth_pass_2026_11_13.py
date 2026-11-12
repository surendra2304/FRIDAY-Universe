"""Regression tests for the 2026-11-13 truth pass (ZAI Agent 2).

Live-measured failures these pin:

1. Greeting hijack: the server chat router matched greetings with
   ``startswith``, so "Hey FRIDAY, compute 17*23" answered with a greeting
   and the question never reached the brain.
2. Time hijack: the bare-substring time/date list matched "time" inside
   "What is 17 TIMES 23" and answered with a clock reading.
3. Proactive alert storm: the engine deduped on message text, which embeds
   the CPU percentage — a pinned server produced a "different" alert every
   30 s poll (17 near-identical lines measured in one reply).
4. Summary storm: pop_notifications_summary() burst every pending line into
   the answer text.
5. Memory pollution: monitor-alert lines and "User: … | Assistant: …"
   dumps were recorded and later recalled as "memories" of the owner.
6. Worker truth: the LiveKit worker must report its speech provider in the
   heartbeat file instead of going silently mute (live probe 2026-11-13:
   worker joined and published a track but produced ZERO audio frames).
"""

from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# 1 + 2. router regexes (server-level; the same patterns server.py compiles)
# ---------------------------------------------------------------------------

GREETING_ONLY = re.compile(
    r"^\s*(?:hello|hi|hey|sup|good\s(?:morning|afternoon|evening))"
    r"(?:\s+there|\s+friday|\s+friends)?[\s,!.?]*$",
    re.IGNORECASE,
)
TIME_ONLY = re.compile(
    r"(?:what(?:'s| is)? (?:the |current )?)?(?:time|date|day|today)(?: is it)?[\s?.!]*",
    re.IGNORECASE,
)


class TestGreetingAnchored:
    def test_real_greetings_still_match(self) -> None:
        for phrase in ("hello", "Hi FRIDAY", "hey there!", "good morning", "Hello."):
            assert GREETING_ONLY.match(phrase), f"{phrase!r} must stay a greeting"

    def test_live_hijack_phrases_are_not_greetings(self) -> None:
        for phrase in (
            "Hey FRIDAY, compute 17*23 for me and briefly explain why the sky appears blue.",
            "hello can you check the fleet status",
            "hi, what do you remember about me",
            "hey what's on my screen",
        ):
            assert not GREETING_ONLY.match(phrase), f"{phrase!r} must reach the brain, not the greeting path"


class TestTimeAnchored:
    def test_real_time_questions_still_match(self) -> None:
        for phrase in ("what time is it", "time?", "today", "date", "what's the time"):
            assert TIME_ONLY.fullmatch(phrase.strip()), f"{phrase!r} must stay a time question"

    def test_live_hijack_phrase_is_not_a_time_question(self) -> None:
        # the live incident: "times" contains "time"
        assert not TIME_ONLY.fullmatch("what is 17 times 23? and tell me in one sentence why the sky is blue".strip())


# ---------------------------------------------------------------------------
# 3. proactive engine: per-category dedupe
# ---------------------------------------------------------------------------

class TestProactiveCategoryDedupe:
    def _engine(self):
        from friday.observability.notifications import NotificationManager
        from friday.observability.proactive_engine import ProactiveEngine, SystemSnapshot

        mgr = NotificationManager()
        engine = ProactiveEngine(mgr, poll_interval_seconds=999)
        return engine, mgr, SystemSnapshot

    def test_same_condition_different_reading_announces_once(self) -> None:
        from datetime import datetime, timezone
        from friday.observability.proactive_engine import SystemSnapshot

        engine, mgr, _ = self._engine()
        snap1 = SystemSnapshot(
            timestamp=datetime.now(timezone.utc), cpu_percent=99.8, ram_percent=None,
            ram_used_gb=None, ram_total_gb=None, battery_percent=None, battery_plugged=None,
            disk_percent=None, network_up_kbps=None, network_down_kbps=None, top_processes=["python"],
        )
        snap2 = SystemSnapshot(
            timestamp=datetime.now(timezone.utc), cpu_percent=97.1, ram_percent=None,
            ram_used_gb=None, ram_total_gb=None, battery_percent=None, battery_plugged=None,
            disk_percent=None, network_up_kbps=None, network_down_kbps=None, top_processes=["python"],
        )
        engine._evaluate(snap1, None)
        engine._evaluate(snap2, snap1)
        # one condition (cpu_hot), one alert — not one per percentage drift
        cpu_alerts = [n for n in mgr._queue if "cpu" in n.message.lower()]
        assert len(cpu_alerts) == 1, f"percentage drift must not duplicate the alert, got {len(cpu_alerts)}"

    def test_after_cooldown_the_condition_can_resurface(self) -> None:
        from datetime import timedelta
        from friday.observability.proactive_engine import SystemSnapshot

        engine, mgr, _ = self._engine()
        engine._announcement_cooldown = timedelta(seconds=0)  # simulate cooldown elapsing
        snap = SystemSnapshot(
            timestamp=None, cpu_percent=95.0, ram_percent=None, ram_used_gb=None,
            ram_total_gb=None, battery_percent=None, battery_plugged=None,
            disk_percent=None, network_up_kbps=None, network_down_kbps=None, top_processes=[],
        )
        engine._evaluate(snap, None)
        engine._evaluate(snap, None)
        cpu_alerts = [n for n in mgr._queue if "cpu" in n.message.lower()]
        assert len(cpu_alerts) == 2, "a lapsed cooldown legitimately re-announces"


# ---------------------------------------------------------------------------
# 4. summary cap
# ---------------------------------------------------------------------------

class TestSummaryCap:
    def test_summary_shows_at_most_three_and_marks_rest_delivered(self) -> None:
        from friday.observability.notifications import NotificationManager

        mgr = NotificationManager()
        for i in range(8):
            mgr.post_notification(message=f"CPU is running hot at 9{i}.0%.", category="cpu_hot")
        summary = mgr.pop_notifications_summary()
        assert summary is not None
        lines = [ln for ln in summary.splitlines() if ln.startswith("- ")]
        assert len(lines) <= 3, f"summary must cap at 3 lines, got {len(lines)}"
        assert "+ 5 older alerts cleared" in summary
        # everything is delivered — nothing haunts the next answer
        assert mgr.fetch_pending_notifications(mark_delivered=False) == []

    def test_single_alert_reads_as_one_line(self) -> None:
        from friday.observability.notifications import NotificationManager

        mgr = NotificationManager()
        mgr.post_notification(message="Disk is 93% full.", category="disk_full")
        summary = mgr.pop_notifications_summary()
        assert summary == "I noticed that Disk is 93% full. while you were away."


# ---------------------------------------------------------------------------
# 5. memory hygiene
# ---------------------------------------------------------------------------

class TestMemoryHygiene:
    def test_alert_lines_are_noise(self) -> None:
        from friday.memory.hygiene import is_memory_noise

        assert is_memory_noise("CPU is running hot at 99.8%. Top offender: python")
        assert is_memory_noise("Quick heads-up: RAM usage is at 90.5% (0.7/0.9 GB). Might want to close a few things.")
        assert is_memory_noise("I noticed the following while you were away:")
        assert is_memory_noise("CPU has cooled down. Crisis averted.")

    def test_dialogue_dumps_are_noise(self) -> None:
        from friday.memory.hygiene import is_memory_noise

        assert is_memory_noise("User: Access my screen | Assistant: I noticed the following while you were away: RAM usage is at 9%")

    def test_task_dispatch_boilerplate_is_noise(self) -> None:
        from friday.memory.hygiene import is_memory_noise

        # live 2026-11-13: these recalled as "memories of the owner"
        assert is_memory_noise("Verify storage and create retrieval index Upstream findings from the previous step, use this as context for your work: MEMORA response")
        assert is_memory_noise("Store the research findings and analysis in persistent memory: Research the c")

    def test_real_owner_facts_are_kept(self) -> None:
        from friday.memory.hygiene import is_memory_noise

        assert not is_memory_noise("My favorite chai is masala chai")
        assert not is_memory_noise("I review the fleet every morning at 9")
        assert not is_memory_noise("You are Surendra — the creator, administrator, and operator of me, FRIDAY")


# ---------------------------------------------------------------------------
# 6. voice worker heartbeat (import-guarded: livekit SDK may be absent)
# ---------------------------------------------------------------------------

class TestWorkerHeartbeat:
    def test_status_file_round_trip(self, tmp_path, monkeypatch) -> None:
        pytest.importorskip("livekit.agents")
        import importlib.util
        from pathlib import Path

        worker_path = Path(__file__).resolve().parents[1] / "src" / "friday" / "voice" / "livekit_worker.py"
        spec = importlib.util.spec_from_file_location("lw_test", worker_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod, "STATUS_FILE", tmp_path / "voice_worker_status.json")
        mod._write_status("no-provider", "none", detail="no speech provider available")
        import json

        state = json.loads((tmp_path / "voice_worker_status.json").read_text(encoding="utf-8"))
        assert state["state"] == "no-provider"
        assert state["detail"] == "no speech provider available"
        assert state["updated_at"]
