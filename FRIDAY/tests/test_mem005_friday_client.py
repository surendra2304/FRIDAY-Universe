"""TASK-MEM-005-R1: FRIDAY's Memora client credential model.

FRIDAY authenticates to Memora only as itself, with its own key
(FRIDAY_MEMORA_API_KEY, falling back to its per-agent FRIDAY_API_KEY).
Access to another agent's namespace is requested through Memora's scoped
delegation (X-On-Behalf-Of) — never by presenting that agent's key — and
MEMORA_API_KEY (Memora's own key / the former master fallback) is never read.
"""
from __future__ import annotations

import pytest

from friday.memory.memora_client import MemoraClient

KEY_VARS = (
    "MEMORA_API_KEY",
    "FRIDAY_MEMORA_API_KEY",
    "FRIDAY_API_KEY",
    "FRIDAY_UNIVERSE_API_KEY",
    "STRATEX_API_KEY",
    "INTELX_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_key_env(monkeypatch):
    for var in KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("FRIDAY_MEMORA_REMOTE_ENABLED", raising=False)


def make_client(**kwargs) -> MemoraClient:
    kwargs.setdefault("remote_enabled", True)
    return MemoraClient(**kwargs)


def test_constructor_never_reads_memora_api_key(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    client = make_client()
    assert client.api_key is None
    assert client._own_api_key() is None


def test_constructor_prefers_dedicated_memora_key(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    monkeypatch.setenv("FRIDAY_API_KEY", "friday-service")
    client = make_client()
    assert client.api_key == "friday-dedicated"
    assert client._own_api_key() == "friday-dedicated"


def test_own_key_ignores_other_agents_keys(monkeypatch):
    monkeypatch.setenv("STRATEX_API_KEY", "stratex-key")
    monkeypatch.setenv("INTELX_API_KEY", "intelx-key")
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    client = make_client()
    assert client._own_api_key() is None


def test_headers_for_self_carry_no_delegation(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    client = make_client()
    headers = client._remote_headers("friday")
    assert headers["X-Agent-Name"] == "friday"
    assert "X-On-Behalf-Of" not in headers
    assert headers["Authorization"] == "Bearer friday-dedicated"


def test_headers_for_other_agent_delegate_with_fridays_own_key(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    monkeypatch.setenv("STRATEX_API_KEY", "stratex-key")
    client = make_client()
    headers = client._remote_headers("stratex")
    assert headers["X-Agent-Name"] == "friday"
    assert headers["X-On-Behalf-Of"] == "stratex"
    # The credential is FRIDAY's — never the target agent's key.
    assert headers["Authorization"] == "Bearer friday-dedicated"


def test_publish_event_refuses_foreign_source(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    monkeypatch.setenv("STRATEX_API_KEY", "stratex-key")
    client = make_client()
    result = client.publish_event("stratex", "friday", "alert", {"x": 1})
    assert result["status"] == "error"
    assert "cannot be delegated" in result["error"]


def test_poll_events_uses_own_key_not_target_key(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORA_API_KEY", "friday-dedicated")
    client = make_client()
    # No server is listening; the call must fail at transport, not at the
    # credential gate — proving the own-key path was taken for a foreign feed.
    result = client.poll_events("stratex", after_id=0, limit=10)
    assert result["status"] == "error"
    assert "not configured" not in result["error"]
