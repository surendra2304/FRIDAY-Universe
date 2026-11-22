"""Self-healing primitives: health registry, circuit breakers, bounded self-repair.

What this adds to CORTEX:

* ``HealthRegistry`` — every subsystem reports observed outcomes. A subsystem that starts
  failing is *detected* (consecutive failures, or a rolling failure ratio over a minimum
  number of samples) rather than merely logged.
* ``SubsystemCircuit`` — a real breaker with CLOSED → OPEN → HALF_OPEN → CLOSED transitions,
  a single probe in HALF_OPEN, and an ``outage_for`` duration so callers can degrade
  gracefully instead of queueing behind a dead dependency.
* ``SelfHealingSupervisor`` — probes the registry and applies **bounded** repairs. A repair
  action is throttled (``repair_cooldown_seconds``), a subsystem that keeps failing after
  repairs escalates instead of looping, and no repair can silently become a "fix" that it
  cannot verify: repairs report ``repaired``, ``still_failing`` or ``escalated``.

Deliberate limits: repairs are local and idempotent (re-probe, reset breaker, drop cached
state, re-register a worker). Anything that cannot be proven from a post-repair probe is
escalated, never claimed as fixed.

Probes may report a tri-state ``ProbeResult`` instead of a plain bool (TASK-COR-014):
``HEALTHY`` / ``UNHEALTHY`` behave exactly like ``True`` / ``False``, while
``UNCONFIGURED`` means the subsystem was never configured in this deployment (for
example no base URL in the environment). An unconfigured subsystem is not down: the
registry records no circuit outcome for it and the supervisor treats it as a standing
configuration notice — logged once per unconfigured streak, never repaired, never
counted as a repair failure and never escalated. That distinction is the root-cause
fix for the 2026-11-17→19 escalation spam, where ``probe_ai_universe`` returned
``False`` for an unset URL and the supervisor escalated an absent provider every cycle.

The escalation ratio is a standing live check (TASK-CTX-004): the raw
fires/messages ratio is degenerate — zero deliveries is the correct output of a
healthy fleet *and* of a fleet whose probe observes nothing — so the check is
defined on the per-cycle run data instead. A per-subsystem unconfigured streak
(consecutive cycles in ``run.unconfigured``) alerts once per streak through the
existing escalation channel when it reaches ``unconfigured_streak_threshold``
cycles; a run of consecutive failed deliveries alerts once per broken-channel
streak; the check state is exposed in ``SelfHealingLoop.status()`` as
``ratio_check`` (streaks, per-subsystem signal rate, delivery gap, last alert).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import urllib.parse
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from enum import Enum
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("cortex-core.resilience")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ProbeResult(str, Enum):
    """Tri-state outcome of a health probe (TASK-COR-014).

    ``HEALTHY`` and ``UNHEALTHY`` are the classic bool outcomes. ``UNCONFIGURED``
    is distinct from ``UNHEALTHY``: the subsystem has no configuration to probe
    (e.g. its base-URL environment variables are unset), so there is nothing
    that could be repaired and nothing to escalate — only a configuration
    notice to record. Probes that return a plain bool keep working: ``True``
    is read as ``HEALTHY`` and ``False`` as ``UNHEALTHY``.
    """

    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNCONFIGURED = "UNCONFIGURED"

    @classmethod
    def coerce(cls, value: Any) -> "ProbeResult":
        """Normalise a probe return value (``ProbeResult`` or bool) to a result."""
        if isinstance(value, cls):
            return value
        return cls.HEALTHY if bool(value) else cls.UNHEALTHY

    @property
    def healthy(self) -> bool:
        return self is ProbeResult.HEALTHY


class SubsystemCircuit:
    """Circuit breaker for one subsystem (dependency, agent or tool)."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 15.0,
        window: int = 20,
        min_samples: int = 5,
        failure_ratio_threshold: float = 0.6,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.window = window
        self.min_samples = min_samples
        self.failure_ratio_threshold = failure_ratio_threshold

        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.opened_at: float | None = None
        self._outcomes: deque[bool] = deque(maxlen=window)
        self._lock = asyncio.Lock()
        self.total_successes = 0
        self.total_failures = 0
        self.transitions: list[dict[str, Any]] = []

    # ── state ───────────────────────────────────────────────────────────────
    def _record_transition(self, to: CircuitState, reason: str) -> None:
        self.transitions.append(
            {"from": self.state.value, "to": to.value, "reason": reason, "at": _utcnow().isoformat()}
        )
        self.transitions = self.transitions[-20:]
        logger.warning("circuit[%s] %s -> %s (%s)", self.name, self.transitions[-1]["from"], to.value, reason)
        self.state = to

    @property
    def failure_ratio(self) -> float | None:
        if len(self._outcomes) < self.min_samples:
            return None
        return sum(1 for ok in self._outcomes if not ok) / len(self._outcomes)

    def outage_for(self) -> float:
        """Seconds the subsystem has been unavailable (0 when it is not)."""
        if self.state != CircuitState.OPEN or self.opened_at is None:
            return 0.0
        return round(time.monotonic() - self.opened_at, 3)

    def is_available(self) -> bool:
        """True when a call may be attempted now (HALF_OPEN allows exactly one probe)."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            return self._can_half_open()
        return True  # HALF_OPEN: the probe itself decides

    def _can_half_open(self) -> bool:
        return self.opened_at is not None and (time.monotonic() - self.opened_at) >= self.recovery_timeout_seconds

    # ── outcomes ────────────────────────────────────────────────────────────
    async def before(self) -> bool:
        """Returns False when the breaker refuses the call (fail fast)."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._can_half_open():
                    self._record_transition(CircuitState.HALF_OPEN, "recovery timeout elapsed")
                    return True
                return False
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self._outcomes.append(True)
            self.total_successes += 1
            self.consecutive_failures = 0
            if self.state == CircuitState.HALF_OPEN:
                self._record_transition(CircuitState.CLOSED, "probe succeeded")
            self.opened_at = None

    async def record_failure(self, reason: str = "call failed") -> None:
        async with self._lock:
            self._outcomes.append(False)
            self.total_failures += 1
            self.consecutive_failures += 1
            if self.state == CircuitState.HALF_OPEN:
                self._open(reason=f"probe failed: {reason}")
                return
            if self.state == CircuitState.CLOSED:
                if self.consecutive_failures >= self.failure_threshold:
                    self._open(reason=f"{self.consecutive_failures} consecutive failures")
                elif self.failure_ratio is not None and self.failure_ratio >= self.failure_ratio_threshold:
                    self._open(reason=f"failure ratio {self.failure_ratio:.0%} over {len(self._outcomes)} samples")

    def _open(self, reason: str) -> None:
        self.opened_at = time.monotonic()
        self._record_transition(CircuitState.OPEN, reason)

    async def reset(self, reason: str = "manual reset") -> None:
        """Clear the failure state without erasing the observation history.

        ``samples`` is evidence ("we have looked N times"); wiping it on recovery made a
        subsystem that had just been verified read as never-observed in the self-model.
        """
        async with self._lock:
            self.consecutive_failures = 0
            self.opened_at = None
            if self.state != CircuitState.CLOSED:
                self._record_transition(CircuitState.CLOSED, reason)

    def snapshot(self) -> dict[str, Any]:
        return {
            "subsystem": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "failure_ratio": round(self.failure_ratio, 4) if self.failure_ratio is not None else None,
            "samples": len(self._outcomes),
            "outage_for_seconds": self.outage_for(),
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "last_transitions": list(self.transitions[-3:]),
        }


