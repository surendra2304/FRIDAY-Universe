"""Wire-level regressions for the owner's four workflows, not simplified statuses.

External providers are NOT contacted. Real FleetClient + httpx transport,
TaskResult enum/envelope shapes, actual LiveKit SDK registration, canonical
chat-authority propagation and video queue contracts are exercised.
"""
from __future__ import annotations

import asyncio
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from friday.core.config import Settings
from friday.core.task_envelope import TaskResult, TaskStatus
from friday.ecosystem.fleet_client import FleetClient
from friday.tools.builtin.forge_code_task import ForgeCodeTool
from friday.tools.builtin.intelx_research import IntelXResearchTool
from friday.tools.builtin.vyralx_render import VyralXRenderTool
from friday.tools.builtin.vyralx_publish import VyralXPublishTool
from friday.voice.brain_bridge import VoiceBrainBridge, build_voice_tools

ROOT = Path(__file__).resolve().parents[2]


class WireFleet(FleetClient):
    def __init__(self, handler):
        super().__init__(settings=Settings(env="testing", memory_backend="in_memory",
                                          intelx_url="http://intelx.test", forge_url="http://forge.test",
                                          vyralx_url="http://vyralx.test", vyralx_api_key="test-only"))
        self.transport = httpx.MockTransport(handler)

    def get_shared_client(self):
        # Tools are synchronous adapters using asyncio.run. Each test invokes
        # once and closes the transport; no cross-event-loop pooled connections.
        if self._shared_client is None:
            self._shared_client = httpx.AsyncClient(transport=self.transport)
        return self._shared_client


def receipt(action, agent):
    return {"requested_action": action, "target": agent, "authorization_decision": "AUTHORIZED",
            "verification_evidence": {"fixture": "explicit wire-contract mock"}}


def test_research_real_enum_and_double_envelope():
    seen = []
    def handler(req):
        body = json.loads(req.content);seen.append(body)
        assert req.url.path == "/v1/task/execute"
        assert req.extensions["timeout"]["read"] == 115
        return httpx.Response(200, json={"task_id": body["task_id"], "target_agent": "intelx",
            "status": "SUCCESS", "result": {"query": "test question", "text_response": "Evidence from fixture.",
                "spoken_summary": "A sourced answer.", "citations_count": 1,
                "sources": [{"title": "Official documentation", "url": "https://example.org/evidence"}]},
            "receipt": receipt("research_live", "intelx")})
    result = IntelXResearchTool(WireFleet(handler)).execute(query="test question")
    assert not result.is_error, result.content
    assert seen[0]["action"] == "research_live"
    assert "Evidence from fixture." in result.content
    assert "https://example.org/evidence" in result.content
    assert result.metadata["spoken_summary"] == "A sourced answer."


def test_fresh_research_never_falls_back_to_old_status():
    seen = []
    def handler(req):
        seen.append(req.url.path)
        return httpx.Response(404, json={"detail": "not deployed"})
    result = IntelXResearchTool(WireFleet(handler)).execute(query="test question")
    assert result.is_error
    assert seen == ["/v1/task/execute"]


def test_forge_real_enum_manifest_and_longer_timeout():
    def handler(req):
        body = json.loads(req.content)
        assert body["payload"]["execute_now"] is True
        assert req.extensions["timeout"]["read"] == 210
        manifest = {"all_passed": True, "total_stages": 2, "passed_stages": 2,
                    "stages": {"build": {"passed": True}, "unit_tests": {"passed": True}}}
        return httpx.Response(200, json={"task_id": body["task_id"], "target_agent": "forge", "status": "SUCCESS",
            "result": {"forge_task_id": "f-fixture", "state": "completed", "manifest": manifest},
            "verification_manifest": manifest, "receipt": receipt("build", "forge")})
    result = ForgeCodeTool(WireFleet(handler)).execute(goal="build a CSV converter and test it")
    assert not result.is_error, result.content
    assert "2/2 stages passed" in result.content
    assert result.metadata["verification_manifest"]["all_passed"] is True


