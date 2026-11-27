"""TASK-PRO-002: IntelX standing-watch outbox drainer (PRO-001 extension).

IntelX standing watches (TASK-INT-007) append alert envelopes
(schema intelx.watch_alert/1) to an append-only JSONL outbox; this
drainer tails that outbox and delivers through the real
NotificationManager path under the STANDING_WATCHES.md §4 contract.

Rules pinned here:
- an envelope appended after the baseline is delivered exactly once,
  with its dedupe_key/watch_id in the notification metadata;
- the first cycle on a fresh drainer state is a silent baseline —
  pre-existing outbox content is recorded as seen, never announced;
- dedupe survives a drainer restart (persisted delivered keys) and an
  outbox that is rebuilt from scratch (offset reset cannot re-deliver);
- quiet hours 23:00-07:00 IST hold non-exempt envelopes; held alerts
  survive a restart and flush as ONE digest at/after 07:00;
- an envelope with quiet_hours_exempt=true is delivered immediately
  even inside quiet hours (the flag is the policy input);
- malformed lines (bad JSON, non-object, wrong schema, missing
  dedupe_key) are skipped and counted — the cycle never raises and
  the tail never wedges;
- a missing outbox is tolerated (watches not enabled yet) and an
  outbox created later drains normally;
- a trailing partial line (writer mid-append) is not consumed until
  it is newline-terminated;
- kill switch off -> no posts, no state file, no churn.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

from friday.core.owner_time import OWNER_TZ
from friday.proactive import intelx_watch as iw


class _FakeNotifications:
    def __init__(self):
        self.posted = []

    def post_notification(self, message, category="x", severity="info", metadata=None, notification_id=None):
        self.posted.append(
            {"message": message, "category": category, "severity": severity, "metadata": metadata or {}}
        )
        return f"id-{len(self.posted)}"


def _at(hour: int, minute: int = 0, day: int = 15) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=OWNER_TZ)


def _envelope(fp: str = "0123456789abcdef", **kw):
    """One envelope exactly as IntelX's build_envelope writes it."""
    env = {
        "schema": "intelx.watch_alert/1",
        "envelope_id": f"sha-{fp}",
        "dedupe_key": f"intelx.watch:ai_model_releases:{fp}",
        "watch_id": "ai_model_releases",
        "severity": "info",
        "quiet_hours_exempt": False,
        "title": "Introducing Images 2.6",
        "summary": "A new image model is now available via the API.",
        "url": "https://openai.com/index/images-2-6",
        "publisher": "OpenAI Blog",
        "published_at": "2026-11-04T00:00:00+00:00",
        "fired_at": "2026-11-15T10:00:00+05:30",
        "score": 5,
        "score_reasons": ["release_language:+3", "model_family_version:+3"],
        "provenance": {
            "source_feed": "https://openai.com/news/rss.xml",
            "fetched_at": "2026-11-15T10:00:00+05:30",
            "task": "TASK-INT-007",
        },
    }
    env.update(kw)
    return env


class _World:
    """A synthetic IntelX outbox + drainer wired to it."""

    def __init__(self, tmp_path: Path):
        self.outbox = tmp_path / "intelx" / "data" / "watches" / "outbox.jsonl"
        self.state_path = tmp_path / "drainer_state.json"
        self.notifications = _FakeNotifications()

    def drainer(self) -> iw.IntelxWatchDrainer:
        return iw.IntelxWatchDrainer(
            outbox_path=self.outbox,
            state_path=self.state_path,
            enabled_fn=lambda: True,
        )

    def append(self, *rows) -> None:
        self.outbox.parent.mkdir(parents=True, exist_ok=True)
        with self.outbox.open("a", encoding="utf-8") as fh:
            for row in rows:
                if isinstance(row, str):
                    fh.write(row + "\n")
                else:
                    fh.write(json.dumps(row) + "\n")

    def write_raw(self, text: str) -> None:
        self.outbox.parent.mkdir(parents=True, exist_ok=True)
        self.outbox.write_text(text, encoding="utf-8")