@dataclass
class SubsystemStatus:
    name: str
    available: bool
    detail: dict[str, Any]
    outage_for_seconds: float = 0.0


class HealthRegistry:
    """Tracks every subsystem CORTEX depends on, with observed outcomes."""

    def __init__(self) -> None:
        self._circuits: dict[str, SubsystemCircuit] = {}
        self._probes: dict[str, Callable[[], Awaitable[Any]]] = {}
        self._last_probe: dict[str, dict[str, Any]] = {}

    def circuit(self, name: str, **kwargs: Any) -> SubsystemCircuit:
        if name not in self._circuits:
            self._circuits[name] = SubsystemCircuit(name, **kwargs)
        return self._circuits[name]

    def register_probe(self, name: str, probe: Callable[[], Awaitable[Any]]) -> None:
        """Register a probe for the supervisor.

        A probe returns a ``ProbeResult`` (or, for legacy probes, a bool:
        True = healthy). ``ProbeResult.UNCONFIGURED`` means the subsystem is
        not configured in this deployment and must not be scored as a failure.
        """
        self._probes[name] = probe
        self.circuit(name)

    async def run_probe_result(self, name: str) -> ProbeResult:
        """Run a probe and return its tri-state result.

        Circuit outcomes are recorded only for genuine observations:
        ``HEALTHY`` records a success and ``UNHEALTHY`` a failure, while
        ``UNCONFIGURED`` records *no* outcome — an absent configuration is
        not evidence about the subsystem's health, and counting it as a
        failure is what opened circuits and burned repair budgets for a
        provider that was never configured (TASK-COR-014).
        """
        probe = self._probes.get(name)
        circuit = self.circuit(name)
        if probe is None:
            self._last_probe[name] = {"checked_at": _utcnow().isoformat(), "healthy": None, "reason": "no probe"}
            return ProbeResult.HEALTHY
        try:
            result = ProbeResult.coerce(await probe())
        except Exception as exc:  # a probe that raises is a failed probe
            result = ProbeResult.UNHEALTHY
            self._last_probe[name] = {
                "checked_at": _utcnow().isoformat(),
                "healthy": False,
                "result": result.value,
                "error": str(exc)[:200],
            }
        else:
            self._last_probe[name] = {
                "checked_at": _utcnow().isoformat(),
                "healthy": result.healthy if result is not ProbeResult.UNCONFIGURED else None,
                "result": result.value,
            }
        if result is ProbeResult.HEALTHY:
            await circuit.record_success()
        elif result is ProbeResult.UNHEALTHY:
            await circuit.record_failure("health probe failed")
        return result

    async def run_probe(self, name: str) -> bool:
        """Bool view of ``run_probe_result``: True only when HEALTHY.

        Kept for existing callers. Note an UNCONFIGURED subsystem reads as
        False here but records no circuit failure — callers that need to
        distinguish "down" from "not configured" should use
        ``run_probe_result`` (the supervisor does).
        """
        return (await self.run_probe_result(name)) is ProbeResult.HEALTHY

    def status(self) -> list[SubsystemStatus]:
        return [
            SubsystemStatus(
                name=name,
                available=circuit.is_available(),
                detail=circuit.snapshot(),
                outage_for_seconds=circuit.outage_for(),
            )
            for name, circuit in self._circuits.items()
        ]

    def snapshot(self) -> dict[str, Any]:
        degraded = [s.name for s in self.status() if not s.available]
        return {
            "subsystems": {s.name: s.detail for s in self.status()},
            "degraded": degraded,
            "last_probes": dict(self._last_probe),
            "observed_at": _utcnow().isoformat(),
        }


