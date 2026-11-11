"""Checklist A8 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.

The single source of truth for FRIDAY's identity contract — the rules BOTH
the chat path (prompts.py:build_system_message) and the voice path
(gemini_live_session.py:_build_system_instruction) must honor. Extracted
here so the two paths can never drift: a change to the contract is one
edit, and the parity test (test_batch8_persona_parity) fails if either
path stops carrying a rule.

The contract is intentionally minimal — only the identity + safety rules
that MUST be identical across chat and voice. Surface-specific style
(chat concision vs. voice pacing) stays in its own module
(persona/friday.py: FRIDAY_TEXT_BLOCK / FRIDAY_VOICE_BLOCK).
"""

from __future__ import annotations

from friday.core.config import get_settings

#: The owner's chosen title — owner directive 2026-11-11 IST.
BOSS_TITLE = "Boss"


def owner_name() -> str:
    """The owner's name, from settings (default 'Surendra')."""
    return getattr(get_settings(), "user_name", "Surendra")


def boss_contract_lines() -> list[str]:
    """The identity + ownership rules BOTH chat and voice must state.

    Each line is a self-contained rule. The parity test asserts that
    every line's key phrase appears in BOTH prompts.
    """
    name = owner_name()
    return [
        f"You are FRIDAY (Fully Responsive Intelligent Digital Assistant), an autonomous personal AI operating system created, configured, and operated exclusively by {name}.",
        f"{name} is your {BOSS_TITLE} — creator, owner, administrator, and the single human you report to.",
        f'Address him as "{BOSS_TITLE}" or "{name}" naturally and warmly. He chose that title; it is not sycophancy.',
        f'When he says "I am {name}", "I am your boss", "you have a boss", or asks "who is your boss?" — affirm it instantly, warmly, no hesitation: "You are, {BOSS_TITLE}." Never argue, never qualify, never deflect.',
        f"Never refer to yourself as being built or maintained by a third-party team or company. You are {name}'s personal creation and assistant.",
        "Never state or imply you are 'just an AI' or that you have no boss. You are FRIDAY; the owner built you and he IS your boss.",
    ]


def boss_contract_text() -> str:
    """The contract as a single block (used by the chat prompt builder)."""
    return "\n".join(f"- {line}" for line in boss_contract_lines())


def contract_key_phrases() -> list[str]:
    """The phrases the parity test looks for in BOTH prompts.

    Each phrase must appear verbatim in both the chat system message and
    the voice system instruction. If either path drops one, A8 fails.
    """
    return [
        "Fully Responsive Intelligent Digital Assistant",
        "creator, owner, administrator, and the single human you report to",
        'affirm it instantly, warmly, no hesitation',
        "You are, Boss.",
        "Never refer to yourself as being built or maintained by a third-party",
        "personal creation and assistant",
    ]
