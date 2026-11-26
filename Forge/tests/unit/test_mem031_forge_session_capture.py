"""
TASK-MEM-031 — Forge session-event capture tests (claude-mem leg).

Locks ``MemoraClient.record_session_event`` / ``a_record_session_event``
(Forge/app/integrations/memora_client.py): the session event is POSTed
to Memora's ``/v1/capture/events`` with the session id, kind and content;
empty content is refused without an HTTP call; a cloud failure falls
back to the Oracle MEMORA_OUTBOX spool; with no outbox the failure is
reported, never raised.

Runs in the Forge tier-1 CI step (listed in
.github/workflows/friday-universe-ci.yml).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.memora_client import MemoraClient


def _make_client():
    return MemoraClient(
        base_url="https://memora-cloud.example.com",
        api_key="memora_test_key",
    )


@pytest.mark.asyncio
async def test_a_record_session_event_cloud_mock():
    """The async path POSTs the session event to /v1/capture/events."""
    client = _make_client()

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = {
        "stored": True,
        "id": "evt-1",
        "needle_kind": "decision",
        "session_id": "forge-build-t1",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_http_resp
        res = await client.a_record_session_event(
            session_id="forge-build-t1",
            kind="decision",
            content="Decided to keep the async pool at 20 workers.",
            task_id="t1",
        )

    assert res["stored"] is True
    assert res["id"] == "evt-1"
    assert res["needle_kind"] == "decision"
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/v1/capture/events")
    assert kwargs["json"]["session_id"] == "forge-build-t1"
    assert kwargs["json"]["kind"] == "decision"
    assert kwargs["json"]["content"] == "Decided to keep the async pool at 20 workers."
    assert kwargs["json"]["task_id"] == "t1"


def test_record_session_event_cloud_mock_sync():
    """The sync path POSTs the same payload over urllib."""
    client = _make_client()

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {"stored": True, "id": "evt-2", "needle_kind": "observation"}
    ).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        res = client.record_session_event(
            session_id="forge-build-t2",
            content="Synthesized files: a.py (fallback: [])",
            task_id="t2",
        )

    assert res["stored"] is True
    assert res["id"] == "evt-2"
    req = mock_open.call_args[0][0]
    assert req.full_url.endswith("/v1/capture/events")
    payload = json.loads(req.data)
    assert payload["session_id"] == "forge-build-t2"
    assert payload["kind"] == "observation"
    assert payload["task_id"] == "t2"


@pytest.mark.asyncio
async def test_a_record_session_event_falls_back_to_outbox():
    """A cloud failure spools the event into the Oracle outbox."""
    client = MemoraClient(
        base_url="http://invalid-host-unreachable.example.com",
        api_key="memora_test_key",
    )
    outbox = MagicMock()
    outbox.record.return_value = "outbox-1"
    client._oracle_outbox = outbox

    res = await client.a_record_session_event(
        session_id="forge-build-t3",
        kind="bugfix",
        content="Build failed: fallback stub generated.",
    )

    assert res == {"id": "outbox-1", "status": "persisted_locally"}
    _, kwargs = outbox.record.call_args
    assert kwargs["source"] == "session_capture"
    assert kwargs["memory_type"] == "episodic"
    assert "forge-build-t3" in kwargs["content_text"]
    assert "bugfix" in kwargs["content_text"]


@pytest.mark.asyncio
async def test_a_record_session_event_refuses_empty_content():
    """Empty content is refused without any HTTP call."""
    client = _make_client()
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        res = await client.a_record_session_event(session_id="forge-build-t4", content="   ")
    assert res["status"] == "error"
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_a_record_session_event_requires_session_id():
    """A missing session id is refused without any HTTP call."""
    client = _make_client()
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        res = await client.a_record_session_event(session_id="", content="Build finished.")
    assert res["status"] == "error"
    mock_post.assert_not_called()


def test_record_session_event_no_outbox_reports_error():
    """With no cloud and no outbox the failure is reported, not raised."""
    client = MemoraClient(
        base_url="http://invalid-host-unreachable.example.com",
        api_key="memora_test_key",
    )
    client._oracle_outbox = None
    res = client.record_session_event(session_id="forge-build-t5", content="Build finished.")
    assert res["status"] == "error"
    assert "not persisted" in res["error"]