@dataclass
class RepairOutcome:
    subsystem: str
    action: str
    repaired: bool
    escalated: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "subsystem": self.subsystem,
            "action": self.action,
            "repaired": self.repaired,
            "escalated": self.escalated,
            "detail": self.detail,
        }


@dataclass
class HealingRun:
    started_at: datetime
    checked: list[str] = field(default_factory=list)
    unhealthy: list[str] = field(default_factory=list)
    unconfigured: list[str] = field(default_factory=list)
    repairs: list[RepairOutcome] = field(default_factory=list)
    escalations_delivered: list[dict[str, Any]] = field(default_factory=list)
    # TASK-CTX-004 ratio-check snapshot for this cycle (streaks, signal
    # rates, delivery gap, alerts); {} when the check evaluated nothing.
    ratio_check: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def repaired(self) -> list[str]:
        return [r.subsystem for r in self.repairs if r.repaired]

    @property
    def escalated(self) -> list[str]:
        return [r.subsystem for r in self.repairs if r.escalated]

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "checked": list(self.checked),
            "unhealthy": list(self.unhealthy),
            "unconfigured": list(self.unconfigured),
            "repaired": self.repaired,
            "escalated": self.escalated,
            "repairs": [r.as_dict() for r in self.repairs],
            "escalations_delivered": list(self.escalations_delivered),
            "ratio_check": dict(self.ratio_check),
            "duration_ms": round(self.duration_ms, 3),
        }