@pytest.fixture()
def world(tmp_path) -> _World:
    return _World(tmp_path)


def _baseline(world: _World, drainer=None, when=None):
    """Run the first (baseline) cycle; returns the cycle report."""
    drainer = drainer or world.drainer()
    return drainer.run_cycle(world.notifications, now=when or _at(10, 0))


# ---------------------------------------------------------------------------
# delivery
# ---------------------------------------------------------------------------


def test_delivery_posts_envelope_via_notification_manager(world):
    drainer = world.drainer()
    _baseline(world, drainer)  # outbox missing at first: baseline still completes
    env = _envelope()
    world.append(env)

    report = drainer.run_cycle(world.notifications, now=_at(10, 5))

    assert report["posted"] == 1
    assert len(world.notifications.posted) == 1
    post = world.notifications.posted[0]
    assert post["category"] == "intelx_watch"
    assert post["severity"] == "info"
    assert "Introducing Images 2.6" in post["message"]
    assert "https://openai.com/index/images-2-6" in post["message"]
    assert post["metadata"]["dedupe_key"] == env["dedupe_key"]
    assert post["metadata"]["watch_id"] == "ai_model_releases"
    assert post["metadata"]["source"] == "TASK-PRO-002"
    assert post["metadata"]["trigger"] == "intelx_watch_alert"

    # An idle cycle posts nothing more.
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1


def test_baseline_is_silent_for_preexisting_outbox(world):
    world.append(_envelope("aaaaaaaaaaaaaaaa"), _envelope("bbbbbbbbbbbbbbbb"))
    drainer = world.drainer()

    report = drainer.run_cycle(world.notifications, now=_at(10, 0))

    assert report["baseline"] is True
    assert world.notifications.posted == []

    # And they stay silent on later cycles too.
    report = drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert report["posted"] == 0
    assert world.notifications.posted == []


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------


def test_dedupe_across_restart_and_duplicate_lines(world):
    drainer = world.drainer()
    _baseline(world, drainer)
    env = _envelope()
    world.append(env)
    drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert len(world.notifications.posted) == 1

    # Restart: a brand-new drainer over the same persisted state.
    restarted = world.drainer()
    report = restarted.run_cycle(world.notifications, now=_at(10, 10))
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1

    # The producer re-fires the same envelope (same dedupe_key): the
    # line is consumed but never delivered a second time.
    world.append(env)
    report = restarted.run_cycle(world.notifications, now=_at(10, 15))
    assert report["duplicates"] == 1
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1


def test_outbox_rebuilt_from_scratch_cannot_redeliver(world):
    drainer = world.drainer()
    _baseline(world, drainer)
    env_a = _envelope("aaaaaaaaaaaaaaaa")
    env_b = _envelope("bbbbbbbbbbbbbbbb", title="Gemini 4 ships")
    world.append(env_a, env_b)
    drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert len(world.notifications.posted) == 2

    # The outbox is swapped for a fresh, smaller file containing only
    # envelope A again: the tail restarts at 0, and the persisted
    # dedupe key — not the offset — is what stops a second delivery.
    world.write_raw(json.dumps(env_a) + "\n")
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["duplicates"] == 1
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 2

    # Offset tracking still works after the reset: a new envelope
    # appended to the rebuilt outbox drains normally.
    env_c = _envelope("cccccccccccccccc", title="Qwen 5 released")
    world.append(env_c)
    report = drainer.run_cycle(world.notifications, now=_at(10, 15))
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 3
    assert "Qwen 5 released" in world.notifications.posted[2]["message"]


# ---------------------------------------------------------------------------
# quiet hours
# ---------------------------------------------------------------------------


