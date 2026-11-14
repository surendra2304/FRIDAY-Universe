"""TASK-REL-006A: recover tool calls that models emit as text markup.

Production evidence (console test round 1, 2026-11-14 14:06-14:11 IST, and
re-verified by Muse's live probes the same day): the fleet's usual model
(Groq ``openai/gpt-oss-120b``) sometimes answers a tool-worthy turn with NO
structured ``tool_calls`` and the intended call spelled out in the visible
content instead, e.g.::

    <tool name="get_current_time" params='{"timezone":"Asia/Tokyo"}'/>

Every provider parser only read the structured channel, and the agent loop
only guarded against invented *delegation* XML (``<execute_agent>`` …), so
this markup was returned to the owner as the ENTIRE reply — never executed,
no joke, no time, turn over.

This module is the single recovery point used by the Groq/OpenAI provider
parsers AND the agent's tool loop (which also covers providers that do not
parse markup themselves):

* :func:`extract_markup_tool_calls` — parse the known markup shapes into
  real :class:`ToolCall` objects plus the remaining plain text;
* :func:`canonical_tool_name` — map the names models invent
  (``get_current_time``) onto the registered tool (``get_time_date``);
* :func:`strip_tool_markup` — last-resort sanitizer so a final answer can
  never leak raw tool markup to the user, even if recovery failed.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from friday.core.types import ToolCall

#: Names models invent for registered tools. The left side is what appeared
#: in model output; the right side is the tool actually registered in
#: ``ToolExecutionMixin._create_default_registry``.
TOOL_NAME_ALIASES: dict[str, str] = {
    "get_current_time": "get_time_date",
    "current_time": "get_time_date",
    "get_time": "get_time_date",
    "time_date": "get_time_date",
    "get_date": "get_time_date",
    "get_current_date": "get_time_date",
    "calculate": "calculator",
    "get_weather_forecast": "get_weather",
    "search_web": "web_search",
    "get_system_status": "get_system_info",
}

# <tool name="x" params='{...}'/> | <tool name="x" arguments="{...}"></tool>
_TOOL_TAG_RE = re.compile(
    r"<tool\s+[^>]*?name\s*=\s*[\"'](?P<name>[A-Za-z0-9_\-]+)[\"']"
    r"(?P<attrs>[^>]*?)"
    r"(?:/>|>(?P<body>.*?)</tool>)",
    re.DOTALL | re.IGNORECASE,
)
# <function=name>{...}</function> | <function name="x">{...}</function>
_FUNCTION_TAG_RE = re.compile(
    r"<function\s*(?:=\s*|name\s*=\s*[\"'])(?P<name>[A-Za-z0-9_\-]+)[\"']?"
    r"\s*>(?P<body>.*?)</function>",
    re.DOTALL | re.IGNORECASE,
)
_PARAMS_ATTR_RE = re.compile(
    r"(?:params|arguments|args)\s*=\s*(?P<q>[\"'])(?P<json>.*?)(?P=q)",
    re.DOTALL,
)


def canonical_tool_name(name: str) -> str:
    """Map a model-emitted tool name onto the registered tool name."""
    key = (name or "").strip()
    return TOOL_NAME_ALIASES.get(key, TOOL_NAME_ALIASES.get(key.lower(), key))


def _parse_args(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (json.JSONDecodeError, ValueError):
        pass
    # Models sometimes single-quote the whole JSON object.
    try:
        parsed = json.loads(raw.replace("'", '"'))
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (json.JSONDecodeError, ValueError):
        return {}


def extract_markup_tool_calls(content: str | None) -> tuple[list[ToolCall], str]:
    """Recover tool calls spelled as markup in *content*.

    Returns ``(calls, remaining_text)``. ``calls`` is empty when the content
    carries no recognizable tool markup; ``remaining_text`` is the content
    with every recognized markup span removed.
    """
    if not content or "<" not in content:
        return [], content or ""
    calls: list[ToolCall] = []
    spans: list[tuple[int, int]] = []

    for match in _TOOL_TAG_RE.finditer(content):
        args: dict[str, Any] = {}
        attrs = match.group("attrs") or ""
        attr_match = _PARAMS_ATTR_RE.search(attrs)
        if attr_match:
            args = _parse_args(attr_match.group("json"))
        if not args and match.group("body"):
            args = _parse_args(match.group("body"))
        calls.append(
            ToolCall(
                id=f"markup_{uuid.uuid4().hex[:12]}",
                name=canonical_tool_name(match.group("name")),
                arguments=args,
            )
        )
        spans.append(match.span())

    for match in _FUNCTION_TAG_RE.finditer(content):
        if any(start <= match.start() < end for start, end in spans):
            continue  # already consumed as a <tool> span
        calls.append(
            ToolCall(
                id=f"markup_{uuid.uuid4().hex[:12]}",
                name=canonical_tool_name(match.group("name")),
                arguments=_parse_args(match.group("body")),
            )
        )
        spans.append(match.span())

    if not calls:
        return [], content
    remaining = content
    for start, end in sorted(spans, reverse=True):
        remaining = remaining[:start] + remaining[end:]
    return calls, remaining.strip()


def strip_tool_markup(content: str | None) -> str:
    """Remove any tool-call markup from *content* (recognized or not).

    Used as defense-in-depth on final answers: whatever recovery could not
    execute must still never be shown to the user as raw markup.
    """
    if not content:
        return ""
    cleaned = _TOOL_TAG_RE.sub("", content)
    cleaned = _FUNCTION_TAG_RE.sub("", cleaned)
    # Unclosed / malformed leftovers of the same family.
    cleaned = re.sub(r"</?tool\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?function\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()
