"""A14 — Boss-only command surface: owner-exclusive commands keyed to identity.

Some commands must answer to the owner and nobody else: mode switches
(autonomous/full-access), agent shutdown/restart, trading toggles, memory
wipes and fleet-level deployment actions. ``is_boss_only`` recognizes them
deterministically; execution additionally requires a VERIFIED owner
identity:

- the command console (origin-gated + control-token) counts as verified —
  the token IS the owner key there;
- the voice line counts as verified only while speaker biometrics are
  passing (enrolled owner voice) or after the owner authorized the session
  with the boss passphrase;
- any other surface must authorize first: "authorize boss <passphrase>"
  (``BOSS_PASSPHRASE`` env — unset means non-console surfaces are never
  verified, which fails CLOSED).

Refusals are honest: they name the command class, confirm nothing was
executed, and state how to verify. Sessions stay verified for
``VERIFY_TTL_SECONDS`` then re-lock.
"""

from __future__ import annotations

import os
import time
from typing import Any

VERIFY_TTL_SECONDS = 3600

# (category, description, matchers). Matchers are lowercased substrings with
# word-boundary care — kept narrow so ordinary chat never trips the gate.
_BOSS_ONLY: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "mode_switch",
        "autonomous / full-access mode switches",
        (
            "activate autonomous mode", "enable autonomous mode", "turn on autonomous mode",
            "autonomous mode on", "autonomous on", "start autonomous mode", "run autonomously",
            "deactivate autonomous mode", "disable autonomous mode", "turn off autonomous mode",
            "autonomous mode off", "autonomous off", "stop autonomous mode",
            "full access mode", "full-access mode",
        ),
    ),
    (
        "agent_shutdown",
        "agent shutdown / restart",
        (
            "shutdown agent", "shut down agent", "restart agent", "stop agent",
            "kill agent", "shutdown the agent", "shut down the agent", "reboot agent",
        ),
    ),
    (
        "trading_toggle",
        "live-trading enable/disable",
        (
            "enable live trading", "disable live trading", "start live trading",
            "stop live trading", "turn on live trading", "turn off live trading",
            "go live", "switch to live", "live mode on", "live mode off",
        ),
    ),
    (
        "memory_wipe",
        "whole-memory wipe / reset",
        (
            "forget everything", "forget all memories", "wipe your memory", "wipe my memory",
            "wipe memory", "reset your memory", "erase everything you remember",
            "clear all memories", "factory reset",
        ),
    ),
    (
        "fleet_control",
        "fleet-wide deploy / rollback / shutdown",
        (
            "deploy the fleet", "deploy fleet", "rollback the fleet", "rollback deployment",
            "restart the fleet", "shutdown the fleet", "shut down the fleet",
            "shutdown everything", "shut down everything", "restart everything",
            "stop the universe", "shutdown the universe",
        ),
    ),
)

_AUTHORIZE_PHRASES = ("authorize boss", "boss authorize", "authorise boss")


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def is_boss_only(command: str) -> str | None:
    """Category of the boss-only command matched, else None (pure function)."""

    low = _clean(command)
    if not low:
        return None
    for category, _desc, matchers in _BOSS_ONLY:
        for m in matchers:
            if m in low:
                return category
    return None


def boss_only_description(category: str) -> str:
    for cat, desc, _m in _BOSS_ONLY:
        if cat == category:
            return desc
    return "a boss-only action"


def extract_authorize_passphrase(command: str) -> str | None:
    """The passphrase from 'authorize boss <passphrase>' style input, else None."""

    low = _clean(command)
    for phrase in _AUTHORIZE_PHRASES:
        if low.startswith(phrase):
            rest = _clean(command)[len(phrase):].strip()
            return rest or None
    return None


# --- session verification registry --------------------------------------------

_verified_until: dict[str, float] = {}


def _reset_for_tests() -> None:
    _verified_until.clear()


def mark_verified(source: str, ttl_seconds: int = VERIFY_TTL_SECONDS, now_epoch: float | None = None) -> None:
    now_epoch = now_epoch if now_epoch is not None else time.time()
    _verified_until[source] = now_epoch + ttl_seconds


def is_verified(source: str, now_epoch: float | None = None) -> bool:
    now_epoch = now_epoch if now_epoch is not None else time.time()
    until = _verified_until.get(source, 0.0)
    return until > now_epoch


def verify_passphrase(candidate: str) -> bool:
    """Fail-closed passphrase check (BOSS_PASSPHRASE env; unset = never passes)."""

    expected = (os.getenv("BOSS_PASSPHRASE") or "").strip()
    if not expected:
        return False
    return _clean(candidate) == _clean(expected)


def refusal_reply(command: str, category: str) -> dict[str, Any]:
    """The honest boss-gate refusal: what was blocked, why, and how to verify."""

    desc = boss_only_description(category)
    return {
        "reply": (
            f"Hold on — that's a boss-only action ({desc}), and I can't confirm it's you on this line, Boss. "
            "Nothing was executed. Verify once and I'll run it right away: say "
            "'authorize boss <passphrase>' on this line, or send it from the command console."
        ),
        "metadata": {
            "fast_path": True,
            "boss_gate": True,
            "boss_only_category": category,
            "executed": False,
            "command": command,
        },
    }


def handle_authorize(command: str, source: str) -> dict[str, Any] | None:
    """Handle an 'authorize boss <passphrase>' request; None when not one."""

    passphrase = extract_authorize_passphrase(command)
    if passphrase is None:
        return None
    if verify_passphrase(passphrase):
        mark_verified(source)
        return {
            "reply": (
                "Verified, Boss — this line is unlocked for boss-only commands for the next hour. "
                "Say the word and it's done."
            ),
            "metadata": {"fast_path": True, "conversational": True, "boss_authorize": True, "verified": True},
        }
    return {
        "reply": (
            "That passphrase doesn't match, Boss — this line stays locked for boss-only commands. "
            "(If you never set one, BOSS_PASSPHRASE is unset: use the command console for those.)"
        ),
        "metadata": {"fast_path": True, "conversational": True, "boss_authorize": True, "verified": False},
    }