class SelfHealingSupervisor:
    """Probes subsystems, applies bounded repairs, escalates what it cannot fix."""

    def __init__(
        self,
        registry: HealthRegistry,
        repair_cooldown_seconds: float = 30.0,
        max_repairs_per_subsystem: int = 3,
        notifier: EscalationNotifier | None = None,
        # TASK-CTX-004: alert when a subsystem reports no health signal for
        # this many consecutive cycles (default 10 = 5 min at the 30 s tick —
        # long enough to ride out a restart, short enough to catch a silently
        # dead probe within minutes). Proposed value; the coordinator may
        # adjust it. 0 disables the unconfigured-streak alert.
        unconfigured_streak_threshold: int = 10,
        # TASK-CTX-004: alert when this many escalation deliveries fail in a
        # row (the escalation channel itself is broken). 0 disables it.
        delivery_gap_threshold: int = 3,
    ) -> None:
        self.registry = registry
        self.repair_cooldown_seconds = repair_cooldown_seconds
        self.max_repairs_per_subsystem = max_repairs_per_subsystem
        self.unconfigured_streak_threshold = unconfigured_streak_threshold
        self.delivery_gap_threshold = delivery_gap_threshold
        self._repairs: dict[str, list[float]] = {}
        self._attempts: dict[str, int] = {}
        self._repair_fns: dict[str, Callable[[], Awaitable[bool]]] = {}
        self.escalations: list[dict[str, Any]] = []
        # TASK-CTX-004: consecutive cycles each subsystem has spent in
        # ``run.unconfigured`` — the "no health signal" streak. A restart
        # builds a new supervisor, so streaks reset with the process (and a
        # healthy observation clears the streak mid-process, below).
        self._unconfigured_streaks: dict[str, int] = {}
        # Subsystems already alerted for their current unconfigured streak.
        # Marked only when the alert delivery actually lands (the TASK-COR-013
        # fix-up): a failed first delivery must not consume the streak, so
        # enabling the channel mid-streak still pages. Cleared when a probe
        # observes the subsystem configured again.
        self._ratio_alerted: set[str] = set()
        # TASK-CTX-004: consecutive failed escalation deliveries, across all
        # escalation paths (they all flow through ``_notify``). A successful
        # delivery resets it, so a later broken-channel period alerts afresh.
        self._delivery_failures: int = 0
        # Whether the channel-broken alert has been attempted for the current
        # broken-channel streak. Marked on a landed delivery — or on an
        # attempt that fails only because no channel is configured at all
        # (retrying that every cycle could never land); a later successful
        # delivery clears it.
        self._channel_broken_alerted: bool = False
        # Last ratio-check alert (either kind), for ``ratio_check_status``.
        self._last_ratio_alert: dict[str, Any] | None = None
        # Subsystems already escalated during their current continuous failure
        # streak (TASK-COR-013): an escalation is delivered once per streak,
        # not once per cycle. Cleared when a probe observes the subsystem
        # healthy again (or a repair verifies), so a new outage re-escalates.
        self._escalated_streaks: set[str] = set()
        # Subsystems already given a configuration notice during their current
        # unconfigured streak (TASK-COR-014): the notice is logged once per
        # streak, and the entry is cleared as soon as a probe observes the
        # subsystem configured again (healthy or unhealthy), so a later
        # unconfigured period is noticed afresh.
        self._unconfigured_noticed: set[str] = set()
        self.notifier = notifier or EscalationNotifier()

    def register_repair(self, subsystem: str, repair: Callable[[], Awaitable[bool]]) -> None:
        """A repair returns True when it *verified* the subsystem works again."""
        self._repair_fns[subsystem] = repair

    async def _notify(self, escalation: dict[str, Any], run: HealingRun) -> dict[str, Any]:
        """Hand the escalation to the operator channel; never let delivery break healing."""
        try:
            delivery = await self.notifier.deliver(escalation)
        except Exception as exc:  # noqa: BLE001 - defensive: the notifier already guards itself
            delivery = {"delivered": False, "detail": f"{type(exc).__name__}: {exc}"}
        run.escalations_delivered.append(delivery)
        # TASK-CTX-004 delivery gap: every escalation path flows through
        # here, so this is the one place the channel's own health is counted.
        # A dedupe suppression is not a channel failure (that exact page
        # already landed inside the window), so it must not count.
        if delivery.get("delivered"):
            self._delivery_failures = 0
            self._channel_broken_alerted = False
        elif "duplicate suppressed" not in str(delivery.get("detail", "")):
            self._delivery_failures += 1
        return delivery

    async def _escalate(self, escalation: dict[str, Any], run: HealingRun) -> None:
        """Record an escalation and deliver it — once per failure streak.

        TASK-COR-013: previously a permanently failing subsystem was
        re-delivered on every cycle, throttled only by the notifier's dedupe
        window. With the production loop ticking every 30s and that window at
        600s, the operator received one identical message every ~10 minutes
        indefinitely (the ``ai_universe`` escalation, for a provider that is
        intentionally unconfigured in this deployment, delivered 247 times in
        48h before the channel was disconnected on 2026-11-19). The escalation
        is still recorded every cycle; delivery happens on the transition
        into the escalated state and repeats within the same streak are
        recorded as suppressed.

        Fix-up (review C1): the streak is marked only when a delivery
        actually lands (``delivered=True``). A failed first delivery (the
        channel answered 500) or a first attempt made while no channel is
        configured must not consume the streak — the escalation is retried
        on a later cycle, so enabling the channel mid-outage still pages.
        """
        self.escalations.append(escalation)
        self.escalations = self.escalations[-20:]
        subsystem = str(escalation.get("subsystem", ""))
        if subsystem in self._escalated_streaks:
            run.escalations_delivered.append(
                {
                    "subsystem": escalation.get("subsystem"),
                    "reason": escalation.get("reason"),
                    "at": escalation.get("at"),
                    "channel": self.notifier.channel,
                    "delivered": False,
                    "detail": "suppressed: already escalated for this failure streak",
                }
            )
            return
        delivery = await self._notify(escalation, run)
        if delivery.get("delivered"):
            self._escalated_streaks.add(subsystem)

    def _throttled(self, subsystem: str) -> bool:
        history = [t for t in self._repairs.get(subsystem, []) if time.monotonic() - t < self.repair_cooldown_seconds]
        return bool(history)

    def ratio_check_status(self) -> dict[str, Any]:
        """Current TASK-CTX-004 ratio-check state (also the shape stored on each run).

        ``signal_rate`` is healthy observations / all circuit observations
        (``total_successes`` / ``total_successes + total_failures``); an
        unconfigured subsystem records no circuit outcome, so its rate is
        ``None`` with 0 samples — the "no health signal" signature.
        """
        signal_rate: dict[str, dict[str, Any]] = {}
        for status in self.registry.status():
            successes = status.detail.get("total_successes", 0)
            failures = status.detail.get("total_failures", 0)
            samples = successes + failures
            signal_rate[status.name] = {
                "rate": round(successes / samples, 4) if samples else None,
                "samples": samples,
            }
        return {
            "threshold_cycles": self.unconfigured_streak_threshold,
            "delivery_gap_threshold": self.delivery_gap_threshold,
            "unconfigured_streaks": {k: v for k, v in self._unconfigured_streaks.items() if v},
            "signal_rate": signal_rate,
            "consecutive_failed_deliveries": self._delivery_failures,
            "channel_broken": self.delivery_gap_threshold > 0
            and self._delivery_failures >= self.delivery_gap_threshold,
            "last_alert": dict(self._last_ratio_alert) if self._last_ratio_alert else None,
        }

    async def _deliver_ratio_alert(self, escalation: dict[str, Any], run: HealingRun) -> dict[str, Any]:
        """Deliver a ratio-check alert through the escalation channel.

        Deliberately NOT routed through ``_escalate``: that path suppresses
        on ``_escalated_streaks`` (failure streaks), which would both swallow
        a ratio alert that follows a failure streak and let a ratio alert
        suppress a later genuine failure escalation. The ratio check tracks
        its own once-per-streak state (``_ratio_alerted`` /
        ``_channel_broken_alerted``) and reuses the delivery machinery
        (``_notify``) plus the COR-013 fix-up — only a landed delivery marks
        the streak.
        """
        self.escalations.append(escalation)
        self.escalations = self.escalations[-20:]
        return await self._notify(escalation, run)

    async def _evaluate_ratio_check(self, run: HealingRun) -> None:
        """TASK-CTX-004: alert on a silent probe or a broken alert channel.

        Runs at the end of every cycle, after the per-subsystem loop has
        updated the streaks. Both alerts are once per streak; a failed
        delivery never consumes the streak (retry next cycle), except the
        channel-broken alert when no channel is configured at all — that
        attempt can never land, so it is marked attempted once and the
        broken state stays visible in ``ratio_check_status`` instead.
        """
        # (a) Unconfigured streak: no health signal for N consecutive cycles.
        if self.unconfigured_streak_threshold > 0:
            for name, streak in sorted(self._unconfigured_streaks.items()):
                if streak < self.unconfigured_streak_threshold or name in self._ratio_alerted:
                    continue
                escalation = {
                    "subsystem": name,
                    "reason": (
                        f"no health signal from {name} for "
                        f"{self.unconfigured_streak_threshold}+ consecutive cycles (unconfigured)"
                    ),
                    "at": _utcnow().isoformat(),
                    "detail": f"unconfigured for {streak} consecutive cycles; 0 circuit samples",
                }
                delivery = await self._deliver_ratio_alert(escalation, run)
                if delivery.get("delivered"):
                    self._ratio_alerted.add(name)
                    self._last_ratio_alert = dict(escalation)
                    run.repairs.append(
                        RepairOutcome(name, "ratio-check", False, True, escalation["reason"])
                    )
                    logger.warning(
                        "self-healing ratio-check: %s unconfigured for %d cycles; escalated",
                        name,
                        streak,
                    )
        # (b) Delivery gap: the escalation channel itself is not delivering.
        if (
            self.delivery_gap_threshold > 0
            and self._delivery_failures >= self.delivery_gap_threshold
            and not self._channel_broken_alerted
        ):
            escalation = {
                "subsystem": "escalation-channel",
                "reason": "escalation channel not delivering",
                "at": _utcnow().isoformat(),
                "detail": f"{self._delivery_failures} consecutive failed deliveries",
            }
            # NB: a landed delivery resets ``_delivery_failures`` inside
            # ``_notify``, so the triggering count is captured beforehand.
            failures = self._delivery_failures
            delivery = await self._deliver_ratio_alert(escalation, run)
            if delivery.get("delivered") or "no escalation channel configured" in str(
                delivery.get("detail", "")
            ):
                self._channel_broken_alerted = True
                self._last_ratio_alert = dict(escalation)
                logger.warning(
                    "self-healing ratio-check: escalation channel not delivering "
                    "(%d consecutive failures); escalated",
                    failures,
                )
        run.ratio_check = self.ratio_check_status()

    async def run_cycle(self) -> HealingRun:
        run = HealingRun(started_at=_utcnow())
        started = time.perf_counter()

        for status in self.registry.status():
            run.checked.append(status.name)
            circuit = self.registry.circuit(status.name)

            # Always observe. The first version of this loop skipped CLOSED circuits, so a
            # breaker that had never opened was never probed either — no observation, no
            # samples, no way to ever open. Detection has to come from probing, not from
            # waiting for a failure to announce itself.
            probe_result = await self.registry.run_probe_result(status.name)
            if probe_result is ProbeResult.UNCONFIGURED:
                # Not configured in this deployment: a standing configuration
                # notice, not a failure (TASK-COR-014). No circuit outcome was
                # recorded, and the subsystem must not enter the repair /
                # escalation path or consume repair attempts — logged once
                # per unconfigured streak and listed on the run as
                # ``unconfigured``, never as ``unhealthy``. This branch sits
                # ahead of the TASK-COR-013 healthy-observation streak clear
                # below on purpose: UNCONFIGURED is not a healthy observation
                # and must not end an escalated failure streak.
                run.unconfigured.append(status.name)
                # TASK-CTX-004: count consecutive cycles with no health signal.
                self._unconfigured_streaks[status.name] = (
                    self._unconfigured_streaks.get(status.name, 0) + 1
                )
                if status.name not in self._unconfigured_noticed:
                    self._unconfigured_noticed.add(status.name)
                    logger.info(
                        "self-healing: subsystem %s is not configured; "
                        "treating as a standing configuration notice (no repair, no escalation)",
                        status.name,
                    )
                continue
            self._unconfigured_noticed.discard(status.name)
            # TASK-CTX-004: a configured probe — healthy or not — IS a health
            # signal, so the unconfigured streak ends and a later unconfigured
            # period alerts afresh.
            self._unconfigured_streaks[status.name] = 0
            self._ratio_alerted.discard(status.name)
            healthy = probe_result is ProbeResult.HEALTHY
            if healthy:
                # A healthy observation ends any failure streak: a later
                # outage is a new incident and may escalate again
                # (TASK-COR-013).
                self._escalated_streaks.discard(status.name)
            if healthy and circuit.state is CircuitState.CLOSED:
                continue
            run.unhealthy.append(status.name)

            # Something may have recovered on its own (self-healing without intervention).
            if healthy:
                if circuit.state is not CircuitState.CLOSED:
                    await circuit.reset("probe succeeded")
                run.repairs.append(RepairOutcome(status.name, "probe", True, False, "recovered without intervention"))
                continue

            if self._throttled(status.name):
                run.repairs.append(RepairOutcome(status.name, "repair", False, False, "repair throttled by cooldown"))
                continue

            attempts = self._attempts.get(status.name, 0)
            if attempts >= self.max_repairs_per_subsystem:
                escalation = {
                    "subsystem": status.name,
                    "reason": f"{attempts} repair attempts did not restore health",
                    "at": _utcnow().isoformat(),
                }
                await self._escalate(escalation, run)
                run.repairs.append(RepairOutcome(status.name, "none", False, True, escalation["reason"]))
                continue

            repair = self._repair_fns.get(status.name)
            if repair is None:
                escalation = {
                    "subsystem": status.name,
                    "reason": "no repair action registered",
                    "at": _utcnow().isoformat(),
                }
                await self._escalate(escalation, run)
                run.repairs.append(RepairOutcome(status.name, "none", False, True, "no repair action registered"))
                continue

            self._repairs.setdefault(status.name, []).append(time.monotonic())
            self._attempts[status.name] = attempts + 1
            try:
                repaired = bool(await repair())
            except Exception as exc:
                run.repairs.append(
                    RepairOutcome(status.name, "repair", False, False, f"repair raised {type(exc).__name__}: {exc}")
                )
                continue

            # A repair is only a repair if the subsystem is verifiably healthy afterwards.
            # (run_probe_result, not the bool view: a repair that leaves the subsystem
            # UNCONFIGURED has not restored health either, and the verifying probe must
            # not record a second failure outcome for the same observation.)
            verified = repaired and (await self.registry.run_probe_result(status.name)) is ProbeResult.HEALTHY
            if verified:
                circuit = self.registry.circuit(status.name)
                await circuit.reset("self-healing repair verified")
                await circuit.record_success()  # the verifying probe is evidence of health
                self._attempts[status.name] = 0
                self._escalated_streaks.discard(status.name)
                run.repairs.append(RepairOutcome(status.name, "repair+probe", True, False, "repair verified by probe"))
            else:
                run.repairs.append(
                    RepairOutcome(status.name, "repair+probe", False, False, "repair did not restore health")
                )

        # TASK-CTX-004: evaluate the standing ratio check on this cycle's data.
        await self._evaluate_ratio_check(run)

        run.duration_ms = (time.perf_counter() - started) * 1000
        return run


