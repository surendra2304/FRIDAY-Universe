"""TASK-INT-016: IntelX instant-alert fast lane (TASK-INT-015 follow-up).

Since TASK-INT-015, IntelX appends every instant-class envelope
(big breaks: alert_class="instant", severity="high",
quiet_hours_exempt=true) to BOTH the main outbox and a sibling
instant_outbox.jsonl. Until this task nothing read the instant file,
so a big break waited for the main lane's drain cycle like any digest
item. The fast lane tails the instant file on a short cadence through
the SAME drainer state as the PRO-002 main lane.

Rules pinned here:
- an instant envelope is delivered exactly once across both lanes —
  whichever lane reaches it first posts it, the other counts it as a
  duplicate (the persisted delivered_keys are the shared record);
- instant delivery preserves the envelope's severity "high" (the
  INT-015 fleet vocabulary) and stamps trigger
  intelx_watch_instant_alert / lane=instant metadata;
- the instant lane's first cycle is a silent baseline of its own —
  a pre-existing instant backlog is recorded as seen, never announced;
- an exempt instant envelope posts immediately inside quiet hours;
  a (hypothetical) non-exempt envelope in the instant file is held
  under the same policy and flushes via the main lane's digest;
- malformed lines, partial lines and a missing instant file are
  tolerated exactly like the main lane; dedupe survives a restart;
- a failed instant post is held and retried via the shared held queue;
- kill switch off -> neither lane posts and no state file is written.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

from friday.core.owner_time import OWNER_TZ
from friday.proactive import intelx_watch as iw
from datetime import datetime


class _FakeNotifications:
    def __init__(self, fail: bool = False):
        self.posted = []
        self.fail = fail

    def post_notification(self, message, category="x", severity="info", metadata=None, notification_id=None):
        if self.fail:
            raise RuntimeError("notification store unavailable")
        self.posted.append(
            {"message": message, "category": category, "severity": severity, "metadata": metadata or {}}
        )
        return f"id-{len(self.posted)}"


def _at(hour: int, minute: int = 0, day: int = 15) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=OWNER_TZ)


def _envelope(fp: str = "0123456789abcdef", **kw):
    """One digest-class envelope exactly as IntelX's build_envelope writes it."""
    env = {
        "schema": "intelx.watch_alert/1",
        "envelope_id": f"sha-{fp}",
        "dedupe_key": f"intelx.watch:ai_model_releases:{fp}",
        "watch_id": "ai_model_releases",
        "domain": "ai_models",
        "alert_class": "digest",
        "severity": "info",
        "quiet_hours_exempt": False,
        "title": "Introducing Images 2.6",
        "summary": "A new image model is now available via the API.",
        "url": "https://openai.com/index/images-2-6",
        "publisher": "OpenAI Blog",
        "published_at": "2026-11-04T00:00:00+00:00",
        "fired_at": "2026-11-15T10:00:00+05:30",
        "score": 5,
        "score_reasons": ["release_language:+3"],
        "provenance": {
            "source_feed": "https://openai.com/news/rss.xml",
            "fetched_at": "2026-11-15T10:00:00+05:30",
            "task": "TASK-INT-007",
        },
    }
    env.update(kw)
    return env


def _instant_envelope(fp: str = "fedcba9876543210", **kw):
    """One instant-class envelope as TASK-INT-015's build_envelope writes it."""
    env = _envelope(
        fp,
        watch_id="crypto_market_structure",
        domain="markets",
        alert_class="instant",
        severity="high",
        quiet_hours_exempt=True,
        title="Exchange suspends all withdrawals after exploit",
        score=6,
        score_reasons=["venue_incident:+3", "exchange_structure:+3"],
    )
    env["dedupe_key"] = f"intelx.watch:crypto_market_structure:{fp}"
    env.update(kw)
    return env


