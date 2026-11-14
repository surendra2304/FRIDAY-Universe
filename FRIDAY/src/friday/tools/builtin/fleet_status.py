"""TASK-API-002: truthful fleet status tool.

"Friday, how's the fleet?" must be answered with a REAL probe of all nine
specialist agents, not an LLM's guess. This tool wraps the shared
``FleetClient`` (the same client behind ``GET /api/agents/status``) so the
friend persona and the dashboard report the same truth.

Truthfulness rules (mirrors the /api/agents/status contract):
- every reported status comes from an actual health probe, never invented;
- a probe failure is reported as UNREACHABLE with the failure reason — never
  smoothed to "online";
- the scope is stated explicitly: peer endpoint reachability only, not
  task-level verification.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = logging.getLogger(__name__)

#: Statuses that count as "up" for the summary line.
_UP_STATUSES = {"ONLINE", "REACHABLE"}

#: FRIDAY itself is answering, so it is online by construction; the probe
#: surface covers the nine specialists (matching /api/agents/status).
_SPECIALIST_COUNT = 9


class FleetStatusTool(BaseTool):
    """Report the live, truthful health of the ten-agent FRIDAY Universe fleet."""

    name = "get_fleet_status"
    description = (
        "Check the live status of the FRIDAY Universe agent fleet: all nine "
        "specialist agents (Inference, Memora, Stratex, IntelX, Futuris, "
        "Cortex, Forge, Sentinel, VyralX) plus FRIDAY itself. Use this for "
        "questions like 'how is the fleet', 'are the agents online', "
        "'status of the universe', or 'who is unreachable'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 30.0
    parameters = {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "description": "'summary' (default) for the one-line health "
                "picture, or 'full' for every agent with latency and details.",
                "enum": ["summary", "full"],
                "default": "summary",
            }
        },
        "required": [],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        # Lazy import: keeps the tool importable without the API host.
        # TASK-REL-007D: shared client — a fresh FleetClient per call meant
        # a cold probe cache + new httpx pool for every status question.
        from friday.ecosystem.fleet_client import get_shared_fleet_client

        return get_shared_fleet_client()

    @staticmethod
    def _format(statuses: list[Any], detail: str) -> str:
        up = sum(1 for s in statuses if getattr(s, "status", "") in _UP_STATUSES)
        total = _SPECIALIST_COUNT
        # FRIDAY itself is online by construction (it is answering).
        summary = (
            f"Fleet status: {up}/{total} specialist agents up "
            f"(+ FRIDAY, who is talking to you right now). "
            "Scope: peer endpoint reachability, not task-level verification."
        )
        if detail != "full":
            degraded = [
                s for s in statuses if getattr(s, "status", "") not in _UP_STATUSES
            ]
            if degraded:
                names = ", ".join(
                    f"{s.name} ({s.status}" + (f": {s.details}" if s.details else "") + ")"
                    for s in degraded
                )
                summary += f" Attention: {names}."
            return summary

        lines = [summary, ""]
        for s in sorted(statuses, key=lambda x: x.name):
            latency = f", {s.latency_ms} ms" if s.latency_ms is not None else ""
            lines.append(f"- {s.name} ({s.role}): {s.status}{latency}")
            if s.details:
                lines.append(f"    {s.details}")
        return "\n".join(lines)

    def execute(self, detail: str = "summary", **kwargs: Any) -> ToolResult:
        client = self._client()
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                # The tool contract is synchronous; a live loop means we were
                # called from async context — run the probe on a worker thread
                # so we never block or nest loops.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    statuses = pool.submit(
                        lambda: asyncio.run(client.get_all_statuses())
                    ).result(timeout=self.timeout)
            else:
                statuses = asyncio.run(client.get_all_statuses())
        except Exception as exc:
            # Truthful failure: say the probe failed, never invent a status.
            return ToolResult(
                name=self.name,
                content=(
                    "I could not probe the fleet right now "
                    f"({type(exc).__name__}: {exc}). I won't guess — try again "
                    "in a moment, or check /api/agents/status directly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        report = {
            "scope": "peer_endpoint_reachability_only",
            "specialists_up": sum(
                1 for s in statuses if getattr(s, "status", "") in _UP_STATUSES
            ),
            "specialists_total": _SPECIALIST_COUNT,
            "agents": [
                {
                    "name": s.name,
                    "role": s.role,
                    "status": s.status,
                    "latency_ms": s.latency_ms,
                    "endpoint": s.endpoint,
                    "details": s.details,
                }
                for s in statuses
            ],
        }
        return ToolResult(
            name=self.name,
            content=self._format(list(statuses), detail),
            is_error=False,
            safety_level=self.safety_level,
            metadata={"fleet": report, "raw": json.dumps(report, default=str)},
        )
