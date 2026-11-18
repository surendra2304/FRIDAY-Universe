"""TASK-FRD-024 — the autonomous daemon's self-generated task source.

TASK-FRD-023 armed the daemon at boot, but its only task source was
manual submission (``POST /api/autonomous/goals``): an armed daemon
with an empty queue idles forever, which is how it sat unnoticed from
2026-11-10 until the 2026-11-17 diagnosis. This module gives the
daemon its own work — a CLOSED catalogue of triggers over state FRIDAY
can verify herself:

* ``fleet_agent_unhealthy`` — a fleet agent's own health probe
  (``fleet_client.get_all_statuses``) reports DEGRADED, UNREACHABLE
  or OFFLINE;
* ``fleet_poll_failing`` — the fleet status poll itself raises;
* ``stratex_heartbeat_stale`` — Stratex's daemon heartbeat file (the
  freshness pulse the FRD-021 snapshot path gates on) is missing or
  older than the staleness bound;
* ``daemon_goals_failing`` — two or more non-source goals completed
  FAILED inside the lookback window.

Every seeded goal is a READ-ONLY verification or review task, phrased
as one in its text, and is submitted through the daemon's existing
``submit_goal`` path — no authorization bypass, no second executor.
The catalogue is closed on purpose: nothing outside these four
triggers can seed work, and no seeded goal asks any agent to send an
external message, move money, delete anything, or change a
configuration.

Bounds (all enforced here, in one place):

* seeding happens ONLY into a fully idle daemon (empty queue, nothing
  running) — self-generated work never displaces or delays the
  owner's submitted goals, and seeded goals carry priority -1 so a
  later owner submission still sorts ahead of them;
* per-trigger cooldowns (fleet 6 h, poll 6 h, Stratex 6 h, goal
  failures 12 h) plus a reported-failure dedupe set, so a persistent
  anomaly re-seeds at most on its cooldown, never every cycle;
* at most 2 seeds per evaluation and a global daily cap (default 6 —
  each seeded goal costs planner + Inference synthesis quota on the
  free tier and a daemon slot; 6/day surfaces persistent anomalies
  without crowding the quota; override with
  ``FRIDAY_AUTONOMOUS_TASK_SOURCE_DAILY_CAP``);
* the owner's standing flag is re-checked on EVERY evaluation:
  ``settings.autonomous_mode`` off means no seeding, immediately —
  including when the daemon was armed by the runtime toggle, which
  does not consult that flag. ``FRIDAY_AUTONOMOUS_TASK_SOURCE=off``
  is a dedicated kill switch for the source alone.

Trigger evidence is logged (INFO) and stored on the goal's metadata
for every seed. Source state (cooldowns, daily counts, reported
failure ids) persists beside the daemon's own state file so restarts
do not reset the bounds.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from friday.core.config import get_settings
from friday.core.logging import get_logger

logger = get_logger("autonomous.task_source")

#: Metadata tag marking every goal this source seeds. The failure
#: trigger excludes tagged goals, so the source can never investigate
#: its own failures in a loop.
SOURCE_TAG = "autonomous_task_source"

#: Fleet statuses that count as an anomaly worth verifying. ONLINE
#: and REACHABLE are healthy answers from the probe, not anomalies.
UNHEALTHY_STATUSES = {"DEGRADED", "UNREACHABLE", "OFFLINE"}

FLEET_AGENT_COOLDOWN_S = 6 * 3600.0
FLEET_POLL_COOLDOWN_S = 6 * 3600.0
STRATEX_COOLDOWN_S = 6 * 3600.0
FAILURE_COOLDOWN_S = 12 * 3600.0

#: The FRD-021 serving gate is 60 s (one missed scan); as an anomaly
#: trigger that would fire on noise, so the source requires ten
#: minutes of silence — roughly ten missed scan cycles — before it
#: calls the heartbeat stale.
STRATEX_HEARTBEAT_STALE_S = 600.0

FAILURE_LOOKBACK_S = 6 * 3600.0
FAILURE_THRESHOLD = 2

MAX_SEEDS_PER_EVALUATION = 2
DEFAULT_DAILY_CAP = 6

_STATE_RETENTION_S = 7 * 24 * 3600.0
_MAX_REPORTED_FAILURES = 200


@dataclass
class TriggerSeed:
    """One catalogue trigger that fired, ready to submit."""

    trigger: str
    key: str
    goal_text: str
    evidence: dict[str, Any]
    mark_failure_ids: list[str] = field(default_factory=list)


class DaemonTaskSource:
    """Evaluates the closed trigger catalogue and seeds the daemon.

    Readers are injectable for tests; the defaults read the fleet
    client's live probe and the Stratex watch's own path resolution.
    """

    def __init__(
        self,
        *,
        state_path: Path | None = None,
        fleet_statuses: Callable[[], Awaitable[list[Any]]] | None = None,
        stratex_heartbeat_age_s: Callable[[], float | None] | None = None,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._state_path = state_path or (
            Path(__file__).resolve().parents[3] / ".data" / "autonomous_task_source.json"
        )
        self._fleet_statuses = fleet_statuses or self._default_fleet_statuses
        self._stratex_heartbeat_age_s = (
            stratex_heartbeat_age_s or self._default_stratex_heartbeat_age_s
        )
        self._now = now_fn
        self._last_seeded: dict[str, float] = {}
        self._daily: dict[str, int] = {}
        self._reported_failure_ids: list[str] = []
        self._load_state()

    # -- default readers -------------------------------------------------

    @staticmethod
    async def _default_fleet_statuses() -> list[Any]:
        from friday.ecosystem.fleet_client import fleet_client

        return await fleet_client.get_all_statuses()

    @staticmethod
    def _default_stratex_heartbeat_age_s() -> float | None:
        """Age of Stratex's daemon heartbeat, or None when no Stratex
        checkout resolves (a deployment shape, not an anomaly this
        source can verify). A resolved checkout whose heartbeat file
        is missing is infinitely stale."""
        from friday.proactive.stratex_watch import resolve_stratex_paths

        paths = resolve_stratex_paths()
        if paths is None:
            return None
        try:
            mtime = paths.heartbeat.stat().st_mtime
        except OSError:
            return float("inf")
        return max(0.0, time.time() - mtime)

    # -- gates and bounds --------------------------------------------------

    def _seeding_allowed(self) -> bool:
        """The owner's standing flag, re-read on every evaluation, plus
        the source's own kill switch."""
        if os.getenv("FRIDAY_AUTONOMOUS_TASK_SOURCE", "").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return False
        return bool(get_settings().autonomous_mode)

    def _daily_cap(self) -> int:
        try:
            return max(
                0,
                int(
                    os.getenv(
                        "FRIDAY_AUTONOMOUS_TASK_SOURCE_DAILY_CAP",
                        str(DEFAULT_DAILY_CAP),
                    )
                ),
            )
        except ValueError:
            return DEFAULT_DAILY_CAP

    def _today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _cooling_down(self, key: str, cooldown_s: float, now: float) -> bool:
        last = self._last_seeded.get(key)
        return last is not None and now - last < cooldown_s

    # -- state persistence -------------------------------------------------

    def _load_state(self) -> None:
        try:
            if not self._state_path.is_file():
                return
            with self._state_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            logger.warning(
                "Could not load autonomous task source state from %s: %s",
                self._state_path,
                exc,
            )
            return
        if isinstance(data.get("last_seeded"), dict):
            self._last_seeded = {
                str(k): float(v)
                for k, v in data["last_seeded"].items()
                if isinstance(v, (int, float))
            }
        if isinstance(data.get("daily"), dict):
            self._daily = {
                str(k): int(v) for k, v in data["daily"].items() if isinstance(v, int)
            }
        if isinstance(data.get("reported_failure_ids"), list):
            self._reported_failure_ids = [
                str(x) for x in data["reported_failure_ids"]
            ][-_MAX_REPORTED_FAILURES:]

    def _persist_state(self) -> None:
        try:
            now = self._now()
            self._last_seeded = {
                k: v
                for k, v in self._last_seeded.items()
                if now - v < _STATE_RETENTION_S
            }
            today = self._today_key()
            self._daily = {k: v for k, v in self._daily.items() if k >= today}
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "last_seeded": self._last_seeded,
                "daily": self._daily,
                "reported_failure_ids": self._reported_failure_ids[
                    -_MAX_REPORTED_FAILURES:
                ],
            }
            tmp = self._state_path.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, default=str)
            os.replace(tmp, self._state_path)
        except Exception as exc:
            logger.warning("Could not persist autonomous task source state: %s", exc)

    # -- trigger catalogue ---------------------------------------------------

    async def _check_fleet(self, now: float) -> list[TriggerSeed]:
        try:
            statuses = await self._fleet_statuses()
        except Exception as exc:
            key = "fleet_poll_failing"
            if self._cooling_down(key, FLEET_POLL_COOLDOWN_S, now):
                return []
            return [
                TriggerSeed(
                    trigger="fleet_poll_failing",
                    key=key,
                    goal_text=(
                        "FRIDAY's fleet status poll is failing. Check the fleet "
                        "status path, identify what is failing, and report the "
                        "finding. Read-only verification only: do not change "
                        "any configuration, restart any service, or send any "
                        "message."
                    ),
                    evidence={"error": f"{type(exc).__name__}: {exc}"[:200]},
                )
            ]
        seeds: list[TriggerSeed] = []
        for status in statuses or []:
            state = str(getattr(status, "status", "") or "").upper()
            if state not in UNHEALTHY_STATUSES:
                continue
            agent_id = str(getattr(status, "id", "") or "unknown")
            key = f"fleet_agent_unhealthy:{agent_id}"
            if self._cooling_down(key, FLEET_AGENT_COOLDOWN_S, now):
                continue
            name = str(getattr(status, "name", "") or agent_id)
            seeds.append(
                TriggerSeed(
                    trigger="fleet_agent_unhealthy",
                    key=key,
                    goal_text=(
                        f"Verify the current health of {name} and report "
                        "exactly which of its checks are failing. Read-only "
                        "verification only: do not change any configuration, "
                        "restart any service, or send any message."
                    ),
                    evidence={
                        "agent": agent_id,
                        "status": state,
                        "details": str(getattr(status, "details", ""))[:200],
                        "last_checked": str(getattr(status, "last_checked", "")),
                    },
                )
            )
        return seeds

    def _check_stratex(self, now: float) -> list[TriggerSeed]:
        age = self._stratex_heartbeat_age_s()
        if age is None or age <= STRATEX_HEARTBEAT_STALE_S:
            return []
        key = "stratex_heartbeat_stale"
        if self._cooling_down(key, STRATEX_COOLDOWN_S, now):
            return []
        age_text = (
            "missing entirely"
            if age == float("inf")
            else f"{int(age)} seconds old"
        )
        return [
            TriggerSeed(
                trigger="stratex_heartbeat_stale",
                key=key,
                goal_text=(
                    f"Stratex's daemon heartbeat is stale ({age_text}). Fetch "
                    "Stratex's current trading status directly — account "
                    "balance and open positions — and report the figures. "
                    "Read-only: do not place, close, pause or modify any "
                    "trade, and do not change any configuration."
                ),
                evidence={
                    "heartbeat_age_s": None if age == float("inf") else int(age),
                    "threshold_s": int(STRATEX_HEARTBEAT_STALE_S),
                },
            )
        ]

    def _check_goal_failures(self, daemon: Any, now: float) -> list[TriggerSeed]:
        cutoff = now - FAILURE_LOOKBACK_S
        reported = set(self._reported_failure_ids)
        fresh = [
            goal
            for goal in getattr(daemon, "_completed_goals", [])
            if getattr(goal, "status", "") == "FAILED"
            and float(getattr(goal, "completed_at", 0.0) or 0.0) >= cutoff
            and (getattr(goal, "metadata", None) or {}).get("source") != SOURCE_TAG
            and getattr(goal, "id", "") not in reported
        ]
        if len(fresh) < FAILURE_THRESHOLD:
            return []
        key = "daemon_goals_failing"
        if self._cooling_down(key, FAILURE_COOLDOWN_S, now):
            return []
        titles = "; ".join(
            str(getattr(goal, "goal", ""))[:60] for goal in fresh[:4]
        )
        return [
            TriggerSeed(
                trigger="daemon_goals_failing",
                key=key,
                goal_text=(
                    "Several autonomous goals failed in the last six hours: "
                    f"{titles}. Review the recorded failure reason for each "
                    "and report what failed and why. Read-only review: do "
                    "not retry the goals, change any configuration, or send "
                    "any message."
                ),
                evidence={
                    "failed_goal_ids": [str(getattr(g, "id", "")) for g in fresh],
                    "count": len(fresh),
                },
                mark_failure_ids=[str(getattr(g, "id", "")) for g in fresh],
            )
        ]

    # -- evaluation ----------------------------------------------------------

    async def maybe_seed(self, daemon: Any) -> list[str]:
        """Evaluate the catalogue once against the daemon's live state.

        Returns the ids of the goals submitted (usually none). Never
        raises for reader failures — a broken trigger reports through
        its own seed or not at all; the caller additionally guards the
        loop.
        """
        if not self._seeding_allowed():
            return []
        # Owner's work first: seed only into a fully idle daemon.
        if getattr(daemon, "_goal_queue", None) or getattr(
            daemon, "_running_goals", None
        ):
            return []
        now = self._now()
        today = self._today_key()
        if self._daily.get(today, 0) >= self._daily_cap():
            return []

        seeds: list[TriggerSeed] = []
        seeds += await self._check_fleet(now)
        # The Stratex reader is file IO; keep it off the event loop.
        seeds += await asyncio.to_thread(self._check_stratex, now)
        seeds += self._check_goal_failures(daemon, now)

        submitted: list[str] = []
        for seed in seeds:
            if len(submitted) >= MAX_SEEDS_PER_EVALUATION:
                break
            if self._daily.get(today, 0) >= self._daily_cap():
                break
            logger.info(
                "Autonomous task source: seeding goal from trigger %s "
                "(key %s) — evidence: %s",
                seed.trigger,
                seed.key,
                json.dumps(seed.evidence, default=str)[:300],
            )
            goal = daemon.submit_goal(
                seed.goal_text,
                priority=-1,
                metadata={
                    "source": SOURCE_TAG,
                    "trigger": seed.trigger,
                    "trigger_key": seed.key,
                    "evidence": seed.evidence,
                },
            )
            self._last_seeded[seed.key] = now
            self._daily[today] = self._daily.get(today, 0) + 1
            if seed.mark_failure_ids:
                self._reported_failure_ids = (
                    self._reported_failure_ids + seed.mark_failure_ids
                )[-_MAX_REPORTED_FAILURES:]
            submitted.append(goal.id)
        if submitted:
            self._persist_state()
        return submitted