# Process-wide registry: subsystems report here, the supervisor heals from here.
global_health_registry = HealthRegistry()


class SelfHealingLoop:
    """Runs the supervisor on a cadence, forever, and never dies doing it.

    The on/off switch and the cadence are re-read on every tick, so a runtime knob change
    (including an operator-approved self-modification) takes effect on the next tick instead
    of requiring a restart. A failing cycle is counted and logged, not raised.
    """

    def __init__(
        self,
        supervisor: SelfHealingSupervisor,
        settings_provider: Callable[[], tuple[bool, float]] | None = None,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self.supervisor = supervisor
        self._settings_provider = settings_provider or (lambda: (True, 30.0))
        self.min_interval_seconds = min_interval_seconds
        self.cycles = 0
        self.errors = 0
        self.skipped_disabled = 0
        self.last_run: HealingRun | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def tick(self) -> None:
        enabled, interval = self._settings_provider()
        if enabled:
            try:
                self.last_run = await self.supervisor.run_cycle()
                self.cycles += 1
                self.last_error = None
            except Exception as exc:  # noqa: BLE001 - the loop must outlive a bad cycle
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("self-healing cycle failed: %s", exc)
        else:
            self.skipped_disabled += 1
        await asyncio.sleep(max(float(interval), self.min_interval_seconds))

    async def run_forever(self) -> None:
        while True:
            await self.tick()

    def start(self) -> asyncio.Task:
        if self.running:
            return self._task  # type: ignore[return-value]
        self._task = asyncio.create_task(self.run_forever())
        self._task.add_done_callback(self._on_done)
        return self._task

    @staticmethod
    def _on_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:  # pragma: no cover - defensive
            logger.error("self-healing loop terminated unexpectedly: %s", exc)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "cycles": self.cycles,
            "errors": self.errors,
            "skipped_while_disabled": self.skipped_disabled,
            "last_error": self.last_error,
            "last_checked_at": self.last_run.started_at.isoformat() if self.last_run else None,
            "last_unhealthy": list(self.last_run.unhealthy) if self.last_run else [],
            "last_unconfigured": list(self.last_run.unconfigured) if self.last_run else [],
            "last_repairs": [
                r.as_dict() if hasattr(r, "as_dict") else r for r in (self.last_run.repairs if self.last_run else [])
            ],
            "escalation_channel": self.supervisor.notifier.status(),
            # TASK-CTX-004: the standing escalation-ratio check — per-subsystem
            # unconfigured streaks, signal rates, delivery gap, last alert.
            "ratio_check": self.supervisor.ratio_check_status(),
        }


