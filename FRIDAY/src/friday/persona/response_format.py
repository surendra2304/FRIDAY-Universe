"""Checklist A13 (batch 3): response formatting policy.

The owner's chat answers follow ONE consistent shape: short paragraphs,
bulleted enumerations, no walls of text. Free-form LLM replies don't always
respect that, so this module is a deterministic, idempotent post-processor
applied to conversational replies before they reach the owner:

- collapse 3+ consecutive blank lines into one blank line;
- split any paragraph longer than ``MAX_PARAGRAPH_SENTENCES`` into
  paragraphs of at most ``SENTENCES_PER_PARAGRAPH`` sentences;
- reflow run-on inline enumerations ("1) x 2) y 3) z", "1. x 2. y",
  "a) x b) y") into bulleted lines, one item per line;
- strip trailing whitespace per line; at most one trailing newline.

Deliberately NOT done (would damage real content):
- no emoji injection or removal (tools already use consistent markers);
- no truncation of long technical reports (fast-path replies are exempt
  anyway — this policy targets free-form conversational answers);
- no re-wrapping of lines the owner's tools formatted intentionally
  (bullets, numbered lists, code blocks are left alone).
"""

from __future__ import annotations

import re

MAX_PARAGRAPH_SENTENCES = 6
SENTENCES_PER_PARAGRAPH = 3

# Already-structured lines we must not touch.
_STRUCTURED_PREFIX = re.compile(r"^\s*(?:[-*•>]|\d+[.)]|[a-zA-Z][.)]|#{1,6}\s|\|)")

# Run-on inline enumerations: two or more "N) item" / "N. item" markers in a
# single paragraph line. Word-boundary-safe: "3.5" is not a list marker.
_INLINE_ENUM_RE = re.compile(
    r"(?:(?<![\w.])\d+[.)]\s+[^()\n]*?){2,}"
)
_ENUM_MARKER_RE = re.compile(r"(?<![\w.])(\d+)[.)]\s+")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def _split_walls(paragraph: str) -> list[str]:
    """Break a wall-of-text paragraph into <= SENTENCES_PER_PARAGRAPH chunks."""
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(paragraph.strip()) if s.strip()]
    if len(sentences) <= MAX_PARAGRAPH_SENTENCES:
        return [paragraph] if paragraph.strip() else []
    chunks: list[str] = []
    for i in range(0, len(sentences), SENTENCES_PER_PARAGRAPH):
        chunk = " ".join(s.strip() for s in sentences[i:i + SENTENCES_PER_PARAGRAPH])
        if chunk:
            chunks.append(chunk)
    return chunks


def _reflow_inline_enumerations(line: str) -> str:
    """Turn "intro: 1) a 2) b 3) c" inside one line into bullet lines.

    Only fires when the first marker follows a short lead-in (empty, or a
    colon/dash-ended phrase) — markers deep inside prose sentences are left
    alone.
    """
    if _STRUCTURED_PREFIX.match(line):
        return line  # already a list item / heading / table row
    first = _ENUM_MARKER_RE.search(line)
    if first is None:
        return line
    lead = line[: first.start()].rstrip()
    if lead and not lead.endswith((":", "-")) and len(lead) > 80:
        return line  # markers mid-sentence in prose — not an enumeration
    parts = _ENUM_MARKER_RE.split(line)
    # split() with a capturing group yields [lead, num, text, num, text, ...]
    if len(parts) < 5:
        return line
    items: list[str] = []
    for i in range(1, len(parts) - 1, 2):
        item = parts[i + 1].strip()
        if item:
            items.append(f"{int(parts[i])}. {item}")
    if not items:
        return line
    head = f"{lead}\n" if lead else ""
    return head + "\n".join(items)


def apply_response_formatting(text: str) -> str:
    """Apply the A13 formatting policy. Idempotent; never returns None."""
    if not text or not text.strip():
        return text

    lines = text.replace("\r\n", "\n").split("\n")
    out_lines: list[str] = []
    in_code_block = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = " ".join(p.strip() for p in paragraph if p.strip())
        paragraph.clear()
        if not joined:
            return
        chunks = _split_walls(joined)
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                out_lines.append("")  # blank line between split chunks only
            for piece in chunk.split("\n"):
                out_lines.append(_reflow_inline_enumerations(piece))

    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            in_code_block = not in_code_block
            out_lines.append(raw.rstrip())
            continue
        if in_code_block:
            out_lines.append(raw.rstrip())
            continue
        if not stripped:
            flush_paragraph()
            if out_lines and out_lines[-1] != "":
                out_lines.append("")
            continue
        if _STRUCTURED_PREFIX.match(raw):
            flush_paragraph()
            out_lines.append(_reflow_inline_enumerations(raw.rstrip()))
            continue
        paragraph.append(stripped)
    flush_paragraph()

    # Collapse 3+ blank lines -> 1 blank line; strip per-line trailing space.
    formatted: list[str] = []
    blanks = 0
    for ln in out_lines:
        if ln == "":
            blanks += 1
            if blanks > 1:
                continue
        else:
            blanks = 0
        formatted.append(ln)
    while formatted and formatted[-1] == "":
        formatted.pop()
    result = "\n".join(formatted)
    return result if text.endswith("\n") else result