def test_failed_manifest_never_becomes_success():
    peer = SimpleNamespace(dispatch_task=AsyncMock(return_value=TaskResult(task_id="x", target_agent="forge",
        status=TaskStatus.SUCCESS, result={"manifest": {"all_passed": False, "failed_stages": 1}})))
    result = ForgeCodeTool(peer).execute(goal="build something")
    assert result.is_error
    assert "not verified" in result.content


def test_voice_transport_uses_same_chat_without_owner_credentials():
    seen = []
    async def run():
        def handler(req):
            seen.append(req)
            assert req.url == "http://127.0.0.1:10000/api/chat"
            assert req.headers["origin"] == "http://127.0.0.1:10000"
            assert "authorization" not in req.headers
            assert json.loads(req.content) == {"message": "remember I prefer masala chai"}
            return httpx.Response(200, json={"reply": "Saved by Memora.", "metadata": {"fast_path": True}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await VoiceBrainBridge(client).execute("remember I prefer masala chai")
            assert result["state"] == "answered"
            assert result["spoken_reply"] == "Saved by Memora."
            assert result["completion_verified"] is False
    asyncio.run(run())
    assert len(seen) == 1


@pytest.mark.parametrize("code,metadata,state", [
    (202, {"task_state": "PENDING"}, "pending"), (403, {"refused": True}, "refused"),
    (500, {"execution_failed": True}, "failed"), (200, {"probe_success": False}, "failed"),
    (200, {"task_state": "FAILED"}, "failed"),
])
def test_voice_preserves_failure_and_pending(code, metadata, state):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(code,
                json={"reply": "Real backend outcome", "metadata": metadata}))) as client:
            result = await VoiceBrainBridge(client).execute("research quantum batteries")
            assert result["state"] == state
            assert result["spoken_reply"] == "Real backend outcome"
    asyncio.run(run())


def test_voice_timeout_is_not_retried_or_called_not_executed():
    seen = []
    def handler(req):
        seen.append(req)
        raise httpx.ReadTimeout("fixture", request=req)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await VoiceBrainBridge(client).execute("build a small script")
            assert result["state"] == "unconfirmed"
            assert "before repeating" in result["spoken_reply"]
    asyncio.run(run())
    assert len(seen) == 1


@pytest.mark.parametrize("response", [httpx.Response(200, text="<html>"), httpx.Response(200, json={}),
                                        httpx.Response(200, text="x" * 65537)])
def test_voice_invalid_answers_are_unconfirmed(response):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
            result = await VoiceBrainBridge(client).execute("hello")
            assert result["state"] == "unconfirmed"
    asyncio.run(run())


def test_livekit_sdk_tool_registration_and_worker_wiring():
    # SDK optional in minimal CI; do NOT skip/assert green when missing. Contract
    # always runs via a tiny registration seam; real SDK also checked when installed.
    tools = build_voice_tools(VoiceBrainBridge())
    assert len(tools) == 1
    assert tools[0].info.name == "execute_friday_task"
    tree = ast.parse((ROOT / "FRIDAY/src/friday/voice/livekit_worker.py").read_text())
    agents = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Agent"]
    assert any(any(k.arg == "tools" for k in n.keywords) for n in agents)


def test_chat_does_not_mint_boss_authority(monkeypatch):
    from friday.api import server
    calls = []
    async def dispatch(command, *, boss_verified=False):
        calls.append(boss_verified)
        return {"reply": "test response", "metadata": {}}
    monkeypatch.setattr(server, "_dispatch_command", dispatch)
    monkeypatch.setattr(server, "_log_conversation", AsyncMock())
    asyncio.run(server.chat_endpoint(server.ChatRequest(message="enable autonomous mode")))
    assert calls == [False]
    calls.clear()
    asyncio.run(server.execute_command(server.CommandRequest(command="enable autonomous mode")))
    assert calls == [True]  # HTTP callers still must pass the endpoint's control dependency


