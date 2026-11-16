"""TASK-MEM-005-R1 (fix pass): UniversalMemoryFabric has no ambient
shared-key default.

The fabric used to default its credential to os.getenv("MEMORA_API_KEY",
"memora_api") and present it under X-Agent-Name <entry.owner_agent> — any
owner's identity backed by Memora's own key (or a placeholder literal). Now
an explicitly passed key wins; otherwise dispatch resolves the presented
owner's own chain ({OWNER}_MEMORA_API_KEY -> {OWNER}_API_KEY); with no
resolvable key the fabric stays local (its existing graceful degrade).
"""

import urllib.request

import pytest

from mesh.memory_fabric import MemoryEntry, UniversalMemoryFabric

_ENVS = (
    "MEMORA_API_KEY",
    "STRATEX_MEMORA_API_KEY",
    "STRATEX_API_KEY",
    "MEMORA_URL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENVS:
        monkeypatch.delenv(name, raising=False)


def _fabric(tmp_path, **kwargs):
    return UniversalMemoryFabric(local_db_path=str(tmp_path / "fabric.db"), **kwargs)


def test_constructor_has_no_ambient_default(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    assert _fabric(tmp_path).api_key is None


def test_constructor_keeps_explicit_key(tmp_path):
    assert _fabric(tmp_path, api_key="explicit-key").api_key == "explicit-key"


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _dispatch(monkeypatch, fabric, owner_agent):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.header_items())
        captured["url"] = req.full_url
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    entry = MemoryEntry(owner_agent=owner_agent, content_text="probe")
    result = fabric._dispatch_to_cloud(entry)
    return result, captured


def test_dispatch_presents_owner_credential(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    monkeypatch.setenv("STRATEX_MEMORA_API_KEY", "stratex-dedicated")
    result, captured = _dispatch(monkeypatch, _fabric(tmp_path), "STRATEX")
    assert result is True
    assert captured["headers"]["Authorization"] == "Bearer stratex-dedicated"
    assert captured["headers"]["X-agent-name"] == "stratex"


def test_dispatch_falls_back_to_owner_per_agent_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    monkeypatch.setenv("STRATEX_API_KEY", "stratex-own")
    result, captured = _dispatch(monkeypatch, _fabric(tmp_path), "STRATEX")
    assert result is True
    assert captured["headers"]["Authorization"] == "Bearer stratex-own"


def test_dispatch_explicit_key_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("STRATEX_MEMORA_API_KEY", "stratex-dedicated")
    fabric = _fabric(tmp_path, api_key="explicit-key")
    result, captured = _dispatch(monkeypatch, fabric, "STRATEX")
    assert result is True
    assert captured["headers"]["Authorization"] == "Bearer explicit-key"


def test_dispatch_without_any_key_stays_local(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORA_API_KEY", "memora-own-key")
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: called.append(a) or _FakeResponse()
    )
    entry = MemoryEntry(owner_agent="STRATEX", content_text="probe")
    assert _fabric(tmp_path)._dispatch_to_cloud(entry) is False
    assert called == []
