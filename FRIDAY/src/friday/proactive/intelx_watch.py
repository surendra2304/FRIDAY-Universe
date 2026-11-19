"""TASK-PRO-002: IntelX standing-watch outbox drainer — PRO-001's last mile.

IntelX's standing watches (TASK-INT-007) do not notify the owner
directly. Each fired alert is appended as one JSON envelope per line to
IntelX's outbox (``data/watches/outbox.jsonl`` under the IntelX
checkout, overridable with ``INTELX_WATCH_OUTBOX_PATH`` — the delivery
contract in ``IntelX/docs/STANDING_WATCHES.md`` §4). This drainer is
the consumer PRO-001's family was always meant to have on that file: a
background cycle (wired into ``api/server.py``'s lifespan beside
``_stratex_watch_loop``) tails the outbox and posts each envelope
through the REAL notification path —
``observability.notifications.NotificationManager``.

Contract points enforced here (STANDING_WATCHES.md §4 + the PRO-001
anti-spam rules):

- every envelope carries a stable ``dedupe_key``
  (``intelx.watch:<watch_id>:<fp16>``); a key is delivered at most
  once, ever — delivered keys are persisted in the drainer state, so
  restarts, offset resets and a swapped/rebuilt outbox can never
  re-deliver an alert;
- ``quiet_hours_exempt`` is the policy input — IntelX sets it, this
  drainer enforces it: digest-class envelopes carry it false, so quiet
  hours 23:00-07:00 IST (the shared PRO-001 policy) hold them like any
  other non-breaker alert and held alerts flush as ONE digest
  notification at/after 07:00; since TASK-INT-015, instant-class
  envelopes (big breaks) carry it true and post immediately;
- the first cycle on a fresh drainer state is a silent BASELINE —
  envelopes already sitting in the outbox are recorded as seen, never
  announced (enabling the drainer late never floods the owner with
  backlog);
- the outbox is append-only: the drainer consumes only complete
  (newline-terminated) lines, so a writer caught mid-append loses
  nothing — the partial tail is read once it is terminated;
- a malformed line (bad JSON, non-object, wrong schema, missing
  dedupe key) is skipped and logged, never crashes the cycle and
  never wedges the tail — the offset advances past it;
- a missing outbox is a normal state (watches not enabled yet), not
  an error: the cycle reports it and moves on;
- kill switch: ``FRIDAY_PROACTIVE_INTELX_WATCH`` env flag. The code
  default is OFF (fail-safe), exactly like PRO-001's Stratex watch;
  production enables it only as a separate, deliberate step.

TASK-INT-016 adds the fast lane TASK-INT-015 named as its downstream
follow-up (STANDING_WATCHES.md §7): instant-class envelopes are ALSO
appended by IntelX to a sibling ``instant_outbox.jsonl``
(``INTELX_WATCH_INSTANT_OUTBOX_PATH`` override). ``run_instant_cycle``
tails that file on the server's short instant cadence and delivers
through the same state — the SAME persisted ``delivered_keys`` — so an
instant envelope is delivered exactly once across both lanes: whichever
lane reaches it first posts it, the other lane counts it as a
duplicate. The instant lane has its own silent baseline and offset in
the same state file, honours the envelope's ``quiet_hours_exempt``
flag exactly like the main lane, and never enables any watch or flag:
it is inert under the same kill switch.

Truthfulness: every figure in every message comes from the envelope
itself (title, summary, publisher, url, score as IntelX recorded
them); the drainer composes wording only. This module never writes to
IntelX state and never enables the watches — it only drains.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from friday.core.owner_time import OWNER_TZ, now_owner_tz
from friday.proactive.stratex_watch import in_quiet_hours

logger = logging.getLogger(__name__)

#: The only envelope schema this drainer consumes (STANDING_WATCHES.md §4).
ENVELOPE_SCHEMA = "intelx.watch_alert/1"

#: Bounds so drainer state can never grow without limit.
MAX_DELIVERED_KEYS = 1000
MAX_ALERT_LOG = 200
MAX_HELD = 50

SOURCE_TAG = "TASK-PRO-002"
INSTANT_SOURCE_TAG = "TASK-INT-016"

#: Severities a notification may carry. "high" is the fleet vocabulary
#: TASK-INT-015 stamps on instant-class envelopes (from
#: intelx/api/v1/signal_detection.py); before TASK-INT-016 the drainer
#: silently clamped it to "info", downgrading every big break.
VALID_SEVERITIES = {"info", "warning", "critical", "high"}


def drain_enabled() -> bool:
    """Kill switch: FRIDAY_PROACTIVE_INTELX_WATCH in {1,true,yes,on}."""
    return os.getenv("FRIDAY_PROACTIVE_INTELX_WATCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# ---------------------------------------------------------------------------
# outbox resolution (read-only)
# ---------------------------------------------------------------------------


def resolve_outbox_path() -> Path:
    """Locate IntelX's watch outbox.

    ``INTELX_WATCH_OUTBOX_PATH`` (IntelX's own env name) wins; otherwise
    the sibling ``IntelX/`` checkout's default ``data/watches/outbox.jsonl``
    — the same sibling rule PRO-001 uses for Stratex.
    """
    override = (os.getenv("INTELX_WATCH_OUTBOX_PATH") or "").strip()
    if override:
        return Path(override)
    # this file: FRIDAY/src/friday/proactive/intelx_watch.py
    # parents[4] is the repo root; IntelX/ is FRIDAY's sibling there.
    return (
        Path(__file__).resolve().parents[4]
        / "IntelX"
        / "data"
        / "watches"
        / "outbox.jsonl"
    )


def resolve_instant_outbox_path(main_outbox_path: Path | None = None) -> Path:
    """Locate IntelX's instant outbox (TASK-INT-015's fast-lane file).

    ``INTELX_WATCH_INSTANT_OUTBOX_PATH`` (IntelX's own env name) wins;
    otherwise the sibling of the main outbox — the exact rule IntelX's
    ``default_instant_outbox_path`` uses on the producer side.
    """
    override = (os.getenv("INTELX_WATCH_INSTANT_OUTBOX_PATH") or "").strip()
    if override:
        return Path(override)
    main = main_outbox_path if main_outbox_path is not None else resolve_outbox_path()
    return main.parent / "instant_outbox.jsonl"


# ---------------------------------------------------------------------------
# the drainer
# ---------------------------------------------------------------------------


def _default_state_path() -> Path:
    override = (os.getenv("FRIDAY_PROACTIVE_INTELX_WATCH_STATE_FILE") or "").strip()
    if override:
        return Path(override)
    # FRIDAY/state/ beside src/ (parents[3] is the FRIDAY directory).
    return Path(__file__).resolve().parents[3] / "state" / "proactive_intelx_watch.json"


def _empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "baseline_done": False,
        "offset": 0,
        # TASK-INT-016 fast lane: the instant outbox has its own offset
        # and baseline in the SAME state file, so both lanes share the
        # delivered_keys / held queue below (cross-lane dedupe).
        "instant_baseline_done": False,
        "instant_offset": 0,
        "delivered_keys": [],
        "held": [],
        "alert_log": [],
        "malformed_total": 0,
    }


def _envelope_message(envelope: dict[str, Any]) -> str:
    """Owner-facing wording for one envelope — envelope fields only."""
    watch_id = str(envelope.get("watch_id") or "unknown watch")
    title = str(envelope.get("title") or "(untitled alert)")
    lines = [f"IntelX standing watch [{watch_id}]: {title}"]
    summary = str(envelope.get("summary") or "").strip()
    if summary:
        lines.append(summary)
    tail_bits = []
    publisher = str(envelope.get("publisher") or "").strip()
    if publisher:
        tail_bits.append(publisher)
    score = envelope.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        tail_bits.append(f"significance score {score:g}")
    url = str(envelope.get("url") or "").strip()
    if url:
        tail_bits.append(url)
    if tail_bits:
        lines.append(" · ".join(tail_bits))
    return "\n".join(lines)


class IntelxWatchDrainer:
    """Tails IntelX's watch outbox and posts envelopes as notifications.

    One instance per process; ``run_cycle`` is lock-guarded and never
    raises. ``notifications`` is anything with the NotificationManager
    ``post_notification(message, category=..., severity=...,
    metadata=...)`` shape — production passes the agent's durable
    manager.
    """

    def __init__(
        self,
        *,
        outbox_path: Path | None = None,
        instant_outbox_path: Path | None = None,
        state_path: Path | None = None,
        enabled_fn: Callable[[], bool] = drain_enabled,
    ) -> None:
        self._outbox_path = outbox_path if outbox_path is not None else resolve_outbox_path()
        self._instant_outbox_path = (
            instant_outbox_path
            if instant_outbox_path is not None
            else resolve_instant_outbox_path(self._outbox_path)
        )
        self._state_path = state_path if state_path is not None else _default_state_path()
        self._enabled_fn = enabled_fn
        self._lock = threading.Lock()
        self._state: dict[str, Any] | None = None

    # -- state ------------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if self._state is not None:
            return self._state
        state = _empty_state()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                state.update({k: raw[k] for k in state if k in raw})
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning(f"intelx watch drain: drainer state unreadable ({exc}); starting fresh")
        self._state = state
        return state

    def _persist_state(self) -> None:
        if self._state is None:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._state, default=str, indent=1), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except OSError as exc:
            logger.warning(f"intelx watch drain: could not persist drainer state: {exc}")

    # -- outbox reading -----------------------------------------------------

    def _read_new_envelopes(
        self,
        state: dict[str, Any],
        report: dict[str, Any],
        *,
        path: Path | None = None,
        offset_key: str = "offset",
        present_key: str = "outbox_present",
    ) -> list[dict[str, Any]]:
        """Envelopes from complete lines past the persisted offset.

        Advances ``state[offset_key]`` past every complete line consumed
        (valid, duplicate and malformed alike — a poison line must
        never wedge the tail). A trailing partial line is left for the
        next cycle. A file that shrank below the offset was replaced:
        restart from 0 and let the persisted dedupe keys do their job.
        Defaults read the main outbox; the TASK-INT-016 fast lane passes
        the instant outbox with its own offset/presence keys.
        """
        path = path if path is not None else self._outbox_path
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            report[present_key] = False
            return []
        except OSError as exc:
            report["source_errors"].append(f"outbox unreadable: {exc}")
            return []
        report[present_key] = True

        offset = int(state.get(offset_key) or 0)
        if size < offset:
            logger.info(
                f"intelx watch drain: outbox shrank ({offset} -> {size} bytes); "
                "restarting tail at 0 (dedupe keys still guard delivery)"
            )
            offset = 0
        if size == offset:
            state[offset_key] = offset
            return []
        try:
            with path.open("rb") as fh:
                fh.seek(offset)
                chunk = fh.read()
        except OSError as exc:
            report["source_errors"].append(f"outbox read failed: {exc}")
            return []

        last_nl = chunk.rfind(b"\n")
        if last_nl < 0:
            # No complete line yet — the writer is mid-append.
            state[offset_key] = offset
            return []
        complete = chunk[: last_nl + 1]
        state[offset_key] = offset + len(complete)

        envelopes: list[dict[str, Any]] = []
        for raw_line in complete.split(b"\n"):
            line = raw_line.strip()
            if not line:
                continue
            report["lines_read"] += 1
            try:
                row = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                report["malformed"] += 1
                state["malformed_total"] = int(state.get("malformed_total") or 0) + 1
                logger.warning(f"intelx watch drain: skipping malformed outbox line: {line[:120]!r}")
                continue
            if not isinstance(row, dict) or row.get("schema") != ENVELOPE_SCHEMA:
                report["malformed"] += 1
                state["malformed_total"] = int(state.get("malformed_total") or 0) + 1
                logger.warning(f"intelx watch drain: skipping non-envelope outbox line: {line[:120]!r}")
                continue
            if not str(row.get("dedupe_key") or "").strip():
                report["malformed"] += 1
                state["malformed_total"] = int(state.get("malformed_total") or 0) + 1
                logger.warning(f"intelx watch drain: skipping envelope without dedupe_key: {line[:120]!r}")
                continue
            envelopes.append(row)
        return envelopes

    # -- delivery -----------------------------------------------------------

    def _post(
        self,
        notifications: Any,
        state: dict[str, Any],
        *,
        message: str,
        severity: str,
        trigger: str,
        dedupe_key: str,
        extra: dict[str, Any] | None = None,
        source: str = SOURCE_TAG,
        now: datetime,
    ) -> bool:
        metadata = {
            "source": source,
            "trigger": trigger,
            "dedupe_key": dedupe_key,
        }
        if extra:
            metadata.update(extra)
        try:
            notifications.post_notification(
                message,
                category="intelx_watch",
                severity=severity,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(f"intelx watch drain: notification post failed ({trigger}): {exc}")
            return False
        state["alert_log"].append(
            {
                "ts": now.astimezone(OWNER_TZ).isoformat(),
                "trigger": trigger,
                "dedupe_key": dedupe_key,
                "severity": severity,
                "message": message,
                "delivery": "posted",
            }
        )
        state["alert_log"] = state["alert_log"][-MAX_ALERT_LOG:]
        logger.info(f"intelx watch drain [{trigger}] {message.splitlines()[0]}")
        return True

    def _mark_delivered(self, state: dict[str, Any], dedupe_key: str) -> None:
        delivered = state["delivered_keys"]
        if dedupe_key not in delivered:
            delivered.append(dedupe_key)
        state["delivered_keys"] = delivered[-MAX_DELIVERED_KEYS:]

    def _hold(
        self,
        state: dict[str, Any],
        event: dict[str, Any],
        *,
        now: datetime,
        reason: str,
        report: dict[str, Any],
    ) -> None:
        state["held"].append({**event, "queued_at": now.astimezone(OWNER_TZ).isoformat()})
        state["held"] = state["held"][-MAX_HELD:]
        state["alert_log"].append(
            {
                "ts": now.astimezone(OWNER_TZ).isoformat(),
                "trigger": event["trigger"],
                "dedupe_key": event["dedupe_key"],
                "severity": event["severity"],
                "message": event["message"],
                "delivery": reason,
            }
        )
        state["alert_log"] = state["alert_log"][-MAX_ALERT_LOG:]
        report["held"] += 1

    def _flush_held(
        self, notifications: Any, state: dict[str, Any], *, now: datetime, report: dict[str, Any]
    ) -> None:
        if not state["held"] or in_quiet_hours(now):
            return
        held = state["held"]
        lines = [h["message"] for h in held[:6]]
        digest = "IntelX watch alerts held for you:\n" + "\n".join(
            f"- {line}" for line in lines
        )
        if len(held) > len(lines):
            digest += f"\n(+ {len(held) - len(lines)} more alerts)"
        first_key = held[0]["dedupe_key"]
        last_key = held[-1]["dedupe_key"]
        event = {
            "message": digest,
            "severity": "info",
            "trigger": "quiet_hours_digest",
            "dedupe_key": f"intelx-digest:{first_key}..{last_key}",
        }
        if self._post(notifications, state, now=now, **event):
            for h in held:
                self._mark_delivered(state, h["dedupe_key"])
            report["flushed"] = len(held)
            report["posted"] += 1  # the digest itself is one posted notification
            state["held"] = []

    # -- the cycle ------------------------------------------------------------

    def _deliver_envelopes(
        self,
        notifications: Any,
        state: dict[str, Any],
        envelopes: list[dict[str, Any]],
        *,
        now: datetime,
        report: dict[str, Any],
        trigger: str,
        source: str,
        lane: str,
    ) -> None:
        """Deliver fresh envelopes under the shared dedupe/quiet policy.

        Shared by the main lane and the TASK-INT-016 instant lane: the
        persisted delivered_keys + held queue are the single cross-lane
        dedupe record, so an envelope present in both outboxes is
        posted exactly once, by whichever lane reaches it first.
        """
        delivered = set(state["delivered_keys"])
        held_keys = {h["dedupe_key"] for h in state["held"]}
        for envelope in envelopes:
            dedupe_key = str(envelope["dedupe_key"])
            if dedupe_key in delivered or dedupe_key in held_keys:
                report["duplicates"] += 1
                continue
            severity = str(envelope.get("severity") or "info")
            if severity not in VALID_SEVERITIES:
                severity = "info"
            post = {
                "message": _envelope_message(envelope),
                "severity": severity,
                "trigger": trigger,
                "dedupe_key": dedupe_key,
                "source": source,
                "extra": {
                    "watch_id": str(envelope.get("watch_id") or ""),
                    "envelope_id": str(envelope.get("envelope_id") or ""),
                    "publisher": str(envelope.get("publisher") or ""),
                    "url": str(envelope.get("url") or ""),
                    "alert_class": str(envelope.get("alert_class") or ""),
                    "lane": lane,
                },
            }
            # _hold stores the flattened event shape the digest
            # reads (message/severity/trigger/dedupe_key).
            flat = {
                "message": post["message"],
                "severity": severity,
                "trigger": trigger,
                "dedupe_key": dedupe_key,
            }
            if bool(envelope.get("quiet_hours_exempt")) or not in_quiet_hours(now):
                if self._post(notifications, state, now=now, **post):
                    self._mark_delivered(state, dedupe_key)
                    delivered.add(dedupe_key)
                    report["posted"] += 1
                else:
                    report["post_failures"] += 1
                    self._hold(state, flat, now=now, reason="held_post_failed", report=report)
                    held_keys.add(dedupe_key)
            else:
                self._hold(state, flat, now=now, reason="held_quiet_hours", report=report)
                held_keys.add(dedupe_key)
            # Persist after every consumed envelope: alerts are
            # rare (a few per day), and this keeps the
            # delivered-key record as close to the post as
            # possible across a crash/restart.
            self._persist_state()

    def run_cycle(self, notifications: Any, *, now: datetime | None = None) -> dict[str, Any]:
        """One drain cycle. Never raises; returns a report dict."""
        report: dict[str, Any] = {
            "enabled": False,
            "baseline": False,
            "outbox_present": False,
            "lines_read": 0,
            "envelopes": 0,
            "posted": 0,
            "held": 0,
            "flushed": 0,
            "duplicates": 0,
            "malformed": 0,
            "post_failures": 0,
            "source_errors": [],
        }
        if notifications is None:
            report["source_errors"].append("no notification manager")
            return report
        with self._lock:
            try:
                if not self._enabled_fn():
                    return report
                report["enabled"] = True
                moment = now or now_owner_tz()
                state = self._load_state()

                envelopes = self._read_new_envelopes(state, report)
                report["envelopes"] = len(envelopes)

                if not state["baseline_done"]:
                    # Silent baseline: record the world as seen; announce
                    # nothing. The offset has already advanced past every
                    # line read, and the keys guard a rebuilt outbox too.
                    for envelope in envelopes:
                        self._mark_delivered(state, str(envelope["dedupe_key"]))
                    state["baseline_done"] = True
                    report["baseline"] = True
                    if envelopes:
                        logger.info(
                            f"intelx watch drain: baseline established "
                            f"({len(envelopes)} pre-existing envelopes recorded as seen)"
                        )
                    self._persist_state()
                    return report

                self._flush_held(notifications, state, now=moment, report=report)

                self._deliver_envelopes(
                    notifications,
                    state,
                    envelopes,
                    now=moment,
                    report=report,
                    trigger="intelx_watch_alert",
                    source=SOURCE_TAG,
                    lane="main",
                )

                self._persist_state()
            except Exception as exc:  # a drain failure must never take FRIDAY down
                logger.exception(f"intelx watch drain cycle failed: {exc}")
                report["source_errors"].append(f"cycle error: {type(exc).__name__}")
            return report

    def run_instant_cycle(
        self, notifications: Any, *, now: datetime | None = None
    ) -> dict[str, Any]:
        """One TASK-INT-016 fast-lane cycle over the instant outbox.

        Same contract as ``run_cycle`` — kill switch, silent first
        baseline (the instant lane's own), the envelope's
        ``quiet_hours_exempt`` flag as the policy input, malformed /
        partial-line tolerance, never raises — but delivery goes
        through the shared ``_deliver_envelopes``, so the persisted
        delivered_keys dedupe across lanes. Held envelopes (quiet-hours
        or failed posts) join the shared held queue and flush through
        the main lane's digest exactly as before.
        """
        report: dict[str, Any] = {
            "enabled": False,
            "lane": "instant",
            "baseline": False,
            "outbox_present": False,
            "instant_outbox_present": False,
            "lines_read": 0,
            "envelopes": 0,
            "posted": 0,
            "held": 0,
            "flushed": 0,
            "duplicates": 0,
            "malformed": 0,
            "post_failures": 0,
            "source_errors": [],
        }
        if notifications is None:
            report["source_errors"].append("no notification manager")
            return report
        with self._lock:
            try:
                if not self._enabled_fn():
                    return report
                report["enabled"] = True
                moment = now or now_owner_tz()
                state = self._load_state()

                envelopes = self._read_new_envelopes(
                    state,
                    report,
                    path=self._instant_outbox_path,
                    offset_key="instant_offset",
                    present_key="instant_outbox_present",
                )
                report["envelopes"] = len(envelopes)

                if not state.get("instant_baseline_done"):
                    # Silent instant baseline, mirroring the main lane:
                    # a pre-existing instant backlog is recorded as
                    # seen, never announced.
                    for envelope in envelopes:
                        self._mark_delivered(state, str(envelope["dedupe_key"]))
                    state["instant_baseline_done"] = True
                    report["baseline"] = True
                    if envelopes:
                        logger.info(
                            f"intelx watch drain: instant baseline established "
                            f"({len(envelopes)} pre-existing envelopes recorded as seen)"
                        )
                    self._persist_state()
                    return report

                self._deliver_envelopes(
                    notifications,
                    state,
                    envelopes,
                    now=moment,
                    report=report,
                    trigger="intelx_watch_instant_alert",
                    source=INSTANT_SOURCE_TAG,
                    lane="instant",
                )

                self._persist_state()
            except Exception as exc:  # a drain failure must never take FRIDAY down
                logger.exception(f"intelx watch instant drain cycle failed: {exc}")
                report["source_errors"].append(f"cycle error: {type(exc).__name__}")
            return report


# ---------------------------------------------------------------------------
# server entry point (process-global drainer)
# ---------------------------------------------------------------------------

_GLOBAL_DRAINER: IntelxWatchDrainer | None = None
_GLOBAL_LOCK = threading.Lock()


def _global_drainer() -> IntelxWatchDrainer:
    global _GLOBAL_DRAINER
    with _GLOBAL_LOCK:
        if _GLOBAL_DRAINER is None:
            _GLOBAL_DRAINER = IntelxWatchDrainer()
        return _GLOBAL_DRAINER


def run_drain_cycle(notifications: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Run one cycle on the process-global drainer (server loop entry)."""
    return _global_drainer().run_cycle(notifications, now=now)


def run_instant_drain_cycle(
    notifications: Any, *, now: datetime | None = None
) -> dict[str, Any]:
    """Run one TASK-INT-016 fast-lane cycle on the SAME global drainer.

    Sharing the instance (and its lock + state) with the main lane is
    what makes cross-lane dedupe a property of the delivery record,
    not a hope.
    """
    return _global_drainer().run_instant_cycle(notifications, now=now)