# ── Telegram sendMessage targets ─────────────────────────────────────────────
# The fleet's proven operator channel is Telegram via the FRIDAY bot, whose
# Bot API ``sendMessage`` method requires ``chat_id`` and ``text`` — neither
# exists in the generic escalation payload, so a generic JSON POST to a
# sendMessage URL is rejected with HTTP 400 (verified locally against the
# documented parameter handling, TASK-COR-010). When the configured webhook
# URL is a Telegram sendMessage URL, both delivery paths (this notifier and
# ``cortex_api.agent_budgets.WebhookBreachAlertSink``) translate the event
# into Telegram's shape first. The chat id is NOT part of the webhook URL —
# it comes from the environment at delivery time.

TELEGRAM_CHAT_ID_ENV = "SELF_HEALING_ESCALATION_TELEGRAM_CHAT_ID"
TELEGRAM_TEXT_LIMIT = 4096


def is_telegram_send_message_url(url: str | None) -> bool:
    """True iff ``url`` targets the Telegram Bot API ``sendMessage`` method."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if (parsed.hostname or "").lower() != "api.telegram.org":
        return False
    return parsed.path.rstrip("/").endswith("/sendMessage")


def format_escalation_text(event: dict[str, Any]) -> str:
    """Compose the human-readable Telegram ``text`` for an escalation event.

    Accepts either producer's shape: the supervisor's escalation dict
    (``subsystem`` / ``reason`` / ``at``) or the budget sink's payload
    (``agent`` / ``message`` / ``reason``). Truncated to Telegram's
    4096-character limit.
    """
    lines = ["Cortex escalation"]
    agent = event.get("agent")
    if agent:
        lines.append(f"Agent: {agent}")
    subsystem = event.get("subsystem")
    if subsystem:
        lines.append(f"Subsystem: {subsystem}")
    message = event.get("message")
    if message:
        lines.append(str(message))
    reason = event.get("reason")
    if reason and (not message or str(reason) not in str(message)):
        lines.append(f"Reason: {reason}")
    at = event.get("at")
    if at:
        lines.append(f"At: {at}")
    text = "\n".join(lines)
    if len(text) > TELEGRAM_TEXT_LIMIT:
        text = text[: TELEGRAM_TEXT_LIMIT - 3] + "..."
    return text


def telegram_delivery_payload(event: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Build the ``sendMessage`` body for ``event``.

    Returns ``(payload, None)`` on success or ``(None, detail)`` when the
    chat id is not configured — the caller records that as
    ``delivered: False`` with the reason, never a pretend success.
    """
    raw = os.environ.get(TELEGRAM_CHAT_ID_ENV, "").strip()
    if not raw:
        return None, (
            "telegram escalation target configured but "
            f"{TELEGRAM_CHAT_ID_ENV} is unset"
        )
    chat_id: Any = int(raw) if raw.lstrip("-").isdigit() else raw
    return {"chat_id": chat_id, "text": format_escalation_text(event)}, None


