"""TASK-MEM-005-R1: SDK / fallback credential chains.

Every client resolves an agent's OWN Memora credential — the dedicated
{AGENT}_MEMORA_API_KEY first, the per-agent {AGENT}_API_KEY as the
transition fallback — and never MEMORA_API_KEY (Memora's own key).
"""
from __future__ import annotations

import pytest

from sdk.cloud_fallback import MemoraClient as CloudFallbackClient
from sdk.memora_client import MemoraClient, _agent_memora_key

VARS = ("MEMORA_API_KEY", "STRATEX_API_KEY", "STRATEX_MEMORA_API_KEY")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in VARS:
        monkeypatch.delenv(var, raising=False)


def test_sdk_constructor_has_no_master_default(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    assert MemoraClient().api_key is None


def test_helper_ignores_master(monkeypatch):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    assert _agent_memora_key("stratex") is None


def test_helper_prefers_dedicated(monkeypatch):
    monkeypatch.setenv("STRATEX_API_KEY", "own-key")
    monkeypatch.setenv("STRATEX_MEMORA_API_KEY", "dedicated-key")
    assert _agent_memora_key("stratex") == "dedicated-key"
    headers = MemoraClient()._headers("stratex")
    assert headers["Authorization"] == "Bearer dedicated-key"


def test_cloud_fallback_prefers_dedicated(monkeypatch):
    monkeypatch.setenv("STRATEX_API_KEY", "own-key")
    monkeypatch.setenv("STRATEX_MEMORA_API_KEY", "dedicated-key")
    client = CloudFallbackClient(base_url="http://127.0.0.1:1")
    # Transport fails, but the credential gate must have passed: the error
    # is a connection error, not "not configured".
    result = client._request("stratex", "/v1/events")
    assert "not configured" not in str(result.get("error", ""))