def video_wire(*, render_status=200, render_payload=None, publish_payload=None, post_error=False):
    seen = []
    assets = [{"id": 10, "title": "Fixture asset", "rights_verified": True, "duration_seconds": 8}]
    jobs = render_payload if render_payload is not None else [
        {"id": 90, "asset_id": 99, "status": "completed", "output_path": "/other.mp4"},
        {"id": 91, "asset_id": 10, "status": "completed", "output_path": "/fixture.mp4"}]
    def handler(req):
        seen.append((req.method, req.url.path, json.loads(req.content) if req.content else None))
        if req.method == "GET" and req.url.path == "/api/assets":
            return httpx.Response(200, json=assets)
        if req.method == "GET" and req.url.path == "/api/render":
            return httpx.Response(render_status, json=jobs)
        if req.method == "POST":
            if post_error:
                raise httpx.ReadTimeout("fixture", request=req)
            return httpx.Response(202, json=publish_payload if publish_payload is not None else
                {"job_id": 7, "status": "pending_approval" if req.url.path == "/api/publish" else "queued"})
        return httpx.Response(404)
    return WireFleet(handler), seen


def test_video_approval_uses_real_render_route_and_exact_asset():
    client, seen = video_wire()
    result = VyralXPublishTool(client).execute(asset_id=10, title="Fixture")
    assert not result.is_error, result.content
    posts = [x for x in seen if x[0] == "POST"]
    assert posts[0][1] == "/api/publish"
    assert posts[0][2]["render_job_id"] == 91
    assert posts[0][2]["privacy_status"] == "private"
    assert result.metadata["job_status"] == "pending_approval"
    assert not any("execute" in x[1] or x[1] == "/api/jobs" for x in seen)


def test_video_wrong_asset_or_incomplete_render_cannot_publish():
    client, seen = video_wire(render_payload=[{"id": 91, "asset_id": 99, "status": "completed", "output_path": "/other.mp4"}])
    result = VyralXPublishTool(client).execute(asset_id=10, render_job_id=91, title="Fixture")
    assert result.is_error
    assert not any(x[0] == "POST" for x in seen)


@pytest.mark.parametrize("tool", [VyralXPublishTool, VyralXRenderTool])
@pytest.mark.parametrize("payload", [{}, {"job_id": True, "status": "queued"}, {"job_id": 1}, [], {"job_id": -1, "status": "queued"}])
def test_video_never_invents_job_acknowledgement(tool, payload):
    client, _ = video_wire(publish_payload=payload)
    result = tool(client).execute(asset_id=10)
    assert result.is_error, result.content
    assert "unconfirmed" in result.content


@pytest.mark.parametrize("tool", [VyralXPublishTool, VyralXRenderTool])
def test_video_post_timeout_does_not_claim_no_side_effect(tool):
    client, _ = video_wire(post_error=True)
    result = tool(client).execute(asset_id=10)
    assert result.is_error
    assert "unconfirmed" in result.content.lower()
    assert "Nothing was queued" not in result.content


@pytest.mark.parametrize("receipt,stored", [({}, False), ({"status": "skipped"}, False),
    ({"status": "error"}, False), ({"id": "mem-fixture"}, True), ({"status": "success"}, True)])
def test_canonical_memory_refuses_empty_and_skipped_receipts(monkeypatch, receipt, stored):
    from friday.api.server import _dispatch_command
    from friday.memory.memora_client import memora_client
    monkeypatch.setattr(memora_client, "record_fact", lambda **kw: receipt)
    result = asyncio.run(_dispatch_command("remember my favourite chai is masala chai"))
    assert result["metadata"]["memory_store"] is stored
    assert ("NOT saved" in result["reply"]) is (not stored)


