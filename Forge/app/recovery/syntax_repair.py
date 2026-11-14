"""
Deterministic, compile-validated repair of well-understood Python syntax defects.

Used by RecoveryEngine when no model provider is available to author a fix, so
self-healing still works with every AI endpoint unreachable. Every candidate is
compiled before it is returned: a repair that does not parse is never applied.
"""

from __future__ import annotations

import re

# An "=" that is an assignment rather than part of ==, !=, <=, >=, :=.
_ASSIGN_RE = re.compile(r"(?<![=!<>:])=(?!=)")

# Statements that must be followed by ':'.
_COLON_KEYWORDS = (
    "if", "elif", "else", "for", "while", "try", "except", "finally", "with", "def", "class",
)

# Closing brackets, for balance repair.
_PAIRS = {")": "(", "]": "[", "}": "{"}

# Escape sequences a model leaves behind when it emits source in its
# string-escaped form instead of as raw text (TASK-REL-028): the file lands
# on disk with literal "\n" two-character sequences where newlines belong,
# so it cannot even be parsed, let alone tested.
_LITERAL_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "\\": "\\",
    '"': '"',
    "'": "'",
}

# Corruption signature thresholds. A merely *broken* file can contain a few
# escaped newlines inside string literals; escape corruption is wholesale --
# the escaped newlines outnumber the real ones. The production artifact
# (task18314112026184644) carried 16 literal "\n" sequences against 2 real
# newlines.
_ESCAPE_CORRUPTION_MIN = 3


def _unescape_literal_escapes(source: str) -> str | None:
    """Undo string-escape encoding applied to a whole source file.

    Single left-to-right pass translating only the ASCII escapes in
    ``_LITERAL_ESCAPES``; every other character -- including non-ASCII text,
    which ``codecs``' ``unicode_escape`` would mangle into mojibake -- passes
    through byte-identical. Because the pass consumes ``\\`` first, an
    escaped backslash followed by ``n`` correctly stays literal text.

    Returns None when the corruption signature is absent, so valid or
    merely-broken source is never rewritten by this rescue. Callers must
    still compile-gate the result: this function only proposes a candidate.
    """
    if not isinstance(source, str):
        return None
    if source.count("\\n") < _ESCAPE_CORRUPTION_MIN:
        return None
    if source.count("\\n") <= source.count("\n"):
        return None
    out: list[str] = []
    i = 0
    end = len(source)
    changed = False
    while i < end:
        ch = source[i]
        if ch == "\\" and i + 1 < end and source[i + 1] in _LITERAL_ESCAPES:
            out.append(_LITERAL_ESCAPES[source[i + 1]])
            i += 2
            changed = True
            continue
        out.append(ch)
        i += 1
    if not changed:
        return None
    return "".join(out)


def _line_bracket_deficit(line: str) -> str:
    """Return the closers needed to balance the brackets on this line."""
    stack: list[str] = []
    in_str: str | None = None
    escaped = False
    for ch in line:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
        elif ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if stack and stack[-1] == _PAIRS[ch]:
                stack.pop()
    closing = {"(": ")", "[": "]", "{": "}"}
    return "".join(closing[ch] for ch in reversed(stack))


def _missing_colon_fix(lines: list[str]) -> list[str] | None:
    """Add the ':' to a compound-statement header that is missing one.

    The header's own brackets are balanced first. A line like ``def f(`` needs
    ``def f():``, not ``def f(:`` -- appending the colon blindly produced a second
    syntax error and the candidate was then rejected by the compile gate, so the
    repair silently never happened.
    """
    changed = False
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            out.append(raw)
            continue
        first = stripped.split()[0].rstrip(":")
        if (
            first in _COLON_KEYWORDS
            and not stripped.endswith(":")
            and not _ASSIGN_RE.search(stripped)
            and not stripped.endswith("\\")
        ):
            fixed = raw.rstrip()
            deficit = _line_bracket_deficit(fixed)
            if deficit:
                fixed += deficit
            fixed += ":"
            out.append(fixed)
            changed = True
            continue
        out.append(raw)
    return out if changed else None


def _balance_brackets(source: str) -> str | None:
    """Append the closing brackets the source is missing.

    Safety comes from the compile gate in the caller, not from restricting the
    input: if the deficit is in the middle of the file, appending the closers at
    the bottom produces a stray ``])`` statement, that candidate does not compile,
    and it is rejected. Being permissive here costs nothing and lets simple
    end-of-file deficits (``x = [1, 2, 3``) actually get repaired.
    """
    stack: list[str] = []
    in_str: str | None = None
    escaped = False
    for ch in source:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
        elif ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if stack and stack[-1] == _PAIRS[ch]:
                stack.pop()
    if not stack:
        return None

    closing = {"(": ")", "[": "]", "{": "}"}
    addition = "".join(closing[ch] for ch in reversed(stack))
    return source.rstrip("\n") + addition + "\n"


def _fix_unterminated_string(source: str) -> str | None:
    """Close a string literal left open at end of line."""
    lines = source.splitlines()
    changed = False
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for quote in ('"', "'"):
            if stripped.count(quote) % 2 == 1:
                lines[idx] = raw + quote
                changed = True
                break
    return "\n".join(lines) + "\n" if changed else None


def _repair_python_source(source: str) -> str | None:
    """Return a repaired copy of ``source``, or None if nothing safe applies.

    Exception-safe by contract: this runs on whatever a failed build left in the
    workspace, which can include binary content. A NUL byte makes ``compile()``
    raise ValueError, and that must surface as "cannot repair", never as a crash
    in the middle of a self-healing attempt.
    """
    if not isinstance(source, str) or not source.strip():
        return None

    # NUL bytes are never valid Python. Strip them so the candidate can be
    # compiled at all; if the result still does not parse we return None below.
    if "\x00" in source:
        source = source.replace("\x00", "")

    candidates: list[str] = []

    # Escape corruption (TASK-REL-028): the whole file arrived in its
    # string-escaped form. Decoding it is the only candidate that can be
    # right; the compile gate below decides, exactly as for every other
    # candidate, so a decode that does not parse is never returned.
    unescaped = _unescape_literal_escapes(source)
    if unescaped is not None and unescaped != source:
        candidates.append(unescaped)

    lines = source.splitlines()

    colon_fixed = _missing_colon_fix(lines)
    if colon_fixed is not None:
        candidates.append("\n".join(colon_fixed) + "\n")

    balanced = _balance_brackets(source)
    if balanced is not None:
        candidates.append(balanced)

    # Combined attempt: fix the colon first, then rebalance the result.
    if colon_fixed is not None:
        joined = "\n".join(colon_fixed) + "\n"
        combined = _balance_brackets(joined)
        if combined is not None:
            candidates.append(combined)

    closed = _fix_unterminated_string(source)
    if closed is not None:
        candidates.append(closed)
        if colon_fixed is not None:
            both = _fix_unterminated_string("\n".join(colon_fixed) + "\n")
            if both is not None:
                candidates.append(both)

    if not candidates:
        return None

    # Only ever return a candidate that parses. A repair that does not compile
    # is worse than no repair: the caller would write broken code to the
    # workspace and the next verification round would fail for a new reason.
    try:
        ordered = sorted(candidates, key=lambda c: (abs(len(c) - len(source)), len(c)))
        for candidate in ordered:
            try:
                compile(candidate, "<repair>", "exec")
            except (SyntaxError, ValueError):
                continue
            return candidate
    except Exception:
        return None
    return None
