"""Tests for the pooled single-line Gemini key storage format.

FRIDAY's own Gemini keys may be stored combined in a single variable
(``FRIDAY_GEMINI_API_KEY=k1,k2,k3,k4,k5`` -- primary first, then fallbacks
in order), mirroring how Inference stores its GEMINI_API_KEY pool line.
These tests pin the behaviours that make that format safe:

1. The credential pool parses the combined variable into exactly the 5
   keys, in order, labelled PRIMARY + FALLBACK 1-4.
2. Settings.gemini_api_key exposes only the first (primary) key, so
   single-key consumers (LLM factory, embeddings, vision/voice fallbacks)
   never receive the comma-joined string.
3. The chat provider therefore keeps using pool rotation.
"""

import hashlib
import threading

from friday.auth.credential_pool import GeminiCredentialPool
from friday.core.config import Settings
from friday.llm.gemini_provider import GeminiLLMProvider

KEYS = ["KEY_PRIMARY", "KEY_FALLBACK_1", "KEY_FALLBACK_2", "KEY_FALLBACK_3", "KEY_FALLBACK_4"]
COMBINED = ",".join(KEYS)


def _pool_from_combined_env(monkeypatch):
    """Build a pool whose credentials come solely from the combined var."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    for i in range(1, 10):
        monkeypatch.delenv(f"FRIDAY_GEMINI_FALLBACK_API_KEY_{i}", raising=False)
        monkeypatch.delenv(f"GEMINI_FALLBACK_API_KEY_{i}", raising=False)
    monkeypatch.setenv("FRIDAY_GEMINI_API_KEY", COMBINED)
    # Isolate from any developer/production .env file the pool also reads.
    monkeypatch.setattr("dotenv.dotenv_values", lambda **kwargs: {})
    pool = object.__new__(GeminiCredentialPool)
    pool.lock = threading.Lock()
    pool.max_failures = 1
    pool.cooldown_seconds = 60
    pool.state_file = None
    pool.credentials = []
    pool._session_active_key = None
    pool._load_credentials()
    return pool


def test_pool_loads_five_keys_in_order_from_combined_variable(monkeypatch):
    pool = _pool_from_combined_env(monkeypatch)
    assert [c.api_key for c in pool.credentials] == KEYS
    assert [c.project_label for c in pool.credentials] == [
        "PRIMARY",
        "FALLBACK 1",
        "FALLBACK 2",
        "FALLBACK 3",
        "FALLBACK 4",
    ]
    assert [c.key_fingerprint for c in pool.credentials] == [
        hashlib.sha256(k.encode()).hexdigest() for k in KEYS
    ]
    assert pool.credentials[0].is_primary is True
    assert all(not c.is_primary for c in pool.credentials[1:])


def test_settings_exposes_only_primary_from_combined_value():
    settings = Settings(gemini_api_key=COMBINED)
    assert settings.gemini_api_key == "KEY_PRIMARY"


def test_settings_combined_value_via_environment(monkeypatch):
    monkeypatch.setenv("FRIDAY_GEMINI_API_KEY", COMBINED)
    settings = Settings()
    assert settings.gemini_api_key == "KEY_PRIMARY"


def test_settings_single_key_unchanged():
    settings = Settings(gemini_api_key="KEY_SOLO")
    assert settings.gemini_api_key == "KEY_SOLO"


def test_provider_uses_pool_with_primary_from_combined_storage(monkeypatch):
    pool = _pool_from_combined_env(monkeypatch)
    settings = Settings(gemini_api_key=COMBINED)
    provider = GeminiLLMProvider(settings.gemini_api_key, credential_pool=pool)
    assert provider._should_use_pool() is True
    assert provider._get_active_api_key() == "KEY_PRIMARY"


def test_provider_would_not_use_pool_for_raw_combined_string(monkeypatch):
    """Documents the hazard the Settings normalisation prevents: a raw
    comma-joined explicit key matches no single pool credential, so the
    provider would fall back to using the joined string as one key."""
    pool = _pool_from_combined_env(monkeypatch)
    provider = GeminiLLMProvider(COMBINED, credential_pool=pool)
    assert provider._should_use_pool() is False