class _World:
    """A synthetic IntelX watches dir (main + instant outbox) + drainer."""

    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "intelx" / "data" / "watches"
        self.outbox = self.dir / "outbox.jsonl"
        self.instant_outbox = self.dir / "instant_outbox.jsonl"
        self.state_path = tmp_path / "drainer_state.json"
        self.notifications = _FakeNotifications()

    def drainer(self, enabled: bool = True) -> iw.IntelxWatchDrainer:
        return iw.IntelxWatchDrainer(
            outbox_path=self.outbox,
            instant_outbox_path=self.instant_outbox,
            state_path=self.state_path,
            enabled_fn=lambda: enabled,
        )

    def _append(self, path: Path, rows) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                if isinstance(row, str):
                    fh.write(row + "\n")
                else:
                    fh.write(json.dumps(row) + "\n")

    def append_main(self, *rows) -> None:
        self._append(self.outbox, rows)

    def append_instant(self, *rows) -> None:
        self._append(self.instant_outbox, rows)


@pytest.fixture()
def world(tmp_path) -> _World:
    return _World(tmp_path)


def _baseline_both(world: _World, drainer, when=None):
    when = when or _at(10, 0)
    drainer.run_cycle(world.notifications, now=when)
    drainer.run_instant_cycle(world.notifications, now=when)


# ---------------------------------------------------------------------------
# cross-lane delivery + dedupe
# ---------------------------------------------------------------------------


def test_instant_lane_delivers_first_main_lane_counts_duplicate(world):
    drainer = world.drainer()
    _baseline_both(world, drainer)
    env = _instant_envelope()
    # IntelX writes the instant envelope to BOTH files (INT-015).
    world.append_instant(env)
    world.append_main(env)

    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 5))
    assert report["lane"] == "instant"
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 1
    post = world.notifications.posted[0]
    assert post["category"] == "intelx_watch"
    assert post["severity"] == "high"  # INT-015 vocabulary, not clamped to info
    assert post["metadata"]["source"] == "TASK-INT-016"
    assert post["metadata"]["trigger"] == "intelx_watch_instant_alert"
    assert post["metadata"]["lane"] == "instant"
    assert post["metadata"]["alert_class"] == "instant"
    assert post["metadata"]["dedupe_key"] == env["dedupe_key"]

    # The main lane later reads the same envelope from the main outbox:
    # consumed, counted as a duplicate, never delivered twice.
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["duplicates"] == 1
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1


def test_main_lane_delivers_first_instant_lane_counts_duplicate(world):
    drainer = world.drainer()
    _baseline_both(world, drainer)
    env = _instant_envelope()
    world.append_main(env)
    world.append_instant(env)

    report = drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert report["posted"] == 1
    post = world.notifications.posted[0]
    assert post["severity"] == "high"
    assert post["metadata"]["trigger"] == "intelx_watch_alert"
    assert post["metadata"]["lane"] == "main"

    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 6))
    assert report["duplicates"] == 1
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1


def test_instant_dedupe_survives_restart(world):
    drainer = world.drainer()
    _baseline_both(world, drainer)
    env = _instant_envelope()
    world.append_instant(env)
    drainer.run_instant_cycle(world.notifications, now=_at(10, 5))
    assert len(world.notifications.posted) == 1

    restarted = world.drainer()
    world.append_instant(env)  # producer re-fires the same envelope
    report = restarted.run_instant_cycle(world.notifications, now=_at(10, 10))
    assert report["duplicates"] == 1
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1


# ---------------------------------------------------------------------------
# baseline + quiet hours
# ---------------------------------------------------------------------------


def test_instant_baseline_is_silent_for_preexisting_backlog(world):
    world.append_instant(_instant_envelope("aaaaaaaaaaaaaaaa"))
    drainer = world.drainer()

    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 0))
    assert report["baseline"] is True
    assert world.notifications.posted == []

    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 5))
    assert report["posted"] == 0
    assert world.notifications.posted == []


def test_instant_envelope_posts_immediately_inside_quiet_hours(world):
    drainer = world.drainer()
    _baseline_both(world, drainer, when=_at(22, 0))
    world.append_instant(_instant_envelope())

    report = drainer.run_instant_cycle(world.notifications, now=_at(23, 30))
    assert report["posted"] == 1
    assert report["held"] == 0
    assert len(world.notifications.posted) == 1


