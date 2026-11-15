"""TASK-IG-VOI-02 — hands-free dictation mode for FRIDAY voice.

Source ideas: reels DfM_GI2EkTH (Infina: speak the whole prompt, it
types for you, say "send") and DfOVzvvBxVs (Wispr Flow try-out) —
counted once in the corpus roll-up. The capability: the owner talks,
FRIDAY types his words into the active app on his laptop, and a
spoken "send" sends the message. Fully hands-free text entry into
other apps.

Architecture fit (why it looks like this): the voice worker has
exactly one tool — ``execute_friday_task`` into the canonical FRIDAY
brain — and the brain already owns the deployed laptop path
(TASK-LAP-001: ``laptop_type_text`` and friends, protocol-proven
end-to-end). Dictation is therefore a *protocol* over that tool, not
a new execution path:

- This module is the deterministic core: the control-phrase tables
  (start / stop / send / new line / new paragraph / scratch that),
  the session state machine, and the canonical relay phrasings the
  brain receives. ``plan()`` turns a transcript stream into relays,
  which pins the contract mechanically and gives a future
  worker-side interceptor (post-TASK-VOI-010) an exact target.
- ``instruction_section()`` is the model-facing contract, appended
  to the worker instructions by the optional-sections aggregator
  (TASK-IG-VOI-01, PR #448). Until that aggregator is on main this
  module is inert; the two PRs compose in either merge order.
- Every brain-bound relay begins with the ``Dictation:`` prefix —
  the structured-protocol marker the confirmation gate
  (TASK-IG-VOI-01) deliberately passes: dictation relays carry the
  owner's own words into his own apps, and dictation "send" is
  itself an explicit spoken control word, so re-gating each relayed
  sentence would make the mode unusable.

Control-phrase safety: a control phrase matches only when it is the
WHOLE utterance (after case/punctuation normalisation). A dictated
sentence that merely contains a command — "send the report to Priya
tomorrow" — is typed as content, never executed as a control. That
asymmetry is the mode's core safety property and is pinned by tests.

Honest limits: relays are per-utterance (Gemini Live's final
transcripts), so mid-sentence corrections ride the brain's typing,
and "scratch that" can only erase chunks dictated in this session —
it cannot unsend a sent message (after SEND the chunk log clears).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

RELAY_PREFIX = "Dictation:"

START_PHRASES = frozenset({
    "start dictation", "begin dictation", "start dictating",
    "dictation mode", "dictation on",
})
STOP_PHRASES = frozenset({
    "stop dictation", "end dictation", "stop dictating",
    "dictation off", "exit dictation",
})
SEND_PHRASES = frozenset({
    "send", "send it", "send now", "send message", "send the message",
})
NEW_LINE_PHRASES = frozenset({"new line", "newline", "line break"})
NEW_PARAGRAPH_PHRASES = frozenset({
    "new paragraph", "next paragraph", "paragraph break",
})
SCRATCH_PHRASES = frozenset({
    "scratch that", "delete that", "undo that", "remove that",
})

_FILLER = re.compile(r"^(please|friday|ok|okay)\s+|\s+(please)$")
_PUNCT = re.compile(r"[.!?,;:]+")


def normalize_control(text: str) -> str:
    """Normalise an utterance for whole-phrase control matching."""
    out = _PUNCT.sub(" ", (text or "").lower())
    out = " ".join(out.split())
    out = _FILLER.sub("", out).strip()
    return out


@dataclass(frozen=True)
class Relay:
    """One planned step. ``brain_request`` is the exact string for
    execute_friday_task ("" for pure mode transitions, which are
    conversational and never reach the brain)."""

    kind: str  # start | stop | type | send | newline | paragraph | scratch
    brain_request: str = ""


def type_relay(chunk: str) -> str:
    return (
        f"{RELAY_PREFIX} type the following text into the active app "
        f"on my laptop, exactly as written, with no additions: {chunk}"
    )


def send_relay() -> str:
    return (
        f"{RELAY_PREFIX} in the active app on my laptop, send the "
        "message I just dictated (press Enter or use the app's send "
        "control)."
    )


def newline_relay() -> str:
    return (
        f"{RELAY_PREFIX} type a line break in the active app on my "
        "laptop (press Enter once). This is a line break inside the "
        "message, NOT a send."
    )


def paragraph_relay() -> str:
    return (
        f"{RELAY_PREFIX} type a paragraph break (two line breaks) in "
        "the active app on my laptop. This is inside the message, "
        "NOT a send."
    )


def scratch_relay(chunk: str) -> str:
    n = len(chunk)
    return (
        f"{RELAY_PREFIX} delete the last {n} characters I dictated "
        f"in the active app on my laptop (press Backspace {n} "
        f"times). The text to remove is: {chunk}"
    )


@dataclass
class DictationSession:
    """Stateful planner: feed final transcripts, get relays back."""

    active: bool = False
    chunks: list = field(default_factory=list)

    def handle(self, transcript: str) -> "Relay | None":
        text = (transcript or "").strip()
        if not text:
            return None
        control = normalize_control(text)

        if not self.active:
            if control in START_PHRASES:
                self.active = True
                self.chunks = []
                return Relay("start")
            return None

        if control in STOP_PHRASES:
            self.active = False
            self.chunks = []
            return Relay("stop")
        if control in SEND_PHRASES:
            self.chunks = []  # a sent message cannot be scratched back
            return Relay("send", send_relay())
        if control in NEW_LINE_PHRASES:
            return Relay("newline", newline_relay())
        if control in NEW_PARAGRAPH_PHRASES:
            return Relay("paragraph", paragraph_relay())
        if control in SCRATCH_PHRASES:
            if not self.chunks:
                return None
            chunk = self.chunks.pop()
            return Relay("scratch", scratch_relay(chunk))

        # Anything else while active is content: type it verbatim.
        self.chunks.append(text)
        return Relay("type", type_relay(text))


def plan(transcripts) -> list:
    """Plan a whole transcript stream (contract tests, future
    worker-side interception). Returns the relays in order."""
    session = DictationSession()
    relays = []
    for transcript in transcripts:
        relay = session.handle(transcript)
        if relay is not None:
            relays.append(relay)
    return relays


def instruction_section() -> str:
    """The model-facing contract, appended to the worker instructions
    by the optional-sections aggregator (TASK-IG-VOI-01)."""
    return (
        "DICTATION MODE: when the user says 'start dictation', "
        "confirm in a few words and enter dictation mode. In "
        "dictation mode do not converse, answer questions or add "
        "anything of your own: for everything the user says, call "
        "execute_friday_task with a request starting 'Dictation:' "
        "that types his words verbatim into the active app on his "
        "laptop — type: 'Dictation: type the following text into "
        "the active app on my laptop, exactly as written, with no "
        "additions: <his words>'. If he says just 'send', relay "
        "'Dictation: in the active app on my laptop, send the "
        "message I just dictated'. 'New line' is a line-break relay, "
        "never a send. 'Scratch that' relays a deletion of the last "
        "chunk. A sentence that merely contains a command (for "
        "example 'send the report to Priya tomorrow') is content to "
        "type, not a command. When he says 'stop dictation', confirm "
        "briefly and resume normal conversation."
    )
