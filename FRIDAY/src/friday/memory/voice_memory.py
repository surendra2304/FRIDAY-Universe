"""B11 — Voice-path memory: "remember X" said on the voice line is stored.

The voice line (Gemini Live session) forwards speech straight to the Live
model, which has no access to Memora — so "remember my chai preference"
spoken aloud used to be answered conversationally and then LOST. This
module gives the voice path the same deterministic memory handling the
chat console has, tuned for transcripts:

- ``remember …`` → stored via MemoraClient (same sanitization + importance
  scoring as chat), confirmed out loud;
- ``forget that`` / ``forget about X`` → the same honest soft-delete;
- corrections ("actually my number is…") → politely redirected: voice
  transcripts drop punctuation, and a half-heard correction must never
  overwrite a stored fact, so they are asked for once in chat/typed form.

``handle_voice_memory`` is fail-safe by contract: it returns None for
non-memory input and a spoken confirmation string for handled input, and
it NEVER raises — a store outage becomes an honest spoken "couldn't reach
my memory store", never a lost fact claimed as saved.
"""

from __future__ import annotations

from typing import Any

_REMEMBER_PREFIXES = (
    "remember this boss", "remember this:", "remember this", "remember that:",
    "remember that", "remember:", "remember", "note that", "don't forget that",
    "dont forget that", "don't forget", "dont forget", "keep in mind that",
    "keep in mind", "memorize this", "memorise this", "store this",
)
_FORGET_EXACT = ("forget that", "forget this", "forget it", "forget that now")
_FORGET_PREFIXES = ("forget about ", "forget ", "remove memory ", "delete memory ")
_CORRECTION_OPENERS = (
    "actually", "no wait", "correction", "i meant", "update my", "change my",
)


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _low(text: str) -> str:
    return _clean(text).lower().strip(".,!?").strip()


def extract_voice_memory_intent(text: str) -> dict[str, Any] | None:
    """Classify a voice transcript as a memory intent (pure function).

    Returns ``{"kind": "remember", "payload": str}`` / ``{"kind": "forget",
    "query": str}`` / ``{"kind": "correction"}`` or None when not memory.
    """

    low = _low(text)
    if not low or len(low) > 300:
        return None
    for pfx in _REMEMBER_PREFIXES:
        if low.startswith(pfx):
            payload = _clean(text)[len(pfx):].strip().lstrip(":, -–").strip()
            # bare "remember" (no payload) is conversational, not a store command
            if len(payload) < 3:
                return None
            return {"kind": "remember", "payload": payload}
    if low in _FORGET_EXACT:
        return {"kind": "forget", "query": _clean(text)}
    for pfx in _FORGET_PREFIXES:
        if low.startswith(pfx):
            query = _clean(text)[len(pfx):].strip()
            if len(query) < 3:
                return None
            return {"kind": "forget", "query": query}
    for opener in _CORRECTION_OPENERS:
        if low.startswith(opener) and any(k in low for k in (" my ", " number", " name")):
            return {"kind": "correction"}
    return None


def handle_voice_memory(text: str) -> str | None:
    """Handle one voice transcript's memory intent. Never raises.

    Returns the spoken confirmation when handled, None when the transcript
    is not a memory intent. Store failures are SPOKEN honestly — a fact is
    never claimed saved when it wasn't.
    """

    intent = extract_voice_memory_intent(text)
    if intent is None:
        return None
    try:
        from friday.memory.memora_client import memora_client
        from friday.memory.importance import score_importance

        if intent["kind"] == "remember":
            payload = intent["payload"]
            if len(payload) > 400:
                payload = payload[:397].rstrip() + "…"
            verdict = score_importance(payload)
            res = memora_client.record_fact(
                agent_name="friday",
                fact_text=payload,
                category="owner_fact",
                importance=verdict.score,
            ) or {}
            if str(res.get("status", "success")) == "error":
                return (
                    "I couldn't reach my memory store just now, Boss, so I have NOT saved that. "
                    "Say it again in a moment, or type it in the console and it's locked in."
                )
            tier_note = (
                " That one's pinned — it never fades."
                if verdict.is_pinned
                else (" I'll keep it, but small stuff like that fades after a while."
                      if verdict.is_trivial else "")
            )
            return f"Got it, Boss — locked in: {payload}.{tier_note}"
        if intent["kind"] == "forget":
            res = memora_client.forget_fact("friday", intent["query"]) or {}
            status = str(res.get("status", "error"))
            if status == "deleted":
                gone = str(res.get("content_text", "")).strip()
                return f"Done, Boss — I've forgotten {gone or 'it'}. Out of my active memory now."
            if status == "not_found":
                return "I checked, Boss, and I don't have a stored fact matching that — nothing to forget."
            return "I couldn't reach my memory store just now, so nothing was forgotten — say it again in a moment."
        # correction on the voice line: transcripts drop punctuation, and a
        # half-heard correction must never overwrite a stored fact.
        return (
            "I heard a correction, Boss — voice transcripts drop the punctuation, and I won't "
            "overwrite a stored fact on a half-heard line. Say it once in chat or typed here "
            "and I'll replace it exactly."
        )
    except Exception:
        return (
            "I couldn't reach my memory store just now, Boss, so nothing was saved — "
            "say it again in a moment."
        )
