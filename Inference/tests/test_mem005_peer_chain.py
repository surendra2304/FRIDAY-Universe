"""TASK-MEM-005-R1 (fix pass): Inference's Memora peer credential is its OWN.

get_peer_config("memora") feeds the live mesh routes — ping_mesh_peer presents
the returned key to Memora as Bearer + X-API-KEY under X-Agent-Name
"Inference". The settings field must therefore resolve Inference's
dedicated/per-agent chain (INFERENCE_MEMORA_API_KEY -> INFERENCE_API_KEY)
and never read MEMORA_API_KEY, which is Memora's own key.
"""

from app.core.config import Settings

_ENV_NAMES = ("MEMORA_API_KEY", "INFERENCE_MEMORA_API_KEY", "INFERENCE_API_KEY")


def _settings(monkeypatch, **env):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_shared_memora_key_is_never_presented(monkeypatch):
    s = _settings(monkeypatch, MEMORA_API_KEY="memora-own-key")
    assert s.MEMORA_API_KEY is None
    assert s.get_peer_config("memora")[1] is None


def test_dedicated_key_wins(monkeypatch):
    s = _settings(
        monkeypatch,
        MEMORA_API_KEY="memora-own-key",
        INFERENCE_API_KEY="inference-own",
        INFERENCE_MEMORA_API_KEY="inference-dedicated",
    )
    assert s.MEMORA_API_KEY == "inference-dedicated"
    assert s.get_peer_config("memora")[1] == "inference-dedicated"


def test_fallback_to_own_per_agent_key(monkeypatch):
    s = _settings(
        monkeypatch,
        MEMORA_API_KEY="memora-own-key",
        INFERENCE_API_KEY="inference-own",
    )
    assert s.MEMORA_API_KEY == "inference-own"
    assert s.get_peer_config("memora")[1] == "inference-own"


def test_other_peers_unaffected(monkeypatch):
    s = _settings(monkeypatch, MEMORA_API_KEY="memora-own-key")
    url, key = s.get_peer_config("stratex")
    assert url
    assert key is None
