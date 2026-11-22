"""TASK-CTX-004: the escalation ratio as a standing live check.

Pins the decision logic deterministically. The raw fires/messages ratio is
degenerate — zero deliveries is the correct output of a healthy fleet *and*
of a fleet whose probe observes nothing — so the check is defined on the
per-cycle run data: per-subsystem unconfigured streaks, signal rate, and the
delivery gap (consecutive failed escalation deliveries).
"""

from __future__ import annotations

import asyncio

from cortex_core.resilience import (
    EscalationNotifier,
    HealthRegistry,
    ProbeResult,
    SelfHealingLoop,
    SelfHealingSupervisor,
)


def _run(coro):
    return asyncio.run(coro)


class _RecordingNotifier:
    """Notifier seam double: records deliveries instead of sending them."""

    channel = "test:recording"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def deliver(self, escalation):
        self.calls.append(dict(escalation))
        return {"delivered": True, "subsystem": escalation.get("subsystem"), "channel": self.channel}

    def status(self):
        # Same shape as EscalationNotifier.status(): loop.status() reads it.
        return {
            "channel": self.channel,
            "channel_configured": True,
            "attempts": len(self.calls),
            "delivered": len(self.calls),
            "suppressed_duplicates": 0,
            "last_attempt": None,
        }


class _FlakyNotifier:
    """Notifier seam double: the first ``failures`` deliveries fail the way a
    channel answering HTTP 500 would; later deliveries succeed."""

    channel = "test:flaky"

    def __init__(self, failures: int = 1) -> None:
        self.calls: list[dict] = []
        self._failures = failures

    async def deliver(self, escalation):
        self.calls.append(dict(escalation))
        if self._failures > 0:
            self._failures -= 1
            return {
                "delivered": False,
                "subsystem": escalation.get("subsystem"),
                "channel": self.channel,
                "detail": "channel returned 500",
            }
        return {"delivered": True, "subsystem": escalation.get("subsystem"), "channel": self.channel}

    def status(self):
        # Same shape as EscalationNotifier.status(): loop.status() reads it.
        return {
            "channel": self.channel,
            "channel_configured": True,
            "attempts": len(self.calls),
            "delivered": len(self.calls),
            "suppressed_duplicates": 0,
            "last_attempt": None,
        }


def _unconfigured_probe():
    async def probe():
        return ProbeResult.UNCONFIGURED

    return probe


# ── TASK-CTX-004 escalation-ratio standing check ─────────────────────────────


def test_ratio_check_counts_streak_and_alerts_once_per_streak():
    """An unconfigured subsystem alerts once it reaches the streak threshold,
    and the operator is NOT paged again while the same streak continues."""
    registry = HealthRegistry()
    registry.register_probe("ai_universe", _unconfigured_probe())
    notifier = _RecordingNotifier()
    supervisor = SelfHealingSupervisor(
        registry, repair_cooldown_seconds=0.0, notifier=notifier, unconfigured_streak_threshold=3
    )

    first = _run(supervisor.run_cycle())
    assert first.unconfigured == ["ai_universe"]
    assert first.ratio_check["unconfigured_streaks"] == {"ai_universe": 1}
    assert first.escalated == []
    assert len(notifier.calls) == 0

    second = _run(supervisor.run_cycle())
    assert second.ratio_check["unconfigured_streaks"] == {"ai_universe": 2}
    assert len(notifier.calls) == 0

    third = _run(supervisor.run_cycle())
    assert third.ratio_check["unconfigured_streaks"] == {"ai_universe": 3}
    assert third.escalated == ["ai_universe"]
    assert len(notifier.calls) == 1
    assert "no health signal" in notifier.calls[0]["reason"]
    assert third.ratio_check["last_alert"]["subsystem"] == "ai_universe"

    # The streak continues: the count keeps growing, but no second page.
    for _ in range(3):
        run = _run(supervisor.run_cycle())
        assert run.escalated == []
    assert len(notifier.calls) == 1
    assert supervisor.ratio_check_status()["unconfigured_streaks"] == {"ai_universe": 6}


def test_ratio_check_healthy_observation_clears_streak_and_realerts():
    """A configured probe — healthy or not — is a health signal, so the
    streak ends; a later unconfigured period is a new streak and pages again."""
    registry = HealthRegistry()
    state = {"probe": ProbeResult.UNCONFIGURED}

    async def probe():
        return state["probe"]

    registry.register_probe("ai_universe", probe)
    notifier = _RecordingNotifier()
    supervisor = SelfHealingSupervisor(
        registry, repair_cooldown_seconds=0.0, notifier=notifier, unconfigured_streak_threshold=3
    )

    for _ in range(3):
        _run(supervisor.run_cycle())
    assert len(notifier.calls) == 1

    state["probe"] = ProbeResult.HEALTHY
    cleared = _run(supervisor.run_cycle())
    assert cleared.unconfigured == []
    assert cleared.ratio_check["unconfigured_streaks"] == {}
    assert len(notifier.calls) == 1

    state["probe"] = ProbeResult.UNCONFIGURED
    for _ in range(3):
        _run(supervisor.run_cycle())
    assert len(notifier.calls) == 2


