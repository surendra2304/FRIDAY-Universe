"""TASK-MEM-005-R1 (fix pass): mesh transport presents the SENDER's own
Memora credential.

MeshTransport.publish() used to resolve the MEMORA target's credential from
the shared MEMORA_API_KEY env var — Memora's own key, presented under
whatever X-Agent-From the envelope carried. The transport's only sender
identity is envelope.from_agent, so the Memora credential now resolves from
the sender's own chain: {SENDER}_MEMORA_API_KEY -> {SENDER}_API_KEY.
"""

import asyncio

import pytest

from mesh.envelope import AgentEnvelope
from mesh.transport import AGENT_AUTH_MAP, MeshTransport, _sender_memora_key

_CHAIN_ENVS = (
    "MEMORA_API_KEY",
    "FRIDAY_MEMORA_API_KEY",
    "FRIDAY_API_KEY",
    "STRATEX_API_KEY",
    "MEMORA_URL",
    "STRATEX_URL",
    "MESH_SIGNING_SECRET",
    "FRIDAY_MESH_SIGNING_SECRET",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _CHAIN_ENVS:
        monkeypatch.delenv(name, raising=False)


def test_auth_map_memora_is_sender_resolved():
    assert AGENT_AUTH_MAP["MEMORA"][1] is None


def test_sender_key_dedicated_wins(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    monkeypatch.setenv("FRIDAY_API_KEY", "friday-own")
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    assert _sender_memora_key("FRIDAY") == "friday-dedicated"
    assert _sender_memora_key("friday") == "friday-dedicated"


def test_sender_key_fallback_and_shared_ignored(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    monkeypatch.setenv("FRIDAY_API_KEY", "friday-own")
    assert _sender_memora_key("FRIDAY") == "friday-own"


def test_sender_key_absent_when_only_shared_set(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    assert _sender_memora_key("FRIDAY") == ""
    assert _sender_memora_key("") == ""


class _Resp:
    status_code = 200


class _FakeClient:
    captured = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        _FakeClient.captured = {"url": url, "headers": headers, "json": json}
        return _Resp()


def _publish(monkeypatch, from_agent, to_agent):
    _FakeClient.captured = None
    monkeypatch.setattr("mesh.transport.httpx.AsyncClient", _FakeClient)
    transport = MeshTransport()
    envelope = AgentEnvelope(
        from_agent=from_agent, to_agent=to_agent, intent="record", payload={}
    )
    return asyncio.run(transport.publish(envelope))


def test_publish_to_memora_presents_sender_credential(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    result = _publish(monkeypatch, "FRIDAY", "MEMORA")
    assert result["status"] == "ACCEPTED_HTTP"
    assert _FakeClient.captured["headers"]["Authorization"] == "Bearer friday-dedicated"
    assert _FakeClient.captured["headers"]["X-Agent-From"] == "FRIDAY"


def test_publish_to_memora_blocks_without_sender_credential(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    result = _publish(monkeypatch, "FRIDAY", "MEMORA")
    assert result["status"] == "BLOCKED_MISSING_CREDENTIAL"
    assert result["credential_env"] == "FRIDAY_MEMORA_API_KEY"
    assert _FakeClient.captured is None


def test_publish_to_other_agent_unchanged(monkeypatch):
    monkeypatch.setenv("STRATEX_API_KEY", "stratex-key")
    result = _publish(monkeypatch, "FRIDAY", "STRATEX")
    assert result["status"] == "ACCEPTED_HTTP"
    assert _FakeClient.captured["headers"]["Authorization"] == "Bearer stratex-key"
