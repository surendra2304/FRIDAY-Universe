"""Review-only topic-to-video projects; never infer a media license or publish.

The project key is stable for identical requests. A missing backend review
contract blocks creation BEFORE posting: an old server may ignore new fields.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

LICENSE_CONFIRMATION = "I confirm I reviewed the Pexels license for this video"
PROJECT_WORDS = {"make a video about", "create a video about", "produce a video about",
                 "make a short about", "create a short about", "video project status"}


class VyralXProjectTool(BaseTool):
    name = "vyralx_project"
    description = (
        "Create a complete review-only topic-to-video project (script, licensed stock, "
        "narration, captions, render and thumbnail) or query 'video project status ID'. "
        "Pass the user's original request unchanged. Creation requires the user's explicit "
        f"sentence '{LICENSE_CONFIRMATION}'. Never supply that sentence on their behalf. "
        "This never grants repeat-use rights or permission to publish."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 55
    retry_policy = {"max_attempts": 1}
    idempotency = True
    side_effects = ["Queues a review-required video project after explicit license confirmation"]
    parameters = {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}

    def __init__(self, fleet_client: Any | None = None):
        super().__init__()
        self._fleet_client = fleet_client

    def execute(self, question: str = "", **kwargs) -> ToolResult:
        text = (question or "").strip()
        if not text or len(text) > 2000:
            return self._result("Give me a video topic or 'video project status ID'. No request was sent.", True)
        status_match = re.fullmatch(r"(?:check )?video project status(?:\s+(\d+))?[.!? ]*", text, re.I)
        payload = None
        if status_match:
            project_id = int(status_match.group(1)) if status_match.group(1) else None
            if project_id is not None and project_id < 1:
                return self._result("A project ID must be positive. No request was sent.", True)
        else:
            project_id = None
            # A separate sentence, not a substring of a negation, quote or explanation.
            sentences = [s.strip() for s in re.split(r"[.!?;\n]+", text) if s.strip()]
            if LICENSE_CONFIRMATION.lower() not in [s.lower() for s in sentences]:
                return self._result(
                    "Before I use stock footage, review https://www.pexels.com/license/ for your intended use. "
                    f"Then repeat your video request with the separate sentence: {LICENSE_CONFIRMATION}. "
                    "I have not queued anything. This is not permission to reuse clips or publish.",
                    pending=True)
            topic_request = " ".join(s for s in sentences if s.lower() != LICENSE_CONFIRMATION.lower())
            topic = re.sub(r"^(?:please\s+)?(?:make|create|produce)\s+a\s+(?:video|short)\s+about\s+", "", topic_request, flags=re.I).strip()
            if not 3 <= len(topic) <= 500:
                return self._result("Give me a video topic between 3 and 500 characters. Nothing was submitted.", True)
            key = "friday_review_" + hashlib.sha256(topic.encode()).hexdigest()[:32]
            payload = {"project_key": key, "topic": topic, "video_format": "shorts", "target_seconds": 45,
                       "scene_count": 4, "use_voiceover": True, "confirm_pexels_license": True,
                       "confirm_pexels_repeat_use": False, "review_required": True}
        try:
            return asyncio.run(self._request(project_id, payload))
        except Exception:
            # No exception text, credential-bearing URLs or automatic retry.
            return self._result("VyralX project outcome is unconfirmed. Check video project status before retrying.", True,
                                project_key=payload.get("project_key") if payload else None)

    def _result(self, content, error=False, pending=False, **meta):
        return ToolResult(name=self.name, content=content, is_error=error, safety_level=self.safety_level,
                          metadata={"agent_id": "vyralx", "pending": pending, "completion_verified": False, **meta})

    async def _request(self, project_id, payload):
        if self._fleet_client is None:
            from friday.ecosystem.fleet_client import FleetClient
            client = FleetClient()
        else:
            client = self._fleet_client
        if not getattr(client, "vyralx_url", ""):
            return self._result("VyralX is not configured. No request was sent.", True)
        breaker = client.get_circuit_breaker("vyralx")
        if not await breaker.can_execute():
            return self._result("VyralX circuit is open. No request was sent.", True)
        headers = {"X-API-Key": client.vyralx_key} if getattr(client, "vyralx_key", "") else {}
        shared = client.get_shared_client()
        base = client.vyralx_url.rstrip("/")
        if payload:
            manifest = await shared.get(base + "/api/agent/manifest", headers=headers, timeout=15)
            if manifest.status_code != 200:
                return self._result("Cannot verify VyralX's review-only contract. No project was submitted.", True)
            data = manifest.json()
            contract = data.get("project_review_contract") if isinstance(data, dict) else None
            if not (isinstance(contract, dict) and type(contract.get("version")) is int and contract["version"] == 1
                    and contract.get("persistent_review_required") is True and contract.get("blocks_autonomous_publish") is True):
                return self._result("This VyralX version cannot guarantee review-only projects. Nothing was submitted.", True)
            response = await shared.post(base + "/api/projects", json=payload, headers=headers, timeout=30)
        else:
            path = f"/api/projects/{project_id}" if project_id else "/api/projects"
            response = await shared.get(base + path, headers=headers, timeout=20)
        if response.status_code not in (200, 202):
            return self._result(f"VyralX returned HTTP {response.status_code}. No completion is being claimed; check project status before retrying.", True)
        data = response.json()
        if payload is None and project_id is None:
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                return self._result("Invalid project status response; no completion is confirmed.", True)
            rows = data["items"][:8]
        else:
            rows = [data]
        lines = []
        pending = False
        failed = False
        for row in rows:
            if not isinstance(row, dict) or type(row.get("project_id")) is not int or row["project_id"] < 1:
                return self._result("Invalid project acknowledgment. Outcome unconfirmed; check status before retrying.", True)
            state = row.get("status")
            if state not in {"queued", "running", "rendering", "completed", "failed"}:
                return self._result("Unknown project state; outcome unconfirmed. Check project status.", True)
            if project_id and row["project_id"] != project_id:
                return self._result("Project status ID mismatch. Outcome unconfirmed.", True)
            if payload and (row.get("project_key") != payload["project_key"] or row.get("review_required") is not True):
                return self._result("Review-only project acknowledgment mismatch. Outcome unconfirmed; do not retry automatically.", True)
            if state == "completed":
                rid = row.get("render_job_id")
                if type(rid) is not int or rid < 1 or not row.get("render_download_path"):
                    return self._result("Project says completed but lacks a reviewable render reference. Completion is unverified.", True)
            pending |= state in {"queued", "running", "rendering"}
            failed |= state == "failed"
            line = f"Video project {row['project_id']}: {state}."
            if state == "completed":
                line += f" Render {row['render_job_id']} is available for review at {row['render_download_path']}."
            lines.append(line)
        await breaker.record_success()
        content = "\n".join(lines) if lines else "No video projects were returned."
        content += "\nNo publish approval is granted by this request. Review the video and rights before requesting publication."
        return self._result(content, failed, pending=pending, project_key=payload.get("project_key") if payload else None,
                            projects=rows)