def channel_descriptor(webhook_url: str | None) -> str:
    """Redacted label for an escalation channel, safe for persisted records.

    Delivery records and status payloads are persisted and endpoint-exposed,
    and a Telegram ``sendMessage`` URL embeds the bot token in its path — so
    a record must never carry the URL itself. The descriptor keeps only the
    channel kind and host: ``telegram:api.telegram.org`` for the Telegram
    Bot API, ``webhook:<host>`` for any other webhook, ``none`` when no
    channel is configured, and ``webhook:unknown`` when no host can be
    parsed out (the raw value is never echoed back).
    """
    if not webhook_url:
        return "none"
    host = urlparse(webhook_url.strip()).hostname
    if not host:
        return "webhook:unknown"
    if host == "api.telegram.org":
        return "telegram:api.telegram.org"
    return f"webhook:{host}"


# ── Log redaction for secret-bearing URLs ────────────────────────────────────
# ``channel_descriptor`` keeps webhook URLs out of persisted records, but log
# lines are a second leak path: httpx's INFO logger prints the full request
# URL ("HTTP Request: POST https://api.telegram.org/bot<TOKEN>/sendMessage"),
# and the Telegram URL embeds the bot token. The 2026-11-17 breach drill
# (TASK-COR-012) caught the token in Cortex's journal this way even though
# every persisted record was clean. The filter below rewrites log messages
# before any handler formats them, so the token never reaches a log sink
# while the rest of the line (method, host, path, status) stays useful.

_TELEGRAM_BOT_URL_RE = re.compile(r"(https?://api\.telegram\.org/bot)[^/\s\"'<>]+")
_BARE_BOT_TOKEN_RE = re.compile(r"\bbot\d{5,}:[A-Za-z0-9_-]{20,}\b")
REDACTED_BOT_SEGMENT = "bot***"


def redact_secret_urls(text: str) -> str:
    """Replace Telegram bot tokens in ``text`` with ``bot***``.

    Covers the full sendMessage URL form and a bare ``bot<id>:<token>``
    segment appearing anywhere else (e.g. inside an exception string).
    Text without a token is returned unchanged.
    """
    text = _TELEGRAM_BOT_URL_RE.sub(r"\1***", text)
    return _BARE_BOT_TOKEN_RE.sub(REDACTED_BOT_SEGMENT, text)


