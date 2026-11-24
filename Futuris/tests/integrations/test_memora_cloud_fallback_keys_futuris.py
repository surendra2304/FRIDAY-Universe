"""TASK-MEM-005-R2: Futuris's cloud-fallback Memora client must present
Futuris's OWN Memora credential.

The fallback client's `_request` historically resolved only
``FUTURIS_API_KEY`` — Futuris's peer-API key. While the peer key equalled
the Memora registry value that worked; after the MEM-005 rotation the
registry value lives only in ``FUTURIS_MEMORA_API_KEY``, so the event
consumer (``memora_event_consumer`` -> ``read_event_cursor``/``poll_events``)
401-looped. The resolution chain must be the fleet chain (shared SDK
``_agent_memora_key``, TASK-MEM-005-R1): dedicated ``{AGENT}_MEMORA_API_KEY``
first, the per-agent ``{AGENT}_API_KEY`` as transition fallback, and
``MEMORA_API_KEY`` — Memora's own key — never.

TASK-INT-037 adds the 401 guard on top of that chain: a 401 on the
presented key retries the same request ONCE with the next key in the chain
and logs a loud warning naming the rejected key, so a stale dedicated key
fails one poll loudly instead of 401-looping every poll (FUT-022 storm:
174 cursor 401s in 45 min). No third key, no second retry.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import urllib.error
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "futuris"
    / "integrations"
    / "memora_cloud_fallback.py"
)
_spec = importlib.util.spec_from_file_location("futuris_memora_cloud_fallback", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MemoraClient = _mod.MemoraClient

_ENV_NAMES = ("FUTURIS_MEMORA_API_KEY", "FUTURIS_API_KEY", "MEMORA_API_KEY")


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
        FUTURIS_MEMORA_API_KEY="futuris-dedicated-key",
        FUTURIS_API_KEY="futuris-peer-key",
        MEMORA_API_KEY="memora-shared-key",
    )
    result = client.read_event_cursor("futuris")
    assert result.get("ok") is True
    assert len(captured) == 1
    assert _auth_header(captured[0]) == "Bearer futuris-dedicated-key"


def test_peer_key_is_only_the_fallback(monkeypatch, captured):
    client = _client(
        monkeypatch,
        FUTURIS_API_KEY="futuris-peer-key",
        MEMORA_API_KEY="memora-shared-key",
    )
    result = client.read_event_cursor("futuris")
    assert result.get("ok") is True
    assert len(captured) == 1
    assert _auth_header(captured[0]) == "Bearer futuris-peer-key"


def test_shared_memora_key_is_never_presented(monkeypatch, captured):
    client = _client(monkeypatch, MEMORA_API_KEY="memora-shared-key")
    result = client.read_event_cursor("futuris")
    assert result["status"] == "error"
    assert client.last_error == "FUTURIS_API_KEY is not configured"
    assert captured == []


def test_explicit_api_key_still_wins(monkeypatch, captured):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FUTURIS_MEMORA_API_KEY", "futuris-dedicated-key")
    monkeypatch.setenv("FUTURIS_API_KEY", "futuris-peer-key")
    client = MemoraClient(base_url="http://memora.test", api_key="explicit-key")
    result = client.read_event_cursor("futuris")
    assert result.get("ok") is True
    assert len(captured) == 1
    assert _auth_header(captured[0]) == "Bearer explicit-key"


def test_dedicated_key_401_retries_once_with_peer_key(monkeypatch, caplog):
    """TASK-INT-037: a 401 on the dedicated key retries once with the peer key."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = _client(
        monkeypatch,
        FUTURIS_MEMORA_API_KEY="futuris-dedicated-key",
        FUTURIS_API_KEY="futuris-peer-key",
    )
    with caplog.at_level(logging.WARNING, logger="futuris_memora_cloud_fallback"):
        result = client.read_event_cursor("futuris")
    assert result.get("ok") is True
    assert len(calls) == 2
    assert _auth_header(calls[0]) == "Bearer futuris-dedicated-key"
    assert _auth_header(calls[1]) == "Bearer futuris-peer-key"
    assert "FUTURIS_MEMORA_API_KEY" in caplog.text
    assert "FUTURIS_API_KEY" in caplog.text


def test_401_on_both_keys_returns_error(monkeypatch):
    """TASK-INT-037: a 401 on the retry key returns the error; no third key."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = _client(
        monkeypatch,
        FUTURIS_MEMORA_API_KEY="futuris-dedicated-key",
        FUTURIS_API_KEY="futuris-peer-key",
    )
    result = client.read_event_cursor("futuris")
    assert result["status"] == "error"
    assert client.last_error == "Memora HTTP 401"
    assert len(calls) == 2


def test_401_without_fallback_key_does_not_retry(monkeypatch):
    """TASK-INT-037: with no next key in the chain, a 401 fails as today."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = _client(monkeypatch, FUTURIS_MEMORA_API_KEY="futuris-dedicated-key")
    result = client.read_event_cursor("futuris")
    assert result["status"] == "error"
    assert client.last_error == "Memora HTTP 401"
    assert len(calls) == 1


def test_non_401_error_does_not_retry(monkeypatch):
    """TASK-INT-037: only a 401 triggers the fallback retry, nothing else."""
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = _client(
        monkeypatch,
        FUTURIS_MEMORA_API_KEY="futuris-dedicated-key",
        FUTURIS_API_KEY="futuris-peer-key",
    )
    result = client.read_event_cursor("futuris")
    assert result["status"] == "error"
    assert client.last_error == "Memora HTTP 500"
    assert len(calls) == 1