def test_voice_memory_does_not_promote_empty_receipt_to_saved(monkeypatch):
    from friday.memory.memora_client import memora_client
    from friday.memory.voice_memory import handle_voice_memory
    monkeypatch.setattr(memora_client, "record_fact", lambda **kw: {})
    assert "NOT saved" in handle_voice_memory("remember I prefer masala chai")
    monkeypatch.setattr(memora_client, "record_fact", lambda **kw: {"status": "local_only", "id": "fixture"})
    reply = handle_voice_memory("remember I prefer masala chai")
    assert "local memory backend" in reply
    assert "synchronization is not confirmed" in reply


def test_voice_uses_research_spoken_summary_but_preserves_full_sources():
    async def run():
        body = {"reply": "Full sourced findings: https://example.org/source",
                "metadata": {"spoken_summary": "According to Example, this is the finding."}}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as client:
            result = await VoiceBrainBridge(client).execute("research the latest release")
            assert result["spoken_reply"] == body["metadata"]["spoken_summary"]
            assert "https://example.org/source" in result["full_reply"]
    asyncio.run(run())


@pytest.mark.parametrize("question", ["make a video about solar power",
    "make a video about solar power. I do not confirm I reviewed the Pexels license for this video",
    'make a video about solar power. Someone said "I confirm I reviewed the Pexels license for this video"'])
def test_video_project_never_invents_license_confirmation(question):
    from friday.tools.builtin.vyralx_project import VyralXProjectTool
    tool = VyralXProjectTool(WireFleet(lambda req: pytest.fail("must not send any HTTP request")))
    result = tool.execute(question=question)
    assert result.metadata["pending"] is True
    assert "have not queued" in result.content


def project_manifest():
    return {"project_review_contract": {"version": 1, "persistent_review_required": True,
                                        "blocks_autonomous_publish": True}}


def test_video_project_creation_requires_backend_contract_and_keeps_review_boundary():
    from friday.tools.builtin.vyralx_project import VyralXProjectTool, LICENSE_CONFIRMATION
    seen = []
    def handler(req):
        seen.append(req.url.path)
        if req.method == "GET":
            assert req.url.path == "/api/agent/manifest"
            return httpx.Response(200, json=project_manifest())
        assert req.url.path == "/api/projects"
        payload = json.loads(req.content)
        assert payload["review_required"] is True
        assert payload["confirm_pexels_license"] is True
        assert payload["confirm_pexels_repeat_use"] is False
        assert payload["topic"] == "solar power"
        return httpx.Response(202, json={**payload, "project_id": 18, "status": "queued"})
    result = VyralXProjectTool(WireFleet(handler)).execute(question=f"make a video about solar power. {LICENSE_CONFIRMATION}.")
    assert not result.is_error
    assert result.metadata["pending"] is True
    assert "completed" not in result.content
    assert seen == ["/api/agent/manifest", "/api/projects"]


@pytest.mark.parametrize("contract", [{}, {"project_review_contract": {"version": True}},
    {"project_review_contract": {"version": 1, "persistent_review_required": True, "blocks_autonomous_publish": False}}])
def test_old_video_backend_is_blocked_before_post(contract):
    from friday.tools.builtin.vyralx_project import VyralXProjectTool, LICENSE_CONFIRMATION
    def handler(req):
        assert req.method == "GET"
        return httpx.Response(200, json=contract)
    result = VyralXProjectTool(WireFleet(handler)).execute(question=f"make a video about solar power. {LICENSE_CONFIRMATION}.")
    assert result.is_error


@pytest.mark.parametrize("row", [None, {"project_id": True, "status": "queued"},
    {"project_id": 1, "status": "completed"}, {"project_id": 1, "status": "invented"}])
def test_video_project_bad_acknowledgment_is_unconfirmed(row):
    from friday.tools.builtin.vyralx_project import VyralXProjectTool, LICENSE_CONFIRMATION
    def handler(req):
        return httpx.Response(200, json=project_manifest() if req.method == "GET" else row)
    result = VyralXProjectTool(WireFleet(handler)).execute(question=f"make a video about solar power. {LICENSE_CONFIRMATION}.")
    assert result.is_error
    assert result.metadata["completion_verified"] is False