def test_quiet_hours_hold_then_single_digest_after_0700(world):
    drainer = world.drainer()
    _baseline(world, drainer, when=_at(22, 0))
    world.append(_envelope())

    report = drainer.run_cycle(world.notifications, now=_at(23, 30))
    assert report["held"] == 1
    assert report["posted"] == 0
    assert world.notifications.posted == []

    # Restart inside quiet hours: the held alert survives, still unposted.
    restarted = world.drainer()
    report = restarted.run_cycle(world.notifications, now=_at(23, 45))
    assert report["posted"] == 0
    assert world.notifications.posted == []

    # After 07:00 the held alert flushes as exactly ONE digest.
    report = restarted.run_cycle(world.notifications, now=_at(7, 15, day=16))
    assert report["flushed"] == 1
    assert len(world.notifications.posted) == 1
    digest = world.notifications.posted[0]
    assert digest["metadata"]["trigger"] == "quiet_hours_digest"
    assert "Introducing Images 2.6" in digest["message"]

    # Nothing is left to flush or re-deliver afterwards.
    report = restarted.run_cycle(world.notifications, now=_at(7, 20, day=16))
    assert report["posted"] == 0
    assert len(world.notifications.posted) == 1


def test_quiet_hours_exempt_envelope_delivers_immediately(world):
    drainer = world.drainer()
    _baseline(world, drainer, when=_at(22, 0))
    world.append(_envelope(quiet_hours_exempt=True))

    report = drainer.run_cycle(world.notifications, now=_at(23, 30))
    assert report["posted"] == 1
    assert report["held"] == 0
    assert len(world.notifications.posted) == 1


# ---------------------------------------------------------------------------
# robustness: malformed lines, missing outbox, partial writes
# ---------------------------------------------------------------------------


def test_malformed_lines_skipped_never_crash_never_wedge(world):
    drainer = world.drainer()
    _baseline(world, drainer)
    good = _envelope()
    world.append(
        "this is not json at all",
        '["a", "json", "array"]',
        {"schema": "something.else/9", "dedupe_key": "intelx.watch:x:1"},
        {"schema": "intelx.watch_alert/1", "title": "no dedupe key here"},
        "",
        good,
    )

    report = drainer.run_cycle(world.notifications, now=_at(10, 5))

    assert report["malformed"] == 4
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 1
    assert world.notifications.posted[0]["metadata"]["dedupe_key"] == good["dedupe_key"]

    # The tail is not wedged on the poison lines: the next good
    # envelope drains normally and malformed does not recount.
    world.append(_envelope("cccccccccccccccc", title="Qwen 5 released"))
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["malformed"] == 0
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 2


def test_missing_outbox_tolerated_then_created(world):
    drainer = world.drainer()
    assert not world.outbox.exists()

    report = drainer.run_cycle(world.notifications, now=_at(10, 0))
    assert report["enabled"] is True
    assert report["outbox_present"] is False
    assert report["source_errors"] == []
    assert world.notifications.posted == []

    report = drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert report["outbox_present"] is False
    assert world.notifications.posted == []

    # Once IntelX creates the outbox and fires, delivery just works.
    world.append(_envelope())
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["outbox_present"] is True
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 1


def test_partial_line_not_consumed_until_terminated(world):
    drainer = world.drainer()
    _baseline(world, drainer)
    env = _envelope()
    # Writer caught mid-append: full JSON, no trailing newline yet.
    world.write_raw(json.dumps(env))

    report = drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert report["posted"] == 0
    assert world.notifications.posted == []

    with world.outbox.open("a", encoding="utf-8") as fh:
        fh.write("\n")
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["posted"] == 1
    assert len(world.notifications.posted) == 1


# ---------------------------------------------------------------------------
# kill switch + failure handling
# ---------------------------------------------------------------------------


def test_kill_switch_off_means_no_posts_and_no_state(world):
    world.append(_envelope())
    drainer = iw.IntelxWatchDrainer(
        outbox_path=world.outbox,
        state_path=world.state_path,
        enabled_fn=lambda: False,
    )
    report = drainer.run_cycle(world.notifications, now=_at(10, 0))
    assert report["enabled"] is False
    assert world.notifications.posted == []
    assert not world.state_path.exists()