class SecretUrlRedactionFilter(logging.Filter):
    """Logging filter that redacts bot tokens from a record's message.

    The record is never dropped (``filter`` always returns True); its
    message is rewritten in place via ``record.getMessage()`` so every
    downstream handler and formatter sees only the redacted text.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never break logging itself
            return True
        redacted = redact_secret_urls(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def install_secret_url_log_redaction(
    logger_names: tuple[str, ...] = ("httpx", "httpcore"),
) -> SecretUrlRedactionFilter:
    """Attach a shared ``SecretUrlRedactionFilter`` to the HTTP client loggers.

    httpx logs every request URL at INFO; httpcore is its transport layer.
    Both producers of escalation traffic (this module's
    ``EscalationNotifier`` and ``cortex_api.agent_budgets``'
    ``WebhookBreachAlertSink``) emit through these loggers in the Cortex
    API process, whose startup calls this once. Idempotent: repeated calls
    return the already-installed filter instead of stacking duplicates.
    """
    shared: SecretUrlRedactionFilter | None = None
    for name in logger_names:
        target = logging.getLogger(name)
        existing = next(
            (f for f in target.filters if isinstance(f, SecretUrlRedactionFilter)),
            None,
        )
        if existing is not None:
            if shared is None:
                shared = existing
            continue
        if shared is None:
            shared = SecretUrlRedactionFilter()
        target.addFilter(shared)
    assert shared is not None  # logger_names is never empty in practice
    return shared


class EscalationNotifier:
    """Delivers escalations to an operator channel — or says plainly that it could not.

    Without a configured channel this does not pretend to notify anyone: it records
    ``delivered: False`` with the reason. Repeated escalations for the same subsystem and
    reason are collapsed inside ``dedupe_window_seconds`` and counted, so a permanently
    broken dependency cannot spam an operator into ignoring the channel.

    Delivery records name the channel by its redacted descriptor (see
    ``channel_descriptor``), never the webhook URL: the records persist and
    are endpoint-exposed, and a Telegram URL carries the bot token.
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        timeout_seconds: float = 5.0,
        # 6h, aligned with the fleet owner-notification policy (FRD-025's
        # per-key cooldown). The previous 600s default, combined with the
        # supervisor's per-cycle re-escalation, produced the TASK-COR-013
        # spam cadence; the supervisor now also delivers once per failure
        # streak, so this window is a backstop, not the only throttle.
        dedupe_window_seconds: float = 21600.0,
    ) -> None:
        self.webhook_url = (webhook_url or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self.dedupe_window_seconds = dedupe_window_seconds
        self.deliveries: list[dict[str, Any]] = []
        self.suppressed = 0
        self._last_sent: dict[tuple[str, str], float] = {}

    @property
    def channel(self) -> str:
        # Redacted descriptor only — the full URL (a Telegram one carries
        # the bot token) must never reach a delivery record or status.
        return channel_descriptor(self.webhook_url)

    def _recently_sent(self, key: tuple[str, str]) -> bool:
        last = self._last_sent.get(key)
        return last is not None and (time.monotonic() - last) < self.dedupe_window_seconds

    async def deliver(self, escalation: dict[str, Any]) -> dict[str, Any]:
        key = (str(escalation.get("subsystem", "")), str(escalation.get("reason", "")))
        record = {
            "subsystem": escalation.get("subsystem"),
            "reason": escalation.get("reason"),
            "at": _utcnow().isoformat(),
            "channel": self.channel,
        }
        if self.webhook_url is None:
            record.update({"delivered": False, "detail": "no escalation channel configured"})
            self.deliveries.append(record)
            return record
        if self._recently_sent(key):
            self.suppressed += 1
            record.update({"delivered": False, "detail": "duplicate suppressed within dedupe window"})
            self.deliveries.append(record)
            return record

        payload: dict[str, Any] = escalation
        if is_telegram_send_message_url(self.webhook_url):
            payload, error = telegram_delivery_payload(escalation)
            if payload is None:
                record.update({"delivered": False, "detail": error})
                self.deliveries.append(record)
                return record

        import httpx

        try:
            # trust_env=False, mirroring WebhookBreachAlertSink: the
            # escalation webhook is a configured operator endpoint —
            # ambient HTTP(S)_PROXY variables must not intercept or break
            # alert delivery.
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.post(self.webhook_url, json=payload)
            delivered = 200 <= response.status_code < 300
            record.update(
                {
                    "delivered": delivered,
                    "status_code": response.status_code,
                    "detail": "delivered" if delivered else f"channel returned {response.status_code}",
                }
            )
            if delivered:
                self._last_sent[key] = time.monotonic()
        except Exception as exc:  # noqa: BLE001 - a notification failure is not a healing failure
            detail = f"{type(exc).__name__}: {exc}"
            if self.webhook_url and self.webhook_url in detail:
                # Transport errors can embed the URL; the record must not.
                detail = detail.replace(self.webhook_url, self.channel)
            record.update({"delivered": False, "detail": detail})
        self.deliveries.append(record)
        self.deliveries = self.deliveries[-50:]
        return record

    def status(self) -> dict[str, Any]:
        delivered = [d for d in self.deliveries if d.get("delivered")]
        return {
            "channel": self.channel,
            "channel_configured": self.webhook_url is not None,
            "attempts": len(self.deliveries),
            "delivered": len(delivered),
            "suppressed_duplicates": self.suppressed,
            "last_attempt": self.deliveries[-1] if self.deliveries else None,
        }
