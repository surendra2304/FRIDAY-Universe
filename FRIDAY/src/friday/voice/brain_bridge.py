"""The deployed LiveKit worker's connection to the canonical FRIDAY brain.

No second tool registry or memory store, no automatic POST retries, no owner
credential minted by the microphone. The origin-only chat route must retain
boss_verified=False. Transport uncertainty is never reported as non-execution.
"""
from __future__ import annotations

from typing import Any

import httpx

BRAIN_URL = "http://127.0.0.1:10000/api/chat"
BRAIN_ORIGIN = "http://127.0.0.1:10000"


class VoiceBrainBridge:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def execute(self, request: str) -> dict[str, Any]:
        text = (request or "").strip()
        if not text or len(text) > 4000:
            return {"state": "refused", "spoken_reply": "Please give me a request between 1 and 4000 characters. Nothing was submitted."}
        try:
            if self.client is None:
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                    return await self._send(client, text)
            return await self._send(self.client, text)
        except httpx.HTTPError:
            return {"state": "unconfirmed", "spoken_reply": "I lost contact with FRIDAY's brain. The outcome is unconfirmed. Please check the task history before repeating an action."}

    async def _send(self, client: httpx.AsyncClient, text: str) -> dict[str, Any]:
        # The same endpoint used by chat performs memory retrieval, authorization,
        # task dispatch and conversation persistence. No control token is passed.
        async with client.stream("POST", BRAIN_URL, json={"message": text},
                                 headers={"Origin": BRAIN_ORIGIN}, timeout=230.0) as response:
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 65536:
                    return {"state": "unconfirmed", "spoken_reply": "FRIDAY returned an oversized answer. Please inspect the task history; I cannot confirm the outcome by voice."}
            try:
                import json
                body = json.loads(content)
            except (ValueError, UnicodeError):
                body = None
            code = response.status_code
        if not isinstance(body, dict) or not isinstance(body.get("reply"), str) or not body["reply"].strip():
            return {"state": "unconfirmed", "spoken_reply": "FRIDAY did not return a usable answer. I cannot confirm task completion."}
        meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        task_state = str(meta.get("task_state", "")).upper()
        if code in {401, 403} or meta.get("refused") or meta.get("security_blocked"):
            state = "refused"
        elif code == 202 or meta.get("pending") is True or task_state in {"PENDING", "RUNNING", "WAITING_APPROVAL"}:
            state = "pending"
        elif code >= 400 or meta.get("execution_failed") or meta.get("error") or meta.get("success") is False or meta.get("probe_success") is False or meta.get("memory_store") is False or task_state == "FAILED":
            state = "failed"
        else:
            # An answer is not a claim that an external action completed.
            state = "answered"
        spoken = meta.get("spoken_summary") if state == "answered" else None
        if not isinstance(spoken, str) or not spoken.strip():
            spoken = body["reply"]
        return {"state": state, "spoken_reply": spoken[:6000],
                "full_reply": body["reply"], "task_state": task_state,
                "task_id": meta.get("task_id"), "completion_verified": False}


def build_voice_tools(bridge: VoiceBrainBridge | None = None) -> list:
    """Register against the real LiveKit SDK; defer SDK import for light tests."""
    from livekit.agents import function_tool

    brain = bridge or VoiceBrainBridge()

    @function_tool(name="execute_friday_task", description=(
        "Send the user's complete request to FRIDAY's canonical brain. REQUIRED for "
        "remembering/recalling preferences, sourced research, code build/test, video "
        "draft/render/status/approval, and fleet status. Read spoken_reply faithfully; "
        "never turn pending/refused/failed/unconfirmed into success. Never upload or "
        "publish automatically; approval remains a separate owner action."))
    async def execute_friday_task(request: str) -> dict[str, Any]:
        return await brain.execute(request)

    return [execute_friday_task]