def test_ratio_check_failed_delivery_does_not_consume_streak():
    """TASK-COR-013 fix-up, applied to the ratio alert: a failed first
    delivery must not consume the unconfigured streak. The next cycle retries
    the alert; only a delivery that lands marks the streak."""
    registry = HealthRegistry()
    registry.register_probe("ai_universe", _unconfigured_probe())
    notifier = _FlakyNotifier(failures=1)
    supervisor = SelfHealingSupervisor(
        registry, repair_cooldown_seconds=0.0, notifier=notifier, unconfigured_streak_threshold=2
    )

    _run(supervisor.run_cycle())  # streak 1, no alert yet
    failed = _run(supervisor.run_cycle())  # streak 2 -> alert attempt FAILS
    assert failed.escalated == []
    assert failed.escalations_delivered[0]["delivered"] is False
    assert len(notifier.calls) == 1

    retried = _run(supervisor.run_cycle())  # streak unmarked -> retry, lands
    assert retried.escalated == ["ai_universe"]
    assert retried.escalations_delivered[0]["delivered"] is True
    assert len(notifier.calls) == 2

    # Delivered at last: the rest of the streak is silent.
    _run(supervisor.run_cycle())
    assert len(notifier.calls) == 2


def test_ratio_check_restart_resets_streaks():
    """Streaks live on the supervisor instance, so a restart (new supervisor)
    starts counting from zero — a fresh process never inherits a stale streak."""
    registry = HealthRegistry()
    registry.register_probe("ai_universe", _unconfigured_probe())
    first = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        notifier=_RecordingNotifier(),
        unconfigured_streak_threshold=3,
    )
    for _ in range(2):
        _run(first.run_cycle())
    assert first.ratio_check_status()["unconfigured_streaks"] == {"ai_universe": 2}

    restarted = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        notifier=_RecordingNotifier(),
        unconfigured_streak_threshold=3,
    )
    assert restarted.ratio_check_status()["unconfigured_streaks"] == {}
    assert restarted.ratio_check_status()["consecutive_failed_deliveries"] == 0
    run = _run(restarted.run_cycle())
    assert run.ratio_check["unconfigured_streaks"] == {"ai_universe": 1}
    assert run.escalated == []


def test_ratio_check_delivery_gap_alerts_once_per_broken_channel():
    """When escalation deliveries keep failing, the check pages about the
    channel itself — once the alert lands, the broken-channel streak is
    marked and the operator is not paged again for it."""
    registry = HealthRegistry()

    async def probe() -> bool:
        return False

    async def repair() -> bool:
        return False  # cannot fix it

    registry.register_probe("redis", probe)
    # First three deliveries fail (the failure escalations), the fourth —
    # the channel-broken alert — succeeds.
    notifier = _FlakyNotifier(failures=3)
    supervisor = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        max_repairs_per_subsystem=1,
        notifier=notifier,
        delivery_gap_threshold=3,
    )
    supervisor.register_repair("redis", repair)

    _run(supervisor.run_cycle())  # repair attempt 1
    _run(supervisor.run_cycle())  # escalate -> delivery 1 FAILS
    _run(supervisor.run_cycle())  # escalate -> delivery 2 FAILS
    fourth = _run(supervisor.run_cycle())  # escalate -> delivery 3 FAILS, then channel alert
    assert len(notifier.calls) == 4
    assert notifier.calls[-1]["reason"] == "escalation channel not delivering"
    assert notifier.calls[-1]["subsystem"] == "escalation-channel"
    assert supervisor._channel_broken_alerted is True
    assert fourth.ratio_check["channel_broken"] is False  # the alert landed: gap reset
    assert fourth.ratio_check["last_alert"]["reason"] == "escalation channel not delivering"

    # The failure streak was never consumed by the failed deliveries, so the
    # next cycle retries the outage escalation — and it lands.
    _run(supervisor.run_cycle())
    assert len(notifier.calls) == 5


