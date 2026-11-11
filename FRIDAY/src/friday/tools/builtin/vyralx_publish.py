"""Checklist F24 (MASTER_COMPLETION_CHECKLIST) — Batch 7, ZAI Agent 2.

Publish a drafted+rendered VyralX clip as a YouTube/Shorts DRAFT upload.

Fail-closed by design (mirrors the Stratex live-trading guard D-015):
- DEFAULT mode = draft upload only (creates a private draft on the owner's
  YouTube channel for review; never makes the clip public);
- PRODUCTION publish (status=public) requires the explicit owner phrase
  "publish to youtube" AND an owner-authorization flag — exactly the two-
  gate pattern Stratex uses for live trades.

Routing (server chain): PUBLISH_KEYWORDS → TOOL_EXECUTION vyralx_publish
— never DIRECT_REASONING. The honest reply always states which mode ran
and that production publishing is gated.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


#: Owner-authorization flag. Production publishing is BLOCKED unless this is
#: literally "true" in the environment — same two-gate shape as Stratex (D-015).
PROD_PUBLISH_ENV = "FRIDAY_VYRALX_PUBLISH_PROD_ALLOWED"

#: The phrase the owner must say for a production publish (D-015 shape).
PROD_CONFIRM_PHRASE = "publish to youtube"


class VyralXPublishTool(BaseTool):
    """Publish a rendered VyralX clip as a YouTube/Shorts DRAFT (fail-closed)."""

    name = "vyralx_publish"
    description = (
        "Publish a rendered clip to YouTube as a DRAFT for the owner's review. "
        "Use when the owner says 'publish the clip', 'upload as draft', "
        "'send the short to youtube'. DEFAULT = private draft (no public "
        "release). Production publish (status=public) requires the explicit "
        "phrase 'publish to youtube' AND the owner-authorization flag — "
        "same two-gate guard as live trading (D-015)."
    )
    safety_level = SafetyLevel.SAFE  # default draft; production path re-classifies
    timeout = 90.0
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the rendered clip to publish (matches the render output title).",
            },
            "status": {
                "type": "string",
                "enum": ["draft", "public"],
                "description": "'draft' (default — private review) or 'public' (production publish; gated).",
                "default": "draft",
            },
            "confirm_phrase": {
                "type": "string",
                "description": "Required only when status=public; must be the exact owner phrase 'publish to youtube'.",
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

    def execute(self, title: str = "", status: str = "draft", confirm_phrase: str = "", **kwargs: Any) -> ToolResult:
        title = (title or "").strip()
        if not title:
            return ToolResult(
                name=self.name,
                content="I need the clip title to publish — which rendered clip should I upload, Boss?",
                is_error=True,
                safety_level=self.safety_level,
            )
        mode = (status or "draft").lower()
        # ── Fail-closed gate (D-015 shape) ──────────────────────────────────
        if mode == "public":
            if (confirm_phrase or "").strip().lower() != PROD_CONFIRM_PHRASE:
                return ToolResult(
                    name=self.name,
                    content=(
                        f"I won't publish '{title}' publicly, Boss. Production publishing is gated "
                        f"(same two-gate guard as live trading, D-015): say the exact phrase "
                        f"'{PROD_CONFIRM_PHRASE}' AND set {PROD_PUBLISH_ENV}=true in the environment. "
                        "Nothing was uploaded."
                    ),
                    is_error=True,
                    safety_level=SafetyLevel.DANGEROUS,
                    metadata={"gate": "confirm_phrase_missing"},
                )
            if os.getenv(PROD_PUBLISH_ENV, "").lower() != "true":
                return ToolResult(
                    name=self.name,
                    content=(
                        f"I have your confirmation phrase for '{title}', but the owner-authorization flag "
                        f"{PROD_PUBLISH_ENV} is not set to 'true' in the environment. Production publish is "
                        "blocked. Nothing was uploaded."
                    ),
                    is_error=True,
                    safety_level=SafetyLevel.DANGEROUS,
                    metadata={"gate": "env_flag_missing"},
                )
        try:
            result = asyncio.run(self._publish(title=title, mode=mode))
        except RuntimeError as exc:
            return ToolResult(
                name=self.name,
                content=f"📤 [VYRALX PUBLISH] I couldn't publish '{title}': {exc}. Nothing was uploaded.",
                is_error=True,
                safety_level=self.safety_level,
            )
        if not result.get("success", True):
            return ToolResult(
                name=self.name,
                content=str(result.get("reply", "Publish failed.")),
                is_error=True,
                safety_level=self.safety_level,
                metadata=result.get("metadata", {}),
            )
        return ToolResult(
            name=self.name,
            content=str(result.get("reply", "Published.")),
            safety_level=SafetyLevel.DANGEROUS if mode == "public" else SafetyLevel.SAFE,
            metadata=result.get("metadata", {}),
        )

    async def _publish(self, *, title: str, mode: str) -> dict[str, Any]:
        """Dispatch to VyralX's real publish surface (F24)."""
        from friday.ecosystem.fleet_client import FleetClient
        from friday.proactive.market_watch import usage_tracker

        client = self._client()
        breaker = client.get_circuit_breaker("vyralx")
        if not await breaker.can_execute():
            return {
                "reply": "📤 [VYRALX PUBLISH // CIRCUIT OPEN] Requests blocked to protect fleet stability.",
                "metadata": {"agent_id": "vyralx", "error": "circuit_open", "status": "degraded"},
                "success": False,
            }
        if not getattr(client, "vyralx_url", ""):
            return {
                "reply": "VyralX is not configured; no publish request was attempted.",
                "metadata": {"agent_id": "vyralx", "error": "base_url_not_configured"},
                "success": False,
            }
        headers = {"Content-Type": "application/json"}
        if getattr(client, "vyralx_key", ""):
            headers["X-API-Key"] = client.vyralx_key
            headers["Authorization"] = f"Bearer {client.vyralx_key}"
        try:
            shared = client.get_shared_client()
            # The publish route the VyralX publish scripts post to.
            resp = await shared.post(
                f"{client.vyralx_url}/api/v1/vyralx/publish",
                json={"title": title, "status": mode, "source": "friday_chat"},
                headers=headers,
                timeout=60.0,
            )
        except Exception as exc:
            await breaker.record_failure(exc)
            return {
                "reply": f"📤 [VYRALX PUBLISH] I couldn't reach VyralX to publish '{title}': {type(exc).__name__}: {exc}.",
                "metadata": {"agent_id": "vyralx", "error": str(exc)},
                "success": False,
            }
        if resp.status_code not in (200, 201, 202):
            if resp.status_code >= 500:
                await breaker.record_failure()
            return {
                "reply": (
                    f"📤 [VYRALX PUBLISH] VyralX answered HTTP {resp.status_code} — the clip could not be published. "
                    "That is the real outcome."
                ),
                "metadata": {"agent_id": "vyralx", "error": f"http_{resp.status_code}"},
                "success": False,
            }
        await breaker.record_success()
        usage_tracker.record("vyralx", calls=1)
        data = resp.json() if resp.text else {}
        video_id = data.get("video_id") or data.get("id")
        upload_status = data.get("status") or data.get("upload_status") or ("public" if mode == "public" else "draft")
        lines = [
            f"📤 [VYRALX PUBLISH] '{title}' uploaded to YouTube:",
            f"• Status: {upload_status}",
        ]
        if video_id:
            lines.append(f"• Video ID: {video_id}")
            if upload_status == "draft":
                lines.append(f"• Review URL: https://studio.youtube.com/video/{video_id}/edit")
            else:
                lines.append(f"• Watch URL: https://youtu.be/{video_id}")
        if upload_status == "draft":
            lines.append("DRAFT only — the clip is private until you publish it in YouTube Studio.")
        else:
            lines.append("PRODUCTION publish — the clip is now public.")
        return {
            "reply": "\n".join(lines),
            "metadata": {
                "agent_id": "vyralx",
                "agent_name": "VyralX",
                "video_id": video_id,
                "upload_status": upload_status,
                "mode": mode,
            },
            "success": True,
        }
