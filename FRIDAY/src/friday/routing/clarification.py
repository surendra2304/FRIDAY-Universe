"""Checklist A10 (batch 3): clarification quality — ONE sharp question.

When a delegation intent is recognized but its required operand is missing
("research", "draft a video script", "save this to fleet memory" with nothing
after it), FRIDAY asks EXACTLY ONE sharp question — never a wall of
questions, never a guess, never silently proceeding with a junk operand.

The gate is deterministic and single-turn by design:
- it fires only when the intent keywords matched and the operand slot is
  empty or a bare pronoun ("it", "that", "this", "them") with no antecedent
  in the same message;
- it returns the question text, and the caller turns it into a normal
  conversational reply (memory + state machine included);
- one question per turn, phrased Boss-tone, offering the most likely shape
  of answer so the owner can reply in three words.
"""

from __future__ import annotations

import re

# Pronouns that LOOK like an operand but carry no content in a fresh turn.
_BARE_PRONOUNS = {"it", "that", "this", "them", "those", "these", "one"}

# Filler words that surround an operand but are not content themselves.
_FILLER_WORDS = {
    "a", "an", "the", "about", "on", "for", "of", "to", "me", "my", "please",
    "can", "you", "could", "would", "some", "into", "in", "up", "now", "and",
    "video", "youtube", "shorts", "clip",
}

# Intent-specific questions. ONE question each, shaped so a three-word answer
# resolves the ambiguity.
_QUESTIONS: dict[str, str] = {
    "research": "What topic should IntelX dig into, Boss? One line is enough — I'll take the brief from there.",
    "script": "What should the script cover, Boss? Give me the topic and I'll have VyralX draft it.",
    "memory_save": "What exactly should I remember, Boss? Say the fact and it goes into fleet memory.",
    "forecast": "What exactly should Futuris forecast, Boss — a market, a metric, or the fleet load, and over which horizon (1h / 24h / 7d / 30d)?",
}

# Leading verb shapes per intent (must match the fast paths' action shapes).
_INTENT_PATTERNS: dict[str, re.Pattern[str]] = {
    "research": re.compile(
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+|friday[, ]+)?"
        r"(?:do\s+some\s+research|research|investigate|look\s+into|dig\s+into|"
        r"find\s+out\s+about|brief\s+me\s+on)\b(.*)$",
        re.IGNORECASE,
    ),
    "script": re.compile(
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+|friday[, ]+)?"
        r"(?:draft|write|compose|make|create)\b.*?\bscript\b(?:\s+(?:about|on|for)\s+(?P<topic>.*))?$",
        re.IGNORECASE,
    ),
    "memory_save": re.compile(
        r"^(?:please\s+)?(?:save|store|remember)\s+(?:this|that|it)?\s*(?:to|in|into)\s+"
        r"(?:fleet\s+memory|cloud\s+memory|memora)\s*(?:[:,]\s*(?P<content>.*))?$",
        re.IGNORECASE,
    ),
    "forecast": re.compile(
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+|friday[, ]+)?"
        r"(?:forecast|predict)(?:\s+(?P<target>.*))?$",
        re.IGNORECASE,
    ),
}


def _operand_has_content(operand: str) -> bool:
    """True when the operand carries at least one real content word."""
    words = [w for w in re.split(r"[\s,:;]+", (operand or "").lower()) if w]
    if not words:
        return False
    if all(w in _BARE_PRONOUNS or w in _FILLER_WORDS for w in words):
        return False
    # Reject pronoun-led operands with nothing after ("save it to fleet memory")
    if words[0] in _BARE_PRONOUNS and len(words) <= 2:
        return False
    return True


def clarify_if_operand_missing(text: str, intent: str) -> str | None:
    """A10: return ONE sharp question when ``text`` matches ``intent`` but its
    operand is missing; None when the request is complete (proceed) or the
    intent doesn't match (not ours to ask about)."""
    if intent not in _INTENT_PATTERNS:
        return None
    low = (text or "").lower().strip().rstrip(".!? ")
    match = _INTENT_PATTERNS[intent].match(low)
    if match is None:
        return None
    if intent == "script":
        operand = (match.groupdict().get("topic") or "").strip()
    elif intent == "memory_save":
        operand = (match.groupdict().get("content") or "").strip()
    elif intent == "forecast":
        operand = (match.groupdict().get("target") or "").strip()
    else:  # research: everything after the action verb
        operand = (match.group(1) or "").strip()
        operand = re.sub(r"^(?:on|about|the)\s+", "", operand).strip()
        # "research and give me the highlights" — trailing ask, no topic
        operand = re.sub(
            r"\s*(?:and\s+)?(?:give|get)\s+me\s+the\s+highlights.*$", "", operand
        ).strip()
    if _operand_has_content(operand):
        return None
    return _QUESTIONS[intent]
