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
    # agent-task dispatch boilerplate (live 2026-11-13): upstream context
    # notes and task instructions are work orders, not owner facts
    "upstream findings from the previous step",
    "use this as context for your work",
    "verify storage and create retrieval index",
    "store the research findings",
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


# Agent experience records — FRIDAY's own failure/success learnings, written
# by MemoraClient._learn_locally and Memora's ExperienceService. They are
# operational notes FOR the agent, never facts the owner told FRIDAY, so a
# recall answer must never list one as something it "remembers" about the
# owner. TASK-REL-027 (2026-11-14, REL-022 residual (b)): live gate replies
# listed "[FAILURE WARNING ...]" records under the confident header "Here's
# what I'm holding onto" when nothing genuine matched the question.
_EXPERIENCE_MARKERS = (
    "[failure warning",
    "[proven success pattern",
    "[learned best practice]",
)


def is_experience_record(text: str) -> bool:
    """True when a stored line is an agent experience/learning record
    (failure warnings, proven-pattern notes), identified by the bracketed
    headers both writers stamp on the content."""
    if not text:
        return False
    low = text.strip().lower()
    return any(marker in low for marker in _EXPERIENCE_MARKERS)


def is_experience_hit(hit: dict) -> bool:
    """True when a recall hit is an experience record — by its stored
    ``memory_type`` when the row carries one (local rows and Memora search
    rows both do), or by the content markers when it does not."""
    if not isinstance(hit, dict):
        return False
    if str(hit.get("memory_type") or "").strip().lower() == "experience":
        return True
    return is_experience_record(str(hit.get("content_text", "") or ""))


def is_unpresentable_recall_hit(hit: dict) -> bool:
    """True when a recall hit must never be presented to the owner as a
    stored fact: monitor/log noise (``is_memory_noise``) or an agent
    experience record (``is_experience_hit``). Presentation surfaces use
    this one predicate; retrieval, ranking and mutation targeting keep
    their own semantics and are deliberately NOT routed through it."""
    if not isinstance(hit, dict):
        return True
    if is_experience_hit(hit):
        return True
    return is_memory_noise(str(hit.get("content_text", "") or ""))
