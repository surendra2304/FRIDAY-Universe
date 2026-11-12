"""Checklist F23 (MASTER_COMPLETION_CHECKLIST) — Batch 7, ZAI Agent 2.
CONTRACT FIX 2026-11-12 (ZAI Agent 2): the first version posted a scene
dict to /api/v1/real-engines/hyperframes/render — a sync demo route. The REAL
production render pipeline is a job queue:

  1. POST /api/render  {asset_id, preset: shorts|long|square,
     trim_start_seconds, trim_end_seconds, fit_mode, subtitle_segments,
     content_pack_id}  → 202 {job_id, status: "queued"} — REQUIRES an
     existing asset with verified rights and a ffprobe-verified duration.
  2. GET /api/render  → the render job list with per-job status
     (queued/running/completed + output_path on completion).

So this tool honestly queues a render through the real pipeline and reports
the job id; the owner polls status with a second invocation (or asks
"render status"). Nothing is ever claimed rendered that the worker has not
actually completed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class VyralXRenderTool(BaseTool):
    """Queue a real VyralX render job (ffmpeg worker pipeline)."""

    name = "vyralx_render"
    description = (
        "Queue a render job through VyralX's REAL render pipeline (POST /api/render — "
        "the ffmpeg worker queue). Requires an uploaded asset with verified rights; "
        "pick one with asset_id or 0 to auto-pick the newest rights-verified asset. "
        "Returns the real job_id + queued status — the worker renders it; ask "
        "'render status' (status_only=true) to poll GET /api/render. Never claims "
        "a render that hasn't completed."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 90.0
    parameters = {
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "integer",
                "description": "VyralX asset ID to render; 0 to auto-pick the newest rights-verified asset.",
            },
            "preset": {
                "type": "string",
                "enum": ["shorts", "long", "square"],
                "description": "Render preset: 'shorts' (9:16, default), 'long' (16:9), or 'square' (1:1).",
                "default": "shorts",
            },
            "trim_start_seconds": {
                "type": "number",
                "description": "Trim start (seconds, default 0).",
            },
            "trim_end_seconds": {
                "type": "number",
                "description": "Trim end (seconds; default = full asset duration).",
            },
            "status_only": {
                "type": "boolean",
                "description": "True to only list recent render jobs + statuses (GET /api/render); no new job queued.",
                "default": False,
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
        asset_id: int = 0,
        preset: str = "shorts",
        trim_start_seconds: float = 0.0,
        trim_end_seconds: float = 0.0,
        status_only: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        fmt = (preset or "shorts").lower()
        if fmt not in ("shorts", "long", "square"):
            fmt = "shorts"
        try:
            result = asyncio.run(
                self._render(
                    asset_id=int(asset_id or 0),
                    preset=fmt,
                    trim_start=float(trim_start_seconds or 0.0),
                    trim_end=float(trim_end_seconds or 0.0),
                    status_only=bool(status_only),
                )
            )
        except RuntimeError as exc:
            return ToolResult(
                name=self.name,
                content=f"🎬 [VYRALX RENDER] I couldn't queue the render: {exc}. Nothing was queued.",
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
            content=str(result.get("reply", "Queued.")),
            safety_level=self.safety_level,
            metadata=result.get("metadata", {}),
        )

    async def _render(
        self,
        *,
        asset_id: int,
        preset: str,
        trim_start: float,
        trim_end: float,
        status_only: bool,
    ) -> dict[str, Any]:
        """Queue a render through VyralX's REAL POST /api/render pipeline."""
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

        shared = client.get_shared_client()

        # ── Status-only mode: poll GET /api/render ──────────────────────────
        if status_only:
            try:
                resp = await shared.get(f"{client.vyralx_url}/api/render", headers=headers, timeout=20.0)
            except Exception as exc:
                await breaker.record_failure(exc)
                return {
                    "reply": f"🎬 [VYRALX RENDER] I couldn't reach VyralX for render status: {type(exc).__name__}: {exc}.",
                    "metadata": {"agent_id": "vyralx", "error": str(exc)},
                    "success": False,
                }
            if resp.status_code != 200:
                if resp.status_code >= 500:
                    await breaker.record_failure()
                return {
                    "reply": f"🎬 [VYRALX RENDER] Render status answered HTTP {resp.status_code} — that is the real outcome.",
                    "metadata": {"agent_id": "vyralx", "error": f"status_http_{resp.status_code}"},
                    "success": False,
                }
            usage_tracker.record("vyralx", calls=1)
            jobs = resp.json() if resp.text else []
            if not isinstance(jobs, list) or not jobs:
                return {
                    "reply": "🎬 [VYRALX RENDER] No render jobs exist yet — nothing has been queued through the real pipeline.",
                    "metadata": {"agent_id": "vyralx", "jobs": 0, "status_only": True},
                    "success": True,
                }
            lines = ["🎬 [VYRALX RENDER] Recent render jobs (newest first):"]
            for j in jobs[:8]:
                out = j.get("output_path") or ""
                err = j.get("error") or ""
                tail = f" → {out}" if j.get("status") == "completed" and out else (f" (error: {err[:80]})" if err else "")
                lines.append(f"  • Job {j.get('id')} [asset {j.get('asset_id')}] {j.get('preset')}: {j.get('status')}{tail}")
            return {
                "reply": "\n".join(lines),
                "metadata": {"agent_id": "vyralx", "jobs": len(jobs), "status_only": True},
                "success": True,
            }

        # ── Resolve the asset (explicit id or newest rights-verified) ───────
        try:
            a_resp = await shared.get(f"{client.vyralx_url}/api/assets", headers=headers, timeout=20.0)
        except Exception as exc:
            await breaker.record_failure(exc)
            return {
                "reply": f"🎬 [VYRALX RENDER] I couldn't reach VyralX to list assets: {type(exc).__name__}: {exc}. Nothing was queued.",
                "metadata": {"agent_id": "vyralx", "error": str(exc)},
                "success": False,
            }
        if a_resp.status_code != 200:
            if a_resp.status_code >= 500:
                await breaker.record_failure()
            return {
                "reply": f"🎬 [VYRALX RENDER] VyralX assets list answered HTTP {a_resp.status_code} — I can't discover an asset to render. That is the real outcome.",
                "metadata": {"agent_id": "vyralx", "error": f"assets_http_{a_resp.status_code}"},
                "success": False,
            }
        usage_tracker.record("vyralx", calls=1)
        assets = a_resp.json() if a_resp.text else []
        if not isinstance(assets, list) or not assets:
            return {
                "reply": (
                    "🎬 [VYRALX RENDER] VyralX has no assets yet, Boss. The render pipeline needs an uploaded "
                    "asset with verified rights (POST /api/assets/upload on VyralX). Nothing was queued."
                ),
                "metadata": {"agent_id": "vyralx", "assets": 0},
                "success": True,
            }
        if asset_id:
            chosen = next((a for a in assets if a.get("id") == asset_id), None)
            if chosen is None:
                return {
                    "reply": f"🎬 [VYRALX RENDER] Asset {asset_id} does not exist in VyralX. Say 'list vyralx assets' to see what's available.",
                    "metadata": {"agent_id": "vyralx", "error": "asset_not_found"},
                    "success": False,
                }
        else:
            verified = [a for a in assets if a.get("rights_verified")]
            chosen = verified[0] if verified else None
            if chosen is None:
                return {
                    "reply": (
                        "🎬 [VYRALX RENDER] None of VyralX's assets have verified rights, Boss — the render "
                        "pipeline refuses them (403 by design). Verify the source rights on VyralX first."
                    ),
                    "metadata": {"agent_id": "vyralx", "error": "no_rights_verified_assets"},
                    "success": False,
                }

        # ── Queue the render (POST /api/render) ─────────────────────────────
        payload: dict[str, Any] = {"asset_id": chosen["id"], "preset": preset}
        if trim_start > 0:
            payload["trim_start_seconds"] = trim_start
        if trim_end > 0:
            payload["trim_end_seconds"] = trim_end
        try:
            resp = await shared.post(
                f"{client.vyralx_url}/api/render",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
        except Exception as exc:
            await breaker.record_failure(exc)
            return {
                "reply": f"🎬 [VYRALX RENDER] I couldn't reach VyralX to queue the render: {type(exc).__name__}: {exc}. Nothing was queued.",
                "metadata": {"agent_id": "vyralx", "error": str(exc)},
                "success": False,
            }
        if resp.status_code not in (200, 201, 202):
            if resp.status_code >= 500:
                await breaker.record_failure()
            detail = ""
            try:
                detail = str(resp.json().get("detail", ""))[:200]
            except Exception:
                pass
            return {
                "reply": (
                    f"🎬 [VYRALX RENDER] VyralX refused the render request (HTTP {resp.status_code}"
                    + (f": {detail}" if detail else "")
                    + "). That is the real outcome — nothing was queued."
                ),
                "metadata": {"agent_id": "vyralx", "error": f"render_http_{resp.status_code}"},
                "success": False,
            }
        await breaker.record_success()
        usage_tracker.record("vyralx", calls=1)
        data = resp.json() if resp.text else {}
        job_id = data.get("job_id")
        job_status = data.get("status", "queued")
        lines = [
            "🎬 [VYRALX RENDER] Render job queued:",
            f"• Asset: {chosen.get('title', chosen['id'])} (asset_id={chosen['id']}, {chosen.get('duration_seconds', '?')}s)",
            f"• Preset: {preset} | Trim: {trim_start or 0}s → {trim_end or 'end'}",
            f"• Job: {job_id} — status: {job_status}",
        ]
        lines.append(
            "The VyralX worker renders it asynchronously. Ask 'render status' (or say 'vyralx render status') "
            "to poll the real job list — I only report what the worker actually completed."
        )
        return {
            "reply": "\n".join(lines),
            "metadata": {
                "agent_id": "vyralx",
                "agent_name": "VyralX",
                "job_id": job_id,
                "job_status": job_status,
                "asset_id": chosen["id"],
                "preset": preset,
            },
            "success": True,
        }