def test_video_project_post_timeout_has_stable_idempotency_key_and_no_retry():
    from friday.tools.builtin.vyralx_project import VyralXProjectTool, LICENSE_CONFIRMATION
    posts = []
    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json=project_manifest())
        posts.append(json.loads(req.content)["project_key"])
        raise httpx.ReadTimeout("explicit test fixture")
    question = f"make a video about solar power. {LICENSE_CONFIRMATION}."
    for _ in range(2):
        result = VyralXProjectTool(WireFleet(handler)).execute(question=question)
        assert result.is_error and "unconfirmed" in result.content
    assert len(posts) == 2 and posts[0] == posts[1]


def test_video_project_status_reads_exact_id_without_posting():
    from friday.tools.builtin.vyralx_project import VyralXProjectTool
    def handler(req):
        assert req.method == "GET" and req.url.path == "/api/projects/18"
        return httpx.Response(200, json={"project_id": 18, "status": "completed", "render_job_id": 20,
                                        "render_download_path": "/api/render/20/download", "review_required": True})
    result = VyralXProjectTool(WireFleet(handler)).execute(question="video project status 18")
    assert not result.is_error and not result.metadata["pending"]
    assert "available for review" in result.content


def test_topic_to_video_routes_to_real_project_tool_not_chat():
    from friday.routing.capability_router import CapabilityRouter
    router = CapabilityRouter()
    result = router.route_request("make a video about solar power")
    assert result.candidate_evaluations[0].required_tools == ["vyralx_project"]


@pytest.mark.parametrize("manifest", [{}, {"all_passed": True, "stages": {}},
    {"stages": {"build": {"passed": False, "status": "passed"}}},
    {"stages": {"build": {"passed": True, "exit_code": 1}}},
    {"stages": {"build": {"passed": True, "exit_code": True}}}])
def test_forge_success_envelope_cannot_replace_stage_evidence(manifest):
    class Client:
        async def dispatch_task(self, envelope):
            return TaskResult(task_id=envelope.task_id, target_agent="forge", status=TaskStatus.SUCCESS,
                              result={"verification_manifest": manifest})
    result = ForgeCodeTool(Client()).execute(goal="build and test a CSV converter")
    assert result.is_error and "unverified" in result.content


def test_canonical_project_fast_path_preserves_raw_user_confirmation(monkeypatch):
    from friday.agent.mixins.fast_paths import FastPathMixin
    from friday.tools.builtin.vyralx_project import VyralXProjectTool, LICENSE_CONFIRMATION
    from friday.core.types import ToolResult
    from friday.agent.state import TaskState
    from friday.memory.memora_client import memora_client
    monkeypatch.setattr(memora_client, "record_interaction_async", lambda **kw: None)
    captured = []
    def execute(self, question, **kw):
        captured.append(question)
        return ToolResult(name="vyralx_project", content="Project queued, not rendered", metadata={"pending": True})
    monkeypatch.setattr(VyralXProjectTool, "execute", execute)
    host = SimpleNamespace(state_machine=SimpleNamespace(transition_to=lambda *a, **k: None,
                           current_state=TaskState.COMPLETED),
                           memory=SimpleNamespace(add_message=lambda *a: None))
    raw = f"Make a video about Solar Power. {LICENSE_CONFIRMATION}."
    result = FastPathMixin._batch3_delegation_fast_path(host, raw, 0)
    assert captured == [raw]
    assert result.metadata["pending"] is True
    assert result.metadata["tool"] == "vyralx_project"


def test_voice_does_not_promote_queued_project_to_completed():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200,
            json={"reply": "Video project 18: queued.", "metadata": {"pending": True, "task_state": "COMPLETED"}}))) as client:
            result = await VoiceBrainBridge(client).execute("make a video about solar power")
            assert result["state"] == "pending" and result["completion_verified"] is False
    asyncio.run(run())