def test_failed_post_is_held_and_retried_via_digest(world):
    class _FlakyNotifications(_FakeNotifications):
        def __init__(self):
            super().__init__()
            self.fail_next = 0

        def post_notification(self, *a, **kw):
            if self.fail_next:
                self.fail_next -= 1
                raise RuntimeError("queue unavailable")
            return super().post_notification(*a, **kw)

    world.notifications = _FlakyNotifications()
    drainer = world.drainer()
    _baseline(world, drainer)
    world.append(_envelope())

    world.notifications.fail_next = 1
    report = drainer.run_cycle(world.notifications, now=_at(10, 5))
    assert report["post_failures"] == 1
    assert report["posted"] == 0
    assert world.notifications.posted == []

    # Next cycle: the held alert is retried and lands (as the digest).
    report = drainer.run_cycle(world.notifications, now=_at(10, 10))
    assert report["flushed"] == 1
    assert len(world.notifications.posted) == 1
    assert "Introducing Images 2.6" in world.notifications.posted[0]["message"]


# ---------------------------------------------------------------------------
# TASK-INT-060: remote (HTTP) outbox source
# ---------------------------------------------------------------------------


class _RemoteWorld:
    """Drainer wired to a fake remote outbox endpoint (TASK-INT-060)."""

    def __init__(self, tmp_path: Path):
        self.state_path = tmp_path / "drainer_state.json"
        self.notifications = _FakeNotifications()
        self.payload: dict = {"lane": "main", "size": 0, "envelopes": [], "malformed": 0}
        self.fail = False

    def fetch(self, url: str):
        if self.fail:
            raise OSError("connection refused")
        return self.payload

    def drainer(self) -> iw.IntelxWatchDrainer:
        return iw.IntelxWatchDrainer(
            state_path=self.state_path,
            enabled_fn=lambda: True,
            outbox_url="https://intelx.example/v1/watches/outbox",
            fetch_fn=self.fetch,
        )


@pytest.fixture()
def remote_world(tmp_path) -> _RemoteWorld:
    return _RemoteWorld(tmp_path)


def test_remote_baseline_records_existing_envelopes_as_seen(remote_world):
    remote_world.payload["envelopes"] = [_envelope()]
    drainer = remote_world.drainer()

    report = drainer.run_cycle(remote_world.notifications, now=_at(10, 0))

    assert report["baseline"] is True
    assert report["outbox_present"] is True
    assert report["posted"] == 0
    assert remote_world.notifications.posted == []


def test_remote_new_envelope_delivered_once_across_refetches(remote_world):
    drainer = remote_world.drainer()
    drainer.run_cycle(remote_world.notifications, now=_at(10, 0))  # baseline, empty

    env = _envelope()
    remote_world.payload["envelopes"] = [env]
    report = drainer.run_cycle(remote_world.notifications, now=_at(10, 5))
    assert report["posted"] == 1
    assert remote_world.notifications.posted[0]["metadata"]["dedupe_key"] == env["dedupe_key"]

    # The endpoint returns the full list every poll; dedupe keys guard it.
    report = drainer.run_cycle(remote_world.notifications, now=_at(10, 10))
    assert report["posted"] == 0
    assert report["duplicates"] == 1
    assert len(remote_world.notifications.posted) == 1


def test_remote_fetch_failure_is_a_source_error_not_a_crash(remote_world):
    drainer = remote_world.drainer()
    drainer.run_cycle(remote_world.notifications, now=_at(10, 0))

    remote_world.fail = True
    report = drainer.run_cycle(remote_world.notifications, now=_at(10, 5))

    assert report["posted"] == 0
    assert any("remote outbox fetch failed" in e for e in report["source_errors"])


def test_remote_malformed_rows_are_counted_and_skipped(remote_world):
    drainer = remote_world.drainer()
    drainer.run_cycle(remote_world.notifications, now=_at(10, 0))

    bad = _envelope("aaaaaaaaaaaaaaaa", schema="other/9")
    remote_world.payload["envelopes"] = [bad, _envelope()]
    report = drainer.run_cycle(remote_world.notifications, now=_at(10, 5))

    assert report["malformed"] == 1
    assert report["posted"] == 1
