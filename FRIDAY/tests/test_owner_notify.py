"""TASK-FRD-025: the severity-gated owner Telegram path (owner_notify).

The gate's contract, proven with a fake clock + recording sender:
an ALERT sends; a ROUTINE never does; the same event cannot re-alert
inside its cooldown; identical words cannot re-alert inside the dedupe
window; two distinct alerts cannot burst back-to-back; the daily cap
holds and resets on the owner's day; the kill switch silences
everything; an unconfigured gateway and a failing sender are reported
honestly and never latch state; the state survives a restart (a new
instance over the same file still honours the cooldown).
"""

from __future__ import annotations

import pytest

from friday.proactive import owner_notify
from friday.proactive.owner_notify import (
    NotifyResult,
    OwnerNotifier,
    Severity,
)


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingSender:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.sent: list[str] = []

    def __call__(self, text: str) -> bool:
        self.sent.append(text)
        return self.result


def make_notifier(tmp_path, sender=None, clock=None, **overrides):
    params = dict(
        per_key_cooldown_seconds=6 * 3600.0,
        text_dedupe_seconds=3600.0,
        global_floor_seconds=120.0,
        daily_cap=20,
    )
    params.update(overrides)
    return OwnerNotifier(
        sender=sender if sender is not None else RecordingSender(),
        state_path=str(tmp_path / "state.json"),
        clock=clock if clock is not None else FakeClock(),
        **params,
    )


def test_alert_sends_and_routine_stays_below_the_bar(tmp_path):
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender)

    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.SENT
    assert sender.sent == ["Stratex is down"]

    assert (
        notifier.notify("daily trivia", severity=Severity.ROUTINE, event_key="trivia")
        is NotifyResult.BELOW_BAR
    )
    assert sender.sent == ["Stratex is down"]  # unchanged: routine never sends


def test_same_event_key_cannot_realert_inside_cooldown(tmp_path):
    clock = FakeClock()
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender, clock=clock)

    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.SENT
    clock.advance(3600)  # an hour later, still inside the 6h key cooldown
    assert (
        notifier.notify("Stratex is STILL down", event_key="fleet_down:stratex")
        is NotifyResult.COOLDOWN
    )
    assert len(sender.sent) == 1

    clock.advance(6 * 3600)  # past the cooldown: a still-down agent may re-alert
    assert (
        notifier.notify("Stratex is STILL down", event_key="fleet_down:stratex")
        is NotifyResult.SENT
    )
    assert len(sender.sent) == 2


def test_identical_text_cannot_realert_under_a_different_key(tmp_path):
    clock = FakeClock()
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender, clock=clock)

    assert notifier.notify("Fleet alert", event_key="a") is NotifyResult.SENT
    clock.advance(600)  # past the global floor, inside the 1h dedupe window
    assert notifier.notify("Fleet alert", event_key="b") is NotifyResult.DUPLICATE
    assert len(sender.sent) == 1

    clock.advance(3600)  # past dedupe too
    assert notifier.notify("Fleet alert", event_key="b") is NotifyResult.SENT


def test_global_floor_blocks_back_to_back_bursts(tmp_path):
    clock = FakeClock()
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender, clock=clock)

    assert notifier.notify("one", event_key="one") is NotifyResult.SENT
    assert notifier.notify("two", event_key="two") is NotifyResult.COOLDOWN
    clock.advance(121)
    assert notifier.notify("two", event_key="two") is NotifyResult.SENT
    assert sender.sent == ["one", "two"]


def test_daily_cap_holds_and_resets_on_the_owners_day(tmp_path, monkeypatch):
    clock = FakeClock()
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender, clock=clock, daily_cap=3)

    for i in range(3):
        assert notifier.notify(f"alert {i}", event_key=f"k{i}") is NotifyResult.SENT
        clock.advance(300)
    assert notifier.notify("alert 3", event_key="k3") is NotifyResult.DAILY_CAP
    assert len(sender.sent) == 3

    monkeypatch.setattr(owner_notify, "owner_today", lambda: "2999-01-01")
    assert notifier.notify("alert 3", event_key="k3") is NotifyResult.SENT


def test_kill_switch_silences_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_OWNER_NOTIFY", "off")
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender)

    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.DISABLED
    assert sender.sent == []
    # The module-level entry point honours the same switch.
    assert owner_notify.notify_owner("anything") is NotifyResult.DISABLED


def test_unconfigured_gateway_is_reported_not_faked(tmp_path):
    sender = RecordingSender()
    notifier = OwnerNotifier(
        sender=sender,
        configured=lambda: False,
        state_path=str(tmp_path / "state.json"),
        clock=FakeClock(),
    )
    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.NOT_CONFIGURED
    assert sender.sent == []


def test_failed_send_does_not_latch_state(tmp_path):
    clock = FakeClock()
    sender = RecordingSender(result=False)
    notifier = make_notifier(tmp_path, sender=sender, clock=clock)

    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.FAILED
    sender.result = True
    # Same instant, same key, same words: the failure latched nothing,
    # so the genuine retry goes straight through.
    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.SENT


def test_raising_sender_is_a_failed_result_never_an_exception(tmp_path):
    def boom(_text: str) -> bool:
        raise RuntimeError("network gone")

    notifier = make_notifier(tmp_path, sender=boom)
    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.FAILED


def test_state_survives_a_restart(tmp_path):
    clock = FakeClock()
    path = str(tmp_path / "state.json")
    first = OwnerNotifier(
        sender=RecordingSender(), state_path=path, clock=clock,
        per_key_cooldown_seconds=6 * 3600.0, text_dedupe_seconds=3600.0,
        global_floor_seconds=120.0, daily_cap=20,
    )
    assert first.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.SENT

    clock.advance(600)
    second = OwnerNotifier(
        sender=RecordingSender(), state_path=path, clock=clock,
        per_key_cooldown_seconds=6 * 3600.0, text_dedupe_seconds=3600.0,
        global_floor_seconds=120.0, daily_cap=20,
    )
    assert (
        second.notify("Stratex is STILL down", event_key="fleet_down:stratex")
        is NotifyResult.COOLDOWN
    )


def test_blank_text_is_never_sent(tmp_path):
    sender = RecordingSender()
    notifier = make_notifier(tmp_path, sender=sender)
    assert notifier.notify("   ", event_key="blank") is NotifyResult.FAILED
    assert sender.sent == []


def test_default_path_uses_the_gateway_configuration_check(tmp_path, monkeypatch):
    # No injected sender: the notifier must consult the real gateway's
    # configuration and report NOT_CONFIGURED instead of pretending.
    monkeypatch.setattr(owner_notify, "_gateway_configured", lambda: False)
    called: list[str] = []
    monkeypatch.setattr(owner_notify, "_gateway_sender", lambda text: called.append(text) or True)
    notifier = OwnerNotifier(state_path=str(tmp_path / "state.json"), clock=FakeClock())
    assert notifier.notify("Stratex is down", event_key="fleet_down:stratex") is NotifyResult.NOT_CONFIGURED
    assert called == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