def test_canonical_memory_save_and_recall_survives_client_recreation(tmp_path, monkeypatch):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module
    path = str(tmp_path / "workflow-memory.db")
    first = module.MemoraClient(local_db_path=path, remote_enabled=False)
    monkeypatch.setattr(module, "memora_client", first)
    saved = asyncio.run(_dispatch_command("remember my favourite chai is masala chai"))
    assert saved["metadata"]["memory_store"] is True
    assert "local memory backend" in saved["reply"]
    first._executor.shutdown(wait=True)
    reopened = module.MemoraClient(local_db_path=path, remote_enabled=False)
    monkeypatch.setattr(module, "memora_client", reopened)
    try:
        recalled = asyncio.run(_dispatch_command("do you remember my chai preference"))
        assert "masala chai" in recalled["reply"]
        async def via_voice_bridge():
            async def canonical(req):
                body = json.loads(req.content)
                return httpx.Response(200, json=await _dispatch_command(body["message"]))
            async with httpx.AsyncClient(transport=httpx.MockTransport(canonical)) as client:
                answer = await VoiceBrainBridge(client).execute("do you remember my chai preference")
                assert "masala chai" in answer["spoken_reply"]
        asyncio.run(via_voice_bridge())
    finally:
        reopened._executor.shutdown(wait=True)


def test_live_csv_goal_reaches_forge_before_desktop_and_retains_evidence(monkeypatch):
    from friday.agent.mixins.fast_paths import FastPathMixin
    from friday.agent.state import TaskState
    from friday.core.types import ToolResult
    from friday.memory.memora_client import memora_client
    monkeypatch.setattr(memora_client, "record_interaction_async", lambda **kw: None)
    captured = []
    manifest = {"stages": {"unit_tests": {"passed": True, "exit_code": 0}}}
    def execute(self, goal, **kw):
        captured.append(goal)
        return ToolResult(name="forge_code_task", content="Fixture verification evidence", metadata={
            "forge": {"task_id": "fixture-build"}, "verification_manifest": manifest, "artifacts": ["csv2json.py"]})
    monkeypatch.setattr(ForgeCodeTool, "execute", execute)
    host = SimpleNamespace(state_machine=SimpleNamespace(transition_to=lambda *a, **k: None,
        current_state=TaskState.COMPLETED), memory=SimpleNamespace(add_message=lambda *a: None))
    raw = "write a Python CSV to JSON converter using only the standard library. Include unittest tests and run them."
    response = FastPathMixin._batch3_delegation_fast_path(host, raw, 0)
    assert captured == [raw]
    assert response.metadata["task_id"] == "fixture-build"
    assert response.metadata["verification_manifest"] == manifest
    assert response.metadata["artifacts"] == ["csv2json.py"]
    decision = __import__("friday.routing.capability_router", fromlist=["CapabilityRouter"]).CapabilityRouter().route_request(raw)
    assert any(c.required_tools == ["forge_code_task"] for c in decision.candidate_evaluations)


def test_explicit_forge_failure_preserves_cause_and_task_reference_without_receipt():
    def handler(req):
        return httpx.Response(200, json={"task_id": "actual-peer-fixture", "target_agent": "forge",
            "status": "PARTIAL_FAILURE", "summary": "Verification failed: generated test syntax error",
            "error": "SyntaxError in test_main.py", "verification_manifest": {"all_passed": False, "failed_stages": 1}})
    result = ForgeCodeTool(WireFleet(handler)).execute(goal="write a Python CSV converter")
    assert result.is_error
    assert "SyntaxError" in result.content
    assert result.metadata["forge"]["task_id"] == "actual-peer-fixture"
    assert result.metadata["verification_manifest"]["all_passed"] is False
    assert "no receipt" not in result.content