def test_non_exempt_envelope_in_instant_file_is_held_then_digest_flushed(world):
    drainer = world.drainer()
    _baseline_both(world, drainer, when=_at(22, 0))
    # The envelope's flag is the policy input even on the fast lane: a
    # non-exempt envelope is held in quiet hours like any digest item.
    world.append_instant(_instant_envelope(quiet_hours_exempt=False, severity="info"))

    report = drainer.run_instant_cycle(world.notifications, now=_at(23, 30))
    assert report["posted"] == 0
    assert report["held"] == 1
    assert world.notifications.posted == []

    # The shared held queue flushes as ONE digest via the main lane.
    report = drainer.run_cycle(world.notifications, now=_at(7, 15, day=16))
    assert report["flushed"] == 1
    assert len(world.notifications.posted) == 1
    assert "held for you" in world.notifications.posted[0]["message"]


# ---------------------------------------------------------------------------
# robustness
# ---------------------------------------------------------------------------


def test_instant_malformed_and_partial_lines_tolerated(world):
    drainer = world.drainer()
    _baseline_both(world, drainer)
    env = _instant_envelope()
    world.append_instant("{not json", json.dumps({"schema": "other/9"}))
    # A trailing partial line (writer mid-append) is not consumed yet.
    world.instant_outbox.parent.mkdir(parents=True, exist_ok=True)
    with world.instant_outbox.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(env))  # no newline yet

    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 5))
    assert report["malformed"] == 2
    assert report["posted"] == 0
    assert report["source_errors"] == []

    with world.instant_outbox.open("a", encoding="utf-8") as fh:
        fh.write("\n")
    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 6))
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 1


def test_missing_instant_outbox_is_tolerated(world):
    drainer = world.drainer()
    report = drainer.run_instant_cycle(world.notifications, now=_at(10, 0))
    assert report["instant_outbox_present"] is False
    assert report["source_errors"] == []
    assert world.notifications.posted == []


def test_instant_post_failure_is_held_and_retried_via_main_flush(world):
    drainer = world.drainer()
    _baseline_both(world, drainer)
    world.append_instant(_instant_envelope())

    failing = _FakeNotifications(fail=True)
    report = drainer.run_instant_cycle(failing, now=_at(10, 5))
    assert report["post_failures"] == 1
    assert report["held"] == 1

    # Outside quiet hours the main lane's flush retries the held alert
    # as a digest and marks the key delivered — it is never lost.
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["flushed"] == 1
    assert len(world.notifications.posted) == 1


def test_kill_switch_off_no_posts_no_state(world):
    drainer = world.drainer(enabled=False)
    world.append_instant(_instant_envelope())
    world.append_main(_envelope())

    r1 = drainer.run_instant_cycle(world.notifications, now=_at(10, 0))
    r2 = drainer.run_cycle(world.notifications, now=_at(10, 0))
    assert r1["enabled"] is False and r2["enabled"] is False
    assert world.notifications.posted == []
    assert not world.state_path.exists()


# ---------------------------------------------------------------------------
# path resolution (producer/consumer symmetry with IntelX's default)
# ---------------------------------------------------------------------------


def test_resolve_instant_outbox_path_sibling_default(tmp_path, monkeypatch):
    monkeypatch.delenv("INTELX_WATCH_INSTANT_OUTBOX_PATH", raising=False)
    main = tmp_path / "watches" / "outbox.jsonl"
    assert iw.resolve_instant_outbox_path(main) == tmp_path / "watches" / "instant_outbox.jsonl"


def test_resolve_instant_outbox_path_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "elsewhere" / "fast.jsonl"
    monkeypatch.setenv("INTELX_WATCH_INSTANT_OUTBOX_PATH", str(custom))
    assert iw.resolve_instant_outbox_path(tmp_path / "outbox.jsonl") == custom


def test_drainer_defaults_instant_path_to_main_sibling(world):
    drainer = iw.IntelxWatchDrainer(
        outbox_path=world.outbox,
        state_path=world.state_path,
        enabled_fn=lambda: True,
    )
    assert drainer._instant_outbox_path == world.instant_outbox
