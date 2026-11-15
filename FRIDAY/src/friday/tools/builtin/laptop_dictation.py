"""Voice dictation typing for the owner's laptop (TASK-IG-LAP-02).

Corpus item DdVlSrQhlng: "this dictation types anything into the PC".
The owner dictates to FRIDAY (voice or text); this tool types the result
into whatever app is focused on his laptop, through the EXISTING laptop
bridge ``type_text`` command — no new bridge command, no protocol
change, and the same SENSITIVE risk class as ``laptop_type_text`` (it
puts words into the owner's applications).

Two modes:

* ``dictation`` (default) — spoken punctuation is honoured: "new line",
  "new paragraph", "period"/"full stop", "comma", "question mark",
  "exclamation mark", "colon", "semicolon", "ellipsis", "open/close
  quote", "dash". Stray spaces before punctuation are removed and
  sentence starts are capitalised, the way every dictation product
  behaves.
* ``verbatim`` — the text is typed exactly as given (code, passwords
  read aloud character by character, literal commands).

Long dictations are chunked losslessly (joining the chunks reproduces
the prepared text byte-for-byte) so each bridge command stays small and
a mid-dictation failure can be reported with an honest typed-so-far
count instead of pretending the whole thing landed.
"""

from __future__ import annotations

import re
from typing import Any

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.builtin.laptop_control import _LaptopTool

logger = get_logger("tools.laptop_dictation")

CHUNK_CHARS = 600

# Longest phrases first so "new paragraph" wins over "new line" and
# "exclamation mark" over any shorter overlap. Word boundaries keep
# "period" inside "periodically" untouched.
_SPOKEN_TOKENS: tuple[tuple[str, str], ...] = (
    (r"new paragraph", "\n\n"),
    (r"new line", "\n"),
    (r"question mark", "?"),
    (r"exclamation mark", "!"),
    (r"exclamation point", "!"),
    (r"full stop", "."),
    (r"open quote", '"'),
    (r"close quote", '"'),
    (r"semicolon", ";"),
    (r"ellipsis", "..."),
    (r"period", "."),
    (r"comma", ","),
    (r"colon", ":"),
    (r"dash", "-"),
    (r"hyphen", "-"),
)

_TOKEN_PATTERNS = tuple(
    (re.compile(r"\b" + phrase + r"\b", re.IGNORECASE), replacement)
    for phrase, replacement in _SPOKEN_TOKENS
)


def prepare_dictation_text(text: str, mode: str = "dictation") -> str:
    """Turn a spoken transcript into text ready to type.

    ``verbatim`` returns the input untouched. ``dictation`` applies the
    spoken-token map plus light cleanup (space-before-punctuation,
    spacing around newlines, sentence capitalisation).
    """
    if mode == "verbatim":
        return text
    prepared = re.sub(r"[ \t]+", " ", text or "")
    for pattern, replacement in _TOKEN_PATTERNS:
        prepared = pattern.sub(replacement, prepared)
    # No space before punctuation: "hello , world ." -> "hello, world."
    prepared = re.sub(r" +([.,!?;:])", r"\1", prepared)
    # Multi-dot from "ellipsis" must not be re-spaced by the rule above.
    prepared = re.sub(r" *\n *", "\n", prepared)
    prepared = re.sub(r" {2,}", " ", prepared)
    prepared = _capitalise_sentences(prepared)
    return prepared.strip()


def _capitalise_sentences(text: str) -> str:
    chars = list(text)
    capitalise_next = True
    for index, char in enumerate(chars):
        if capitalise_next and char.isalpha():
            chars[index] = char.upper()
            capitalise_next = False
        elif char in ".!?\n":
            capitalise_next = True
    return "".join(chars)


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split ``text`` into chunks of at most ``size`` characters.

    Splits prefer a newline, then a space, keeping the separator at the
    end of the earlier chunk — so ``"".join(chunk_text(t)) == t`` always.
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    chunks: list[str] = []
    rest = text
    while len(rest) > size:
        window = rest[:size]
        cut = max(window.rfind("\n"), window.rfind(" "))
        cut = cut + 1 if cut >= size // 2 else size
        chunks.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        chunks.append(rest)
    return chunks


class LaptopDictateTool(_LaptopTool):
    """Type dictated text into the active app on the owner's laptop."""

    name = "laptop_dictate"
    description = (
        "Dictate into the owner's laptop: types text into whichever app is "
        "focused there, through the laptop bridge. In 'dictation' mode "
        "(default) spoken punctuation is honoured — say 'new line', "
        "'period', 'comma', 'question mark' etc. Use 'verbatim' mode to "
        "type text exactly as given. For a single short literal string, "
        "laptop_type_text is the simpler tool; use this one when the user "
        "is dictating a message, note or document."
    )
    safety_level = SafetyLevel.SENSITIVE
    command = "type_text"
    default_timeout = 90.0
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The dictated text (with spoken punctuation in dictation mode).",
            },
            "mode": {
                "type": "string",
                "enum": ["dictation", "verbatim"],
                "description": "dictation: honour spoken punctuation. verbatim: type exactly as given.",
            },
            "laptop_id": {
                "type": "string",
                "description": "Optional laptop id when more than one is connected.",
            },
        },
        "required": ["text"],
    }

    def execute(
        self,
        text: str = "",
        mode: str = "dictation",
        laptop_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        raw = text or ""
        if not raw.strip():
            return self._error("Nothing to dictate — the text was empty.")
        chosen_mode = mode if mode in ("dictation", "verbatim") else "dictation"
        prepared = prepare_dictation_text(raw, chosen_mode)
        if not prepared.strip():
            return self._error("Nothing to type after preparing the dictation.")
        chunks = chunk_text(prepared)
        typed = 0
        laptop_label = ""
        for chunk in chunks:
            evidence, error = self._dispatch({"text": chunk}, laptop_id or None)
            if error is not None:
                if typed:
                    return self._error(
                        f"Dictation stopped after {typed} of {len(chunks)} chunks "
                        f"({sum(len(c) for c in chunks[:typed])} of {len(prepared)} "
                        f"characters typed): {error.content}"
                    )
                return error
            if not evidence or not evidence.get("ok"):
                detail = (evidence or {}).get("error") or "unknown laptop-side error"
                return self._error(
                    f"The laptop failed chunk {typed + 1} of {len(chunks)}: {detail}"
                )
            laptop_label = str(evidence.get("laptop_id") or laptop_label)
            typed += 1
        return ToolResult(
            name=self.name,
            content=(
                f"Typed {len(prepared)} characters into the active app on laptop "
                f"'{laptop_label}' in {typed} chunk(s), {chosen_mode} mode."
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "laptop_id": laptop_label,
                "command": self.command,
                "chunks": typed,
                "characters": len(prepared),
                "mode": chosen_mode,
            },
        )
