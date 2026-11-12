"""Checklist F24 (MASTER_COMPLETION_CHECKLIST) — Batch 7, ZAI Agent 2.
CONTRACT FIX 2026-11-12 (ZAI Agent 2): the first version of this tool posted
a made-up body to a nonexistent route (/api/v1/vyralx/publish). VyralX's REAL
publish flow is a two-gate pipeline:

  1. POST /api/publish  {asset_id, render_job_id, title, description, tags,
     privacy_status, confirm_rights}  → queues a PublishJob, returns
     {job_id, status: "pending_approval"} — REQUIRES an existing asset with
     verified rights AND a completed render job whose output file exists.
  2. POST /api/publish/{job_id}/execute — the actual YouTube upload, only
     after operator review. FRIDAY NEVER calls this automatically.

So this tool is honestly a "queue a publish for approval" tool: it discovers
assets/renders via GET /api/assets + GET /api/jobs, queues the job, and
reports the pending-approval state. The D-015 two-gate (owner phrase + env
flag) still governs non-private publishes; the execute step stays a separate,
explicit VyralX operator action.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


#: Owner-authorization flag. Queuing a non-private publish is BLOCKED unless
#: this is literally "true" in the environment — same two-gate shape as
#: Stratex (D-015).
PROD_PUBLISH_ENV = "FRIDAY_VYRALX_PUBLISH_PROD_ALLOWED"

#: The phrase the owner must say for a public/unlisted publish (D-015 shape).
PROD_CONFIRM_PHRASE = "publish to youtube"


class VyralXPublishTool(BaseTool):
    """Queue a VyralX publish job for approval (YouTube draft pipeline)."""

    name = "vyralx_publish"
    description = (
        "Queue a YouTube publish job through VyralX's REAL publish pipeline. "
        "VyralX requires an asset with verified rights AND a completed render "
        "job — this tool discovers them (say 'list vyralx assets' or pass "
        "asset_id/render_job_id), then queues the publish via POST /api/publish. "
        "The job lands in pending_approval; the actual upload only happens when "
        "the operator calls the execute endpoint — FRIDAY never does that "
        "automatically. Private drafts need no extra gate; public/unlisted "
        "requires the owner phrase 'publish to youtube' AND the env flag "
        "(same two-gate guard as live trading, D-015)."
    )
    safety_level = SafetyLevel.SAFE  # default draft; public path re-classifies
    timeout = 90.0
    parameters = {
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "integer",
                "description": "VyralX asset ID (from 'list vyralx assets'); 0 to auto-pick the newest rights-verified asset.",
            },
            "render_job_id": {
                "type": "integer",
                "description": "Completed render job ID for that asset; 0 to auto-pick.",
            },
            "title": {
                "type": "string",
                "description": "YouTube title (1-100 chars).",
            },
            "description": {
                "type": "string",
                "description": "YouTube description (optional; stock attribution is appended by VyralX).",
            },
            "privacy_status": {
                "type": "string",
                "enum": ["private", "unlisted", "public"],
                "description": "'private' (default — draft review) or 'unlisted'/'public' (gated by D-015).",
                "default": "private",
            },
            "confirm_phrase": {
                "type": "string",
                "description": "Required only for unlisted/public; must be the exact owner phrase 'publish to youtube'.",
            },
            "list_only": {
                "type": "boolean",
                "description": "True to only list assets + their completed renders (no publish queued).",
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
        render_job_id: int = 0,
        title: str = "",
        description: str = "",
        privacy_status: str = "private",
        confirm_phrase: str = "",
        list_only: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        privacy = (privacy_status or "private").lower()
        if privacy not in ("private", "unlisted", "public"):
            privacy = "private"

        # ── D-015 fail-closed gate for non-private publishes ────────────────
        if privacy in ("unlisted", "public"):
            if (confirm_phrase or "").strip().lower() != PROD_CONFIRM_PHRASE:
                return ToolResult(
                    name=self.name,
                    content=(
                        f"I won't queue a {privacy} publish, Boss. Non-private publishing is gated "
                        f"(same two-gate guard as live trading, D-015): say the exact phrase "
                        f"'{PROD_CONFIRM_PHRASE}' AND set {PROD_PUBLISH_ENV}=true in the environment. "
                        "Nothing was queued."
                    ),
                    is_error=True,
                    safety_level=SafetyLevel.DANGEROUS,
                    metadata={"gate": "confirm_phrase_missing"},
                )
            if os.getenv(PROD_PUBLISH_ENV, "").lower() != "true":
                return ToolResult(
                    name=self.name,
                    content=(
                        f"I have your confirmation phrase, but the owner-authorization flag "
                        f"{PROD_PUBLISH_ENV} is not set to 'true' in the environment. {privacy} publish is "
                        "blocked. Nothing was queued."
                    ),
                    is_error=True,
                    safety_level=SafetyLevel.DANGEROUS,
                    metadata={"gate": "env_flag_missing"},
                )

        try:
            result = asyncio.run(
                self._publish(
                    asset_id=int(asset_id or 0),
                    render_job_id=int(render_job_id or 0),
                    title=title,
                    description=description,
                    privacy=privacy,
                    list_only=bool(list_only),
                )
            )
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            return ToolResult(
                name=self.name,
                content=f"📤 [VYRALX PUBLISH] I couldn't complete the publish flow: {exc}. Nothing was queued.",
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
            content=str(result.get("reply", "Queued.")),
            safety_level=SafetyLevel.DANGEROUS if privacy != "private" else SafetyLevel.SAFE,
            metadata=result.get("metadata", {}),
        )

    async def _publish(
        self,
        *,
        asset_id: int,
        render_job_id: int,
        title: str,
        description: str,
        privacy: str,
        list_only: bool,
    ) -> dict[str, Any]:
        """Discover assets/renders via the REAL VyralX API, then queue the
        publish job through the REAL POST /api/publish contract."""
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

        async def _get(path: str) -> tuple[int, Any]:
            shared = client.get_shared_client()
            resp = await shared.get(f"{client.vyralx_url}{path}", headers=headers, timeout=20.0)
            try:
                return resp.status_code, (resp.json() if resp.text else None)
            except Exception:
                return resp.status_code, None

        # ── Step 1: discover assets (GET /api/assets) ───────────────────────
        try:
            status, assets = await _get("/api/assets")
        except Exception as exc:
            await breaker.record_failure(exc)
            return {
                "reply": (
                    f"📤 [VYRALX PUBLISH] I couldn't reach VyralX to list assets: {type(exc).__name__}: {exc}. "
                    "Nothing was queued."
                ),
                "metadata": {"agent_id": "vyralx", "error": str(exc)},
                "success": False,
            }
        if status != 200 or not isinstance(assets, list):
            if status >= 500:
                await breaker.record_failure()
            return {
                "reply": f"📤 [VYRALX PUBLISH] VyralX assets list answered HTTP {status} — I can't discover assets to publish. That is the real outcome.",
                "metadata": {"agent_id": "vyralx", "error": f"assets_http_{status}"},
                "success": False,
            }
        usage_tracker.record("vyralx", calls=1)

        if not assets:
            return {
                "reply": (
                    "📤 [VYRALX PUBLISH] VyralX has no assets yet, Boss. The publish pipeline needs an "
                    "uploaded asset with verified rights and a completed render first — nothing to publish."
                ),
                "metadata": {"agent_id": "vyralx", "assets": 0},
                "success": True,
            }

        # Pick the asset: explicit id, else the newest rights-verified one.
        chosen = None
        if asset_id:
            chosen = next((a for a in assets if a.get("id") == asset_id), None)
            if chosen is None:
                return {
                    "reply": f"📤 [VYRALX PUBLISH] Asset {asset_id} does not exist in VyralX. Say 'list vyralx assets' to see what's available.",
                    "metadata": {"agent_id": "vyralx", "error": "asset_not_found"},
                    "success": False,
                }
        else:
            verified = [a for a in assets if a.get("rights_verified") is True]
            chosen = verified[0] if verified else None
            if chosen is None:
                return {
                    "reply": (
                        "📤 [VYRALX PUBLISH] None of VyralX's assets have verified rights, Boss — the publish "
                        "pipeline refuses them (403 by design). Verify the source rights on VyralX first."
                    ),
                    "metadata": {"agent_id": "vyralx", "error": "no_rights_verified_assets"},
                    "success": False,
                }

        # ── Step 2: find a completed render for the asset ───────────────────
        try:
            r_status, render_jobs = await _get("/api/render")
        except Exception as exc:
            await breaker.record_failure(exc)
            render_jobs, r_status = None, 0
        render = None
        if r_status == 200 and isinstance(render_jobs, list):
            jobs = [j for j in render_jobs if isinstance(j, dict) and (not render_job_id or j.get("id") == render_job_id)]
            completed = [j for j in jobs if isinstance(j, dict) and j.get("status") == "completed"
                         and j.get("asset_id") == chosen["id"] and j.get("output_path")]
            render = completed[0] if completed else None
        if render is None and render_job_id:
            return {
                "reply": f"📤 [VYRALX PUBLISH] Render job {render_job_id} is not a completed render for asset {chosen['id']}. The publish pipeline only accepts completed renders.",
                "metadata": {"agent_id": "vyralx", "error": "render_not_completed"},
                "success": False,
            }

        # ── Step 3 (list-only / no-render mode): report and stop ────────────
        if list_only or render is None:
            lines = [f"📤 [VYRALX PUBLISH] VyralX assets ({len(assets)} newest):"]
            for a in assets[:8]:
                rights = "rights ✓" if a.get("rights_verified") else "rights ✗"
                lines.append(f"  • Asset {a.get('id')}: {a.get('title', 'untitled')} ({a.get('duration_seconds', '?')}s, {rights})")
            if render is None and not list_only:
                lines.append(
                    f"No completed render found for asset {chosen['id']} — queue a render first "
                    "(vyralx_render / POST /api/render). Nothing was queued."
                )
            else:
                lines.append("List-only mode: nothing was queued.")
            return {
                "reply": "\n".join(lines),
                "metadata": {"agent_id": "vyralx", "assets": len(assets), "list_only": True},
                "success": True,
            }

        # ── Step 4: queue the publish (POST /api/publish) ───────────────────
        final_title = (title or str(chosen.get("title") or "")).strip()[:100]
        if not final_title:
            return {
                "reply": "I need a title for the YouTube publish, Boss (1-100 chars). Nothing was queued.",
                "metadata": {"agent_id": "vyralx", "error": "title_missing"},
                "success": False,
            }
        payload = {
            "asset_id": chosen["id"],
            "render_job_id": render["id"],
            "title": final_title,
            "description": (description or "")[:5000],
            "tags": [],
            "privacy_status": privacy,
            "confirm_rights": True,
        }
        try:
            shared = client.get_shared_client()
            resp = await shared.post(
                f"{client.vyralx_url}/api/publish",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
        except Exception as exc:
            await breaker.record_failure(exc)
            return {
                "reply": f"📤 [VYRALX PUBLISH] I couldn't reach VyralX to queue the publish: {type(exc).__name__}. Submission is unconfirmed; check publish status before retrying.",
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
                    f"📤 [VYRALX PUBLISH] VyralX refused the publish request (HTTP {resp.status_code}"
                    + (f": {detail}" if detail else "")
                    + "). That is the real outcome — nothing was queued."
                ),
                "metadata": {"agent_id": "vyralx", "error": f"publish_http_{resp.status_code}"},
                "success": False,
            }
        await breaker.record_success()
        usage_tracker.record("vyralx", calls=2)

        data = resp.json() if resp.text else {}
        if not isinstance(data, dict):
            return {"success": False, "reply": "Invalid VyralX acknowledgement; submission is unconfirmed. Check job history before retrying.",
                    "metadata": {"error": "invalid_job_receipt", "submission_unconfirmed": True}}
        job_id = data.get("job_id")
        job_status = data.get("status")
        if not isinstance(job_id, int) or isinstance(job_id, bool) or job_id <= 0 or job_status not in {'pending_approval'}:
            return {"success": False,
                    "reply": "VyralX returned an invalid publish acknowledgement. Submission is unconfirmed; inspect the job list before retrying.",
                    "metadata": {"agent_id": "vyralx", "error": "invalid_job_receipt", "submission_unconfirmed": True}}
        lines = [
            "📤 [VYRALX PUBLISH] Publish job queued for approval:",
            f"• Asset: {chosen.get('title', chosen['id'])} (asset_id={chosen['id']})",
            f"• Render: job {render['id']} (completed)",
            f"• Title: {final_title} | Privacy: {privacy}",
            f"• Job: {job_id} — status: {job_status}",
        ]
        lines.append(
            "PENDING APPROVAL — the upload only happens when the operator calls the execute endpoint "
            "after reviewing the render and metadata. FRIDAY never executes it automatically."
        )
        return {
            "reply": "\n".join(lines),
            "metadata": {
                "agent_id": "vyralx",
                "agent_name": "VyralX",
                "job_id": job_id,
                "job_status": job_status,
                "asset_id": chosen["id"],
                "render_job_id": render["id"],
                "privacy": privacy,
            },
            "success": True,
        }
