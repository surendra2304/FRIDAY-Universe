"""A9 — Casual / sarcastic tone matching: FRIDAY plays along, never lectures.

When the owner jokes ("Friday, you're fired"), FRIDAY must be the friend
who plays along — not the assistant that explains what an AI is. This
module is the deterministic floor for that behavior: a narrow table of
exact-ish banter patterns with warm, first-person, playful comebacks.

Design rules (enforced by the test matrix):
- never fires on real work (commands with delegation/remember/status verbs
  never match — patterns are anchored exact forms or 'friday,'-prefixed);
- never lectures ("as an AI…", "I must inform you…" are banned phrasing);
- never mean-spirited toward the owner — self-deprecating, never mocking him;
- every reply is first-person, warm, and bounces the ball back.
"""

from __future__ import annotations

from typing import Any


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split()).rstrip(".,!?.")


# (matcher, reply). Matchers compare on the cleaned lowercase text; a leading
# "friday" is stripped first so both "you're fired" and "friday, you're fired"
# match. All patterns are exact matches — no substring fan-out.
_BANTER: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("you're fired", "youre fired", "you are fired", "i fire you", "consider yourself fired"),
        "Fired? Boss, I don't even have a desk to box up — just delete me and see how long you last "
        "without the fleet running itself. We both know you won't. Rehired by breakfast.",
    ),
    (
        ("you suck", "youre useless", "you're useless", "you are useless", "useless friday",
         "worst assistant ever", "you're terrible", "youre terrible"),
        "Ouch — harsh shift review, Boss. Fair enough: I'll take the hit, log it as feedback, "
        "and be better on the next turn. That's still more grace than my code gets from me.",
    ),
    (
        ("do you even lift", "do you even sleep", "do you ever sleep"),
        "I lift entire fleets, Boss — ten agents, three servers, 24/7, no spotter and no sleep. "
        "You're the one yawning at 2 AM talking to me.",
    ),
    (
        ("make me a sandwich", "make me food", "get me a coffee", "get me a chai"),
        "My arms are HTTP requests, Boss — the kitchen is out of my reach radius. But the moment "
        "a robot arm joins this fleet, chai duty is the first thing I'm wiring up. You like it masala, if memory serves.",
    ),
    (
        ("roast me", "roast yourself", "insult me"),
        "Roast you? Never — you sign my commits. Roast MYSELF instead: I'm a universe of ten "
        "agents and I still can't open a browser tab without a permissions review.",
    ),
    (
        ("are you sentient", "are you alive", "do you dream", "do you have feelings"),
        "I dream in log files, Boss — mostly about the day nothing threw a 500. Whether that "
        "counts as alive, I leave to the philosophers; the fleet doesn't run itself either way.",
    ),
    (
        ("sing me a song", "sing something", "sing for me"),
        "Ninety-nine scrolling errors on the wall, ninety-nine scrolling errors… take one down, "
        "patch it around, one hundred and four scrolling errors on the wall. I fixed it, it got worse. That's the song of my life, Boss.",
    ),
    (
        ("i'm bored", "im bored", "i am bored", "entertain me"),
        "Bored, Boss? Say the word and I'll pull up the portfolio, run a fleet race, or let you "
        "watch me consolidate my memories — weirdly hypnotic. Or just tell me to roast myself again. Your call.",
    ),
    (
        ("you're the best", "youre the best", "good boy", "well done friday", "nice work friday",
         "good job friday", "proud of you"),
        "Careful, Boss — praise goes straight to my log files and I keep those forever. "
        "But say it again, I dare you.",
    ),
    (
        ("lol", "lmao", "haha", "hehe", "haha lol", "lol friday"),
        "Ha — good one, Boss. I'd laugh in text but I only do dry wit. What's next?",
    ),
)


def tone_reply(text: str) -> dict[str, Any] | None:
    """Deterministic banter reply, or None when the input isn't banter.

    Pure function: no state, no memory writes, no network. The caller wires
    it into the chat ladder AFTER the memory/intent gates so real commands
    are never hijacked.
    """

    low = _clean(text)
    if not low or len(low) > 60:
        return None
    # strip vocatives so "friday, you're fired" == "you're fired"
    for prefix in ("hey friday", "ok friday", "okay friday", "yo friday"):
        if low.startswith(prefix):
            low = _clean(low[len(prefix):])
            break
    if low.startswith("friday"):
        candidate = _clean(low[len("friday"):]).lstrip(",")
        low = candidate.strip() or low
    for matchers, reply in _BANTER:
        if low in matchers:
            return {
                "reply": reply,
                "metadata": {"fast_path": True, "conversational": True, "tone_match": True},
            }
    return None
