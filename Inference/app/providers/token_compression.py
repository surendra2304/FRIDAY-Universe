"""Rule-based token compression of outbound prompts (TASK-IG2-INF-04).

Pattern cherry-picked from OmniRoute (see ~/workspace/ig-references/repos/
omniroute.md): squeeze free-tier quotas by shrinking the prompt *before* it
hits a metered model. OmniRoute's headline savings (15–95%) are its own
claim and are **not** repeated here as a promise — this module measures its
own savings per request and exposes them via :func:`compression_stats`.

Design rules
------------
* **Rule-based only.** No extra LLM call is made to compress (that would
  spend the quota being saved). Everything here is deterministic text
  processing on the gateway path.
* **Conservative.** Only three things are removed:
  1. redundant whitespace (trailing spaces, 3+ blank lines, space/tab runs
     outside code fences, zero-width characters);
  2. verbatim-duplicated *blocks* (paragraphs of at least
     ``MIN_DEDUPE_BLOCK_CHARS`` chars that already appeared earlier in the
     same request) — replaced by a short omission marker, first occurrence
     always kept intact;
  3. verbatim-duplicated whole messages (same role + content).
* **Code is never touched.** Fenced code blocks (``` ... ```) pass through
  byte-for-byte.
* **Short prompts bypass.** Requests estimated below
  ``INFERENCE_COMPRESSION_MIN_TOKENS`` (default 800) tokens are returned
  unchanged — the overhead and risk are not worth it for small prompts.
* **Kill switch.** ``INFERENCE_TOKEN_COMPRESSION_ENABLED=false`` disables
  the whole stage. Default is on: every rule above only removes redundancy.

The gateway (:class:`app.providers.gateway.ModelGateway`) applies
:func:`compress_provider_request` once per request, before the primary
attempt, so every rung of the fallback ladder sends the compressed prompt.
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any

ENABLED = os.environ.get("INFERENCE_TOKEN_COMPRESSION_ENABLED", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
MIN_TOKENS = max(0, int(os.environ.get("INFERENCE_COMPRESSION_MIN_TOKENS", "800")))
MIN_DEDUPE_BLOCK_CHARS = max(40, int(os.environ.get("INFERENCE_COMPRESSION_DEDUPE_MIN_CHARS", "120")))

_OMISSION_MARKER = "[… repeated context omitted by token compression …]"
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿"), None)  # U+200B U+200C U+200D U+FEFF
_BLANK_RUN = re.compile(r"\n{3,}")
_SPACE_RUN = re.compile(r"[ \t]{2,}")
_TRAILING_WS = re.compile(r"[ \t]+(?=\n|$)")
_FENCE = re.compile(r"(```.*?```)", re.DOTALL)


@dataclass
class CompressionResult:
    """Outcome of one compression pass over a message list."""

    messages: list[tuple[str, str]]
    system_instruction: str | None
    changed: bool = False
    bypassed: bool = False
    bypass_reason: str | None = None
    chars_before: int = 0
    chars_after: int = 0
    blocks_deduped: int = 0
    messages_deduped: int = 0

    @property
    def est_tokens_saved(self) -> int:
        """Estimated tokens saved, using the fleet's chars//4 estimator."""
        return max(0, (self.chars_before - self.chars_after) // 4)


@dataclass
class _Stats:
    requests_seen: int = 0
    requests_compressed: int = 0
    requests_bypassed: int = 0
    chars_before: int = 0
    chars_after: int = 0
    blocks_deduped: int = 0
    messages_deduped: int = 0


_STATS = _Stats()
_STATS_LOCK = threading.Lock()


def compression_stats() -> dict[str, Any]:
    """Process-wide measured savings (served on the admin dashboard)."""
    with _STATS_LOCK:
        s = _Stats(**vars(_STATS))
    saved_chars = max(0, s.chars_before - s.chars_after)
    return {
        "enabled": ENABLED,
        "min_tokens_bypass": MIN_TOKENS,
        "requests_seen": s.requests_seen,
        "requests_compressed": s.requests_compressed,
        "requests_bypassed": s.requests_bypassed,
        "chars_before": s.chars_before,
        "chars_after": s.chars_after,
        "est_tokens_saved": saved_chars // 4,
        "blocks_deduped": s.blocks_deduped,
        "messages_deduped": s.messages_deduped,
        "basis": (
            "measured on this process since start; token figures use the fleet "
            "chars//4 estimator, not provider-reported usage"
        ),
    }


def _record(result: CompressionResult) -> None:
    with _STATS_LOCK:
        _STATS.requests_seen += 1
        if result.bypassed:
            _STATS.requests_bypassed += 1
        elif result.changed:
            _STATS.requests_compressed += 1
        _STATS.chars_before += result.chars_before
        _STATS.chars_after += result.chars_after
        _STATS.blocks_deduped += result.blocks_deduped
        _STATS.messages_deduped += result.messages_deduped


def _clean_whitespace(text: str) -> str:
    """Whitespace normalisation that never touches fenced code blocks."""
    parts = _FENCE.split(text)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            continue  # fenced code block: byte-for-byte
        part = part.translate(_ZERO_WIDTH)
        part = _TRAILING_WS.sub("", part)
        part = _SPACE_RUN.sub(" ", part)
        part = _BLANK_RUN.sub("\n\n", part)
        parts[i] = part
    return "".join(parts)


def _dedupe_blocks(text: str, seen: set[str]) -> tuple[str, int]:
    """Replace repeated long blocks with the omission marker.

    Blocks are split on blank lines. Fenced code blocks are treated as
    opaque: never split, never deduped, never marked as seen content.
    """
    parts = _FENCE.split(text)
    deduped = 0
    for i, part in enumerate(parts):
        if i % 2 == 1:
            continue
        blocks = part.split("\n\n")
        kept: list[str] = []
        for block in blocks:
            key = block.strip()
            if len(key) >= MIN_DEDUPE_BLOCK_CHARS and key in seen:
                kept.append(_OMISSION_MARKER)
                deduped += 1
                continue
            if len(key) >= MIN_DEDUPE_BLOCK_CHARS:
                seen.add(key)
            kept.append(block)
        parts[i] = "\n\n".join(kept)
    return "".join(parts), deduped


def estimate_tokens(messages: list[tuple[str, str]], system_instruction: str | None) -> int:
    chars = len(system_instruction or "")
    for _role, content in messages:
        chars += len(content or "")
    return max(1, chars // 4)


def compress_messages(
    messages: list[tuple[str, str]],
    system_instruction: str | None = None,
    *,
    enabled: bool | None = None,
    min_tokens: int | None = None,
) -> CompressionResult:
    """Compress a ``[(role, content), ...]`` conversation.

    Pure function over plain tuples so it is testable without the provider
    stack; :func:`compress_provider_request` adapts it to ProviderRequest.
    """
    is_enabled = ENABLED if enabled is None else enabled
    threshold = MIN_TOKENS if min_tokens is None else min_tokens
    chars_before = len(system_instruction or "") + sum(len(c or "") for _r, c in messages)
    result = CompressionResult(
        messages=list(messages),
        system_instruction=system_instruction,
        chars_before=chars_before,
        chars_after=chars_before,
    )
    if not is_enabled:
        result.bypassed, result.bypass_reason = True, "disabled by INFERENCE_TOKEN_COMPRESSION_ENABLED"
        _record(result)
        return result
    if estimate_tokens(messages, system_instruction) < threshold:
        result.bypassed, result.bypass_reason = True, f"below {threshold}-token bypass threshold"
        _record(result)
        return result

    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    seen_messages: set[tuple[str, str]] = set()
    total_deduped = 0

    system_out = system_instruction
    if system_instruction:
        system_out, d = _dedupe_blocks(_clean_whitespace(system_instruction), seen)
        total_deduped += d

    for role, content in messages:
        cleaned = _clean_whitespace(content or "")
        # Whole-message dedupe runs on the cleaned text BEFORE block dedupe:
        # a verbatim repeat is dropped outright, while a message that merely
        # re-quotes an earlier block keeps its turn with the block marked.
        if (role, cleaned) in seen_messages and cleaned.strip():
            result.messages_deduped += 1
            continue
        seen_messages.add((role, cleaned))
        deduped_content, d = _dedupe_blocks(cleaned, seen)
        total_deduped += d
        out.append((role, deduped_content))

    result.messages = out
    result.system_instruction = system_out
    result.blocks_deduped = total_deduped
    result.chars_after = len(system_out or "") + sum(len(c) for _r, c in out)
    result.changed = result.chars_after != result.chars_before or bool(total_deduped) or bool(result.messages_deduped)
    _record(result)
    return result


def compress_provider_request(request: Any) -> Any:
    """Apply :func:`compress_messages` to a ProviderRequest, in place-safe fashion.

    Returns a (possibly new) request object. The original is never mutated:
    the gateway may retry the same request object across rungs, and callers
    keep provenance on what they sent.
    """
    messages = [(m.role, m.content) for m in request.messages]
    result = compress_messages(messages, request.system_instruction)
    if not result.changed:
        return request
    from app.providers.base import ProviderMessage

    new_request = request.model_copy(deep=True)
    new_request.messages = [ProviderMessage(role=role, content=content) for role, content in result.messages]
    new_request.system_instruction = result.system_instruction
    return new_request
