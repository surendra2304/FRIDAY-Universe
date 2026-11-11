"""Checklist F23 (MASTER_COMPLETION_CHECKLIST) — Batch 7, ZAI Agent 2.

Render a video clip through VyralX's real free-tool pipeline (ffmpeg +
edge_tts; the existing VyralX/scripts/render_*.py modules). The owner
asks "render the script as a short" or "render this clip" — the answer
must come from VyralX's REAL render endpoint (honest manifest with the
output path, duration and bytes), never a fabricated "done" reply.

Routing (server chain): RENDER_KEYWORDS → TOOL_EXECUTION vyralx_render
— never DIRECT_REASONING. Render is a one-shot dispatch through the
FleetClient (same circuit breaker + honest-failure shape as
vyralx_script).
"""

from __future__ import annotations

import asyncio
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class VyralXRenderTool(BaseTool):
    """Render a drafted VyralX script into a clip (free-tool ffmpeg pipeline)."""

    name = "vyralx_render"
    description = (
        "Render a drafted video script into a short clip through VyralX's free-tool "
        "pipeline (ffmpeg + edge_tts; the same scripts VyralX uses for its own "
        "renders). Use when the owner says 'render the script as a short', 'render "
        "this clip', 'turn that script into a video'. Returns the real manifest: "
        "output path, duration, bytes. Honest failures when VyralX is unreachable."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 90.0
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the drafted script to render (matches the title used when drafting).",
            },
            "script_text": {
                "type": "string",
                "description": "Optional: the script text to render if no draft exists by title.",
            },
            "format": {
                "type": "string",
                "enum": ["shorts", "wide"],
                "description": "Output aspect: 'shorts' (9:16, default) or 'wide' (16:9).",
                "default": "shorts",
            },
        },
        "required": ["title"],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def execute(self, title: str = "", script_text: str = "", format: str = "shorts", **kwargs: Any) -> ToolResult:
        title = (title or "").strip()
        if not title:
            return ToolResult(
                name=self.name,
                content="I need the script title to render — which draft should I turn into a clip, Boss?",
                is_error=True,
                safety_level=self.safety_level,
            )
        fmt = (format or "shorts").lower()
        if fmt not in ("shorts", "wide"):
            fmt = "shorts"
        try:
            result = asyncio.run(self._render(title=title, script_text=script_text, fmt=fmt))
        except RuntimeError as exc:
            return ToolResult(
                name=self.name,
                content=f"🎬 [VYRALX RENDER] I couldn't render '{title}': {exc}. Nothing was rendered.",
                is_error=True,
                safety_level=self.safety_level,
            )
        if not result.get("success", True):
            return ToolResult(
                name=self.name,
                content=str(result.get("reply", "Render failed.")),
                is_error=True,
                safety_level=self.safety_level,
                metadata=result.get("metadata", {}),
            )
        return ToolResult(
            name=self.name,
            content=str(result.get("reply", "Rendered.")),
            safety_level=self.safety_level,
            metadata=result.get("metadata", {}),
        )

    async def _render(self, *, title: str, script_text: str, fmt: str) -> dict[str, Any]:
        """Dispatch to VyralX's real hyperframes render endpoint (F23).

        Honors the FleetClient circuit breaker + records usage for F3.
        """
        from friday.ecosystem.fleet_client import FleetClient
        from friday.proactive.market_watch import usage_tracker

        client = self._client()
        breaker = client.get_circuit_breaker("vyralx")
        if not await breaker.can_execute():
            return {
                "reply": "🎬 [VYRALX RENDER // CIRCUIT OPEN] Requests blocked to protect fleet stability.",
                "metadata": {"agent_id": "vyralx", "error": "circuit_open", "status": "degraded"},
                "success": False,
            }
        if not getattr(client, "vyralx_url", ""):
            return {
                "reply": "VyralX is not configured; no render request was attempted.",
                "metadata": {"agent_id": "vyralx", "error": "base_url_not_configured"},
                "success": False,
            }
        headers = {"Content-Type": "application/json"}
        if getattr(client, "vyralx_key", ""):
            headers["X-API-Key"] = client.vyralx_key
            headers["Authorization"] = f"Bearer {client.vyralx_key}"
        try:
            shared = client.get_shared_client()
            scene = {
                "title": title,
                "format": fmt,
                "script": script_text or title,
                "voice": "en-US-GuyNeural",
                "engine": "hyperframes",
            }
            resp = await shared.post(
                f"{client.vyralx_url}/api/v1/real-engines/hyperframes/render",
                json={"scene": scene},
                headers=headers,
                timeout=60.0,
            )
        except Exception as exc:
            await breaker.record_failure(exc)
            return {
                "reply": f"🎬 [VYRALX RENDER] I couldn't reach VyralX to render '{title}': {type(exc).__name__}: {exc}.",
                "metadata": {"agent_id": "vyralx", "error": str(exc)},
                "success": False,
            }
        if resp.status_code not in (200, 201):
            if resp.status_code >= 500:
                await breaker.record_failure()
            return {
                "reply": (
                    f"🎬 [VYRALX RENDER] VyralX answered HTTP {resp.status_code} — the clip could not be rendered. "
                    "That is the real outcome."
                ),
                "metadata": {"agent_id": "vyralx", "error": f"http_{resp.status_code}"},
                "success": False,
            }
        await breaker.record_success()
        usage_tracker.record("vyralx", calls=1)
        data = resp.json() if resp.text else {}
        result = data.get("result") if isinstance(data, dict) else data
        if not isinstance(result, dict):
            result = {}
        output = result.get("output") or result.get("path") or "not reported"
        duration = result.get("duration") or result.get("total_duration")
        bytes_ = result.get("bytes") or result.get("size")
        lines = [
            f"🎬 [VYRALX RENDER] '{title}' rendered ({fmt}):",
            f"• Output: {output}",
        ]
        if duration is not None:
            lines.append(f"• Duration: {duration}s")
        if bytes_ is not None:
            lines.append(f"• Size: {bytes_} bytes")
        lines.append(
            "Render done LOCALLY on VyralX. Nothing was uploaded or published — "
            "publishing stays a separate, explicit owner action (vyralx_publish)."
        )
        return {
            "reply": "\n".join(lines),
            "metadata": {
                "agent_id": "vyralx",
                "agent_name": "VyralX",
                "output": output,
                "duration": duration,
                "bytes": bytes_,
                "format": fmt,
                "rendered_locally": True,
            },
            "success": True,
        }
