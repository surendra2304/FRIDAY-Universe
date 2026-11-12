"""Memory hygiene — keep telemetry spam and log dumps out of what FRIDAY
"remembers".

Why this exists (2026-11-13, ZAI Agent 2, measured live): the owner asked
"do you remember me?" and got back memories like:

    User: Access my screen | Assistant: I noticed the following while you
    were away: - Something you should know: RAM usage is at 9…

That is not memory of the owner — it is monitor-alert spam that was glued
into old answers and then recorded into Memora verbatim. Recalled memories
must be memories. Every recall surface (chat fast-path, greeting recall,
voice worker context injection) filters through :func:`is_memory_noise`.
"""

from __future__ import annotations

import re

# Proactive monitor phrasing — the alert storm classes.
_NOISE_PREFIXES = (
    "cpu is running hot",
    "cpu has cooled",
    "ram usage is at",
    "battery is at",
    "disk is ",
    "i noticed that ",
    "i noticed the following while you were away",
    "while you were not looking",
    "while you were away",
    "quick heads-up",
    "before you ask",
    "if i may interject",
    "worth noting",
    "just keeping you in the loop",
    "something you should know",
)

# Agent-log / transport artifacts that read as memory to no one.
_LOG_MARKERS = (
    " executed ",
    "[agent task",
    "bundle id",
    "http 200",
    "emora response",
    "workspace task reference",
    "carry out this owner-approved",
)

# A stored "dialogue dump" line: "User: X | Assistant: Y" transcripts are
# conversation history, not owner facts.
_DIALOGUE_DUMP = re.compile(r"^\s*user\s*:", re.IGNORECASE)


def is_memory_noise(text: str) -> bool:
    """True when a stored line is monitor noise or a log artifact, and must
    never be presented as a remembered fact about the owner."""
    if not text:
        return True
    low = text.strip().lower()
    if _DIALOGUE_DUMP.match(low):
        return True
    for prefix in _NOISE_PREFIXES:
        if low.startswith(prefix):
            return True
    for marker in _LOG_MARKERS:
        if marker in low:
            return True
    # The proactive openers also appear mid-line when glued after a greeting.
    if "| assistant:" in low and "user:" in low:
        return True
    return False
