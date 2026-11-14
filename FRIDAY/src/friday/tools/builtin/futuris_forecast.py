"""Checklist F10/C10 (MASTER_COMPLETION_CHECKLIST): Futuris forecasts via chat.

The owner asks for a forecast in plain words ("forecast BTC over the next
24 hours", "what does Futuris predict for the fleet's API load") and gets
Futuris's REAL answer — the same evidence-backed FRIDAY delegation contract
Futuris serves at POST /v1/friday/forecast: research enrichment, the
forecasting pipeline (lookback 14d), honest calibration, and the invariant
that a PREDICTION IS NEVER AN AUTHORIZATION.

Honesty rules:
- Futuris's own statuses (BLOCKED / INSUFFICIENT_DATA) are reported as-is —
  a weak data picture is never dressed up as a forecast;
- every failure (auth, connection, non-2xx) is returned honestly;
- every answer states that forecasts inform but never execute anything.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from friday.tools.base import BaseTool
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.builtin.fleet_dispatch import record_specialist_dispatch

_HORIZONS = ("1h", "24h", "7d", "30d")


def _extract_horizon(text: str) -> str:
    """Pull an explicit horizon out of the request; default 24h."""
    low = (text or "").lower()
    m = re.search(r"\bnext\s+(\d+)\s*(hour|hours|day|days|week|weeks)\b", low)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("hour"):
            return "1h" if n <= 1 else "24h"
        if unit.startswith("day"):
            return "24h" if n <= 1 else "7d" if n <= 7 else "30d"
        if unit.startswith("week"):
            return "7d" if n == 1 else "30d"
    if re.search(r"\bhourly\b|\bnext hour\b|\b1h\b", low):
        return "1h"
    if re.search(r"\bweek\b|\b7d\b", low):
        return "7d"
    if re.search(r"\bmonth\b|\b30d\b", low):
        return "30d"
    return "24h"


def _extract_target(text: str, default: str = "fleet:api:request_rate") -> str:
    """Pull the forecast target out of the request.

    Keeps quoted targets verbatim; otherwise strips the forecast verbs so
    "forecast the fleet's api request rate over 24h" becomes a clean target.
    Falls back to the default target rather than guessing a fake one — the
    caller sees exactly which target was forecast.
    """
    low = (text or "").lower().strip().rstrip(".!? ")
    m = re.search(r"['\"]([^'\"]{3,80})['\"]", low)
    if m:
        return m.group(1).strip()
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
        r"(?:forecast|predict|project|what does futuris (?:predict|forecast|say)(?: about)?|"
        # TASK-REL-007: allow a qualifier ("give me a SHORT forecast: ...") —
        # without it the whole sentence became the forecast target.
        r"give me (?:a |the )?(?:(?:short|quick|brief|latest) )?forecast(?: for)?|"
        r"get (?:me )?(?:a |the )?forecast(?: for)?)\s*"
        r"(?:the\s+|for\s+|about\s+|of\s+)?",
        "", low,
    )
    cleaned = cleaned.lstrip(":,- ").strip()
    # "give me a short forecast: what should I expect for my portfolio"
    # -> target is what follows the expectation phrasing.
    cleaned = re.sub(
        r"^(?:what should i expect (?:for|from)|what to expect (?:for|from))\s+",
        "", cleaned,
    )
    cleaned = re.sub(
        r"\s+(?:over|in|during|for|within)\s+(?:the\s+)?(?:next\s+)?"
        r"(?:\d+\s*)?(?:hour|hours|day|days|week|weeks|month|months|1h|24h|7d|30d)\b.*$",
        "", cleaned,
    )
    cleaned = re.sub(r"\s+(?:this|next)\s+(?:week|month)\b.*$", "", cleaned).strip()
    if 3 <= len(cleaned) <= 80:
        return cleaned
    return default


class FuturisForecastTool(BaseTool):
    """Request a real forecast from Futuris, the fleet's predictive-intelligence agent."""

    name = "futuris_forecast"
    description = (
        "Request a real, evidence-backed forecast from Futuris, the fleet's "
        "Predictive Intelligence agent: point estimate, uncertainty band, "
        "status, confidence and calibration for a named target over a chosen "
        "horizon (1h, 24h, 7d, 30d). Futuris reports BLOCKED or "
        "INSUFFICIENT_DATA honestly instead of dressing a weak data picture "
        "as a forecast. A prediction is never an authorization. Use for "
        "requests like 'forecast the api request rate over the next 24 "
        "hours', 'what does futuris predict for btc', 'predict fleet load'."
    )
    safety_level = SafetyLevel.SAFE
    # TASK-REL-007: must exceed FleetClient's forecast POST budget (120s) —
    # Futuris needs ~40s warm / ~114s cold on the fleet host for a real
    # pipeline run; a 45s tool budget killed every registry-path forecast.
    timeout = 150.0
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The forecast request in plain words (e.g. 'forecast api load over 24h').",
            },
            "target": {
                "type": "string",
                "description": "Optional explicit target metric (e.g. 'fleet:api:request_rate'). Extracted from the question when omitted.",
            },
            "horizon": {
                "type": "string",
                "enum": ["1h", "24h", "7d", "30d"],
                "description": "Forecast horizon (default: extracted from the question, else 24h).",
                "default": "24h",
            },
        },
        "required": [],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def execute(
        self,
        question: str = "",
        target: str = "",
        horizon: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        question = (question or "").strip()
        target = (target or "").strip() or _extract_target(question)
        horizon = (horizon or "").strip().lower()
        if horizon not in _HORIZONS:
            horizon = _extract_horizon(question)

        try:
            result = asyncio.run(self._client().request_futuris_forecast(target=target, horizon=horizon))
        except Exception as exc:
            record_specialist_dispatch("", "futuris", question or target, "failed", error=f"{type(exc).__name__}: {exc}")
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Futuris for that forecast ({type(exc).__name__}: {exc}). "
                    "I won't invent numbers — try again shortly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        reply = str((result or {}).get("reply", "") or "")
        if not reply:
            record_specialist_dispatch("", "futuris", question or target, "failed", error="empty_reply")
            return ToolResult(
                name=self.name,
                content=(
                    "Futuris did not return a readable forecast for that request. "
                    "That is the real outcome — nothing was invented."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": "empty_reply"},
            )
        record_specialist_dispatch("", "futuris", question or target, "success")
        return ToolResult(
            name=self.name,
            content=reply,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "futuris": {
                    "target": target,
                    "horizon": horizon,
                    **{k: v for k, v in ((result or {}).get("metadata", {}) or {}).items() if k != "agent_id"},
                },
                "raw": str(result)[:4000],
            },
        )