def test_ratio_check_channel_alert_attempted_once_when_no_channel_configured():
    """With no channel configured at all, the channel-broken alert is
    attempted once and then stands down — retrying it every cycle could
    never land, and the broken state stays visible in ratio_check."""
    registry = HealthRegistry()

    async def probe() -> bool:
        return False

    async def repair() -> bool:
        return False  # cannot fix it

    registry.register_probe("redis", probe)
    supervisor = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        max_repairs_per_subsystem=1,
        notifier=EscalationNotifier(),  # no webhook: every delivery fails
        delivery_gap_threshold=3,
    )
    supervisor.register_repair("redis", repair)

    for _ in range(6):
        _run(supervisor.run_cycle())
    channel_alerts = [
        e for e in supervisor.escalations if e["reason"] == "escalation channel not delivering"
    ]
    assert len(channel_alerts) == 1
    assert supervisor.ratio_check_status()["channel_broken"] is True


def test_ratio_check_status_exposes_streaks_signal_rate_and_last_alert():
    """The check state is visible in SelfHealingLoop.status() as ratio_check,
    which is what GET /v1/friday/self_healing serves."""
    registry = HealthRegistry()

    async def healthy_probe() -> bool:
        return True

    registry.register_probe("redis", healthy_probe)
    registry.register_probe("ai_universe", _unconfigured_probe())
    notifier = _RecordingNotifier()
    supervisor = SelfHealingSupervisor(
        registry, repair_cooldown_seconds=0.0, notifier=notifier, unconfigured_streak_threshold=3
    )
    loop = SelfHealingLoop(supervisor, settings_provider=lambda: (True, 0.0), min_interval_seconds=0.0)

    run = None
    for _ in range(3):
        run = _run(supervisor.run_cycle())

    status = loop.status()
    ratio = status["ratio_check"]
    assert ratio["threshold_cycles"] == 3
    assert ratio["unconfigured_streaks"] == {"ai_universe": 3}
    # A healthy probe is signal: 3 observations, all healthy.
    assert ratio["signal_rate"]["redis"] == {"rate": 1.0, "samples": 3}
    # An unconfigured probe records no circuit outcome: no signal at all.
    assert ratio["signal_rate"]["ai_universe"] == {"rate": None, "samples": 0}
    assert ratio["consecutive_failed_deliveries"] == 0
    assert ratio["channel_broken"] is False
    assert ratio["last_alert"]["subsystem"] == "ai_universe"
    assert run is not None and run.ratio_check["unconfigured_streaks"] == {"ai_universe": 3}


def test_ratio_check_does_not_suppress_later_failure_escalation():
    """The ratio alert and the failure escalation are independent streaks: a
    ratio alert that landed must not swallow a later genuine failure page
    for the same subsystem (the two paths do not share streak state)."""
    registry = HealthRegistry()
    state = {"probe": ProbeResult.UNCONFIGURED}

    async def probe():
        return state["probe"]

    async def repair() -> bool:
        return False  # cannot fix it

    registry.register_probe("ai_universe", probe)
    notifier = _RecordingNotifier()
    supervisor = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        max_repairs_per_subsystem=1,
        notifier=notifier,
        unconfigured_streak_threshold=2,
    )
    supervisor.register_repair("ai_universe", repair)

    for _ in range(2):  # ratio alert lands
        _run(supervisor.run_cycle())
    assert len(notifier.calls) == 1

    state["probe"] = ProbeResult.UNHEALTHY  # configured now, but failing
    _run(supervisor.run_cycle())  # repair attempt 1
    failed = _run(supervisor.run_cycle())  # budget exhausted -> escalate, must deliver
    assert failed.escalated == ["ai_universe"]
    assert len(notifier.calls) == 2
    assert notifier.calls[-1]["reason"].startswith("1 repair attempts")


def test_ratio_check_default_thresholds():
    """Defaults are the design values: 10 cycles (5 min at the 30 s tick)
    for the unconfigured streak, 3 consecutive failed deliveries for the
    channel gap."""
    supervisor = SelfHealingSupervisor(HealthRegistry())
    assert supervisor.unconfigured_streak_threshold == 10
    assert supervisor.delivery_gap_threshold == 3


def test_ratio_check_disabled_thresholds_never_alert():
    """A threshold of 0 disables that alert: the streaks are still counted
    and exposed, but nothing is ever delivered for them."""
    registry = HealthRegistry()
    registry.register_probe("ai_universe", _unconfigured_probe())
    notifier = _RecordingNotifier()
    supervisor = SelfHealingSupervisor(
        registry,
        repair_cooldown_seconds=0.0,
        notifier=notifier,
        unconfigured_streak_threshold=0,
        delivery_gap_threshold=0,
    )
    for _ in range(5):
        run = _run(supervisor.run_cycle())
    assert run.ratio_check["unconfigured_streaks"] == {"ai_universe": 5}
    assert run.escalated == []
    assert len(notifier.calls) == 0
