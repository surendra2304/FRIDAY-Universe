"""TASK-MEM-005-R2: Stratex's cloud-fallback Memora client must present
Stratex's OWN Memora credential.

Same defect family as the Futuris fallback fixed under TASK-MEM-005-R2:
`_request` resolved only ``STRATEX_API_KEY`` — Stratex's peer-API key —
and never ``STRATEX_MEMORA_API_KEY``, where the MEM-005 rotation placed
the live Memora registry value. The resolution chain must be the fleet
chain (shared SDK ``_agent_memora_key``, TASK-MEM-005-R1): dedicated
``{AGENT}_MEMORA_API_KEY`` first, the per-agent ``{AGENT}_API_KEY`` as
transition fallback, and ``MEMORA_API_KEY`` — Memora's own key — never.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "autonomy" / "memora_cloud_fallback.py"
)
_spec = importlib.util.spec_from_file_location("stratex_memora_cloud_fallback", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MemoraClient = _mod.MemoraClient

_ENV_NAMES = ("STRATEX_MEMORA_API_KEY", "STRATEX_API_KEY", "MEMORA_API_KEY")


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps({"ok": True}).encode()


@pytest.fixture
def captured(monkeypatch):
    """Stub urlopen; record every Request it receives."""
    requests = []

    def fake_urlopen(request, timeout=None):
        requests.append(request)
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return requests


def _client(monkeypatch, **env):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return MemoraClient(base_url="http://memora.test")


def _auth_header(request):
    return request.get_header("Authorization")


def test_dedicated_memora_key_wins(monkeypatch, captured):
    client = _client(
        monkeypatch,
        STRATEX_MEMORA_API_KEY="stratex-dedicated-key",
        STRATEX_API_KEY="stratex-peer-key",
        MEMORA_API_KEY="memora-shared-key",
    )
    result = client.read_event_cursor("stratex")
    assert result.get("ok") is True
    assert len(captured) == 1
    assert _auth_header(captured[0]) == "Bearer stratex-dedicated-key"


def test_peer_key_is_only_the_fallback(monkeypatch, captured):
    client = _client(
        monkeypatch,
        STRATEX_API_KEY="stratex-peer-key",
        MEMORA_API_KEY="memora-shared-key",
    )
    result = client.read_event_cursor("stratex")
    assert result.get("ok") is True
    assert len(captured) == 1
    assert _auth_header(captured[0]) == "Bearer stratex-peer-key"


def test_shared_memora_key_is_never_presented(monkeypatch, captured):
    client = _client(monkeypatch, MEMORA_API_KEY="memora-shared-key")
    result = client.read_event_cursor("stratex")
    assert result["status"] == "error"
    assert client.last_error == "STRATEX_API_KEY is not configured"
    assert captured == []


def test_explicit_api_key_still_wins(monkeypatch, captured):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STRATEX_MEMORA_API_KEY", "stratex-dedicated-key")
    monkeypatch.setenv("STRATEX_API_KEY", "stratex-peer-key")
    client = MemoraClient(base_url="http://memora.test", api_key="explicit-key")
    result = client.read_event_cursor("stratex")
    assert result.get("ok") is True
    assert len(captured) == 1
    assert _auth_header(captured[0]) == "Bearer explicit-key"
