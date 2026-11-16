"""TASK-IG2-INF-02: encrypted-at-rest key vault (FreeLLMAPI pattern).

Pins: roundtrip encryption, tamper/wrong-key detection, per-entry pool
separation (an entry decrypts only into its own settings field — the
FRIDAY / Inference / THIRD_PARTY_* pools are never merged), the guarantee
that no plaintext value ever lands in the vault file, and the startup
rule that a real environment value always wins over the vault.
"""

import json

import pytest

from app.providers.key_vault import (
    KeyVault,
    VaultIntegrityError,
    VaultNotConfiguredError,
    apply_vault_to_settings,
    key_fingerprint,
)

MASTER = "test-master-key-not-a-real-secret"
OTHER_MASTER = "a-different-master-key"


def _vault(tmp_path, master=MASTER):
    return KeyVault(path=tmp_path / "vault.json", master_key=master)


def test_roundtrip_and_persistence(tmp_path):
    vault = _vault(tmp_path)
    vault.set("GEMINI_API_KEYS", "key-one,key-two")
    vault.save()

    reloaded = _vault(tmp_path)
    assert reloaded.names() == ["GEMINI_API_KEYS"]
    assert reloaded.get("GEMINI_API_KEYS") == "key-one,key-two"
    assert reloaded.get("GROQ_API_KEY") is None


def test_plaintext_never_written_to_disk(tmp_path):
    vault = _vault(tmp_path)
    secret = "<redacted_api_token_1>"
    vault.set("GROQ_API_KEY", secret)
    vault.save()

    raw = (tmp_path / "vault.json").read_text(encoding="utf-8")
    assert secret not in raw
    assert "sk-ant" not in raw
    doc = json.loads(raw)
    assert doc["format"] == "friday-inference-key-vault"
    assert set(doc["entries"]) == {"GROQ_API_KEY"}


def test_tampered_ciphertext_is_rejected(tmp_path):
    vault = _vault(tmp_path)
    vault.set("GEMINI_API_KEY", "real-key")
    vault.save()

    path = tmp_path / "vault.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    ct = doc["entries"]["GEMINI_API_KEY"]["ciphertext"]
    doc["entries"]["GEMINI_API_KEY"]["ciphertext"] = ("A" if ct[0] != "A" else "B") + ct[1:]
    path.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(VaultIntegrityError):
        _vault(tmp_path).get("GEMINI_API_KEY")


def test_wrong_master_key_is_rejected(tmp_path):
    vault = _vault(tmp_path)
    vault.set("GEMINI_API_KEY", "real-key")
    vault.save()

    with pytest.raises(VaultIntegrityError):
        _vault(tmp_path, master=OTHER_MASTER).get("GEMINI_API_KEY")


def test_missing_master_key_is_a_clear_error(tmp_path):
    vault = KeyVault(path=tmp_path / "vault.json", master_key=None)
    with pytest.raises(VaultNotConfiguredError):
        vault.set("GEMINI_API_KEY", "x")


def test_entries_are_independent_per_pool(tmp_path):
    """THIRD_PARTY_* entries never leak into the plain provider fields."""
    vault = _vault(tmp_path)
    vault.set("GEMINI_API_KEYS", "inference-pool-key")
    vault.set("THIRD_PARTY_GEMINI_KEYS", "third-party-pool-key")
    vault.save()

    class FakeSettings:
        GEMINI_API_KEYS = None
        THIRD_PARTY_GEMINI_KEYS = None

    settings = FakeSettings()
    report = apply_vault_to_settings(settings, vault=_vault(tmp_path))
    assert settings.GEMINI_API_KEYS == "inference-pool-key"
    assert settings.THIRD_PARTY_GEMINI_KEYS == "third-party-pool-key"
    assert sorted(report["applied"]) == ["GEMINI_API_KEYS", "THIRD_PARTY_GEMINI_KEYS"]


def test_existing_environment_value_always_wins(tmp_path):
    vault = _vault(tmp_path)
    vault.set("GROQ_API_KEY", "vault-value")
    vault.save()

    class FakeSettings:
        GROQ_API_KEY = "<redacted>"

    settings = FakeSettings()
    report = apply_vault_to_settings(settings, vault=_vault(tmp_path))
    assert settings.GROQ_API_KEY == "env-value"
    assert report["applied"] == []
    assert report["skipped_existing"] == ["GROQ_API_KEY"]


def test_verify_all_returns_fingerprints_only(tmp_path):
    vault = _vault(tmp_path)
    vault.set("OPENROUTER_API_KEY", "or-key-123")
    result = vault.verify_all()
    assert result == {"OPENROUTER_API_KEY": key_fingerprint("or-key-123")}
    assert "or-key-123" not in json.dumps(result)


def test_same_value_encrypts_differently_each_time(tmp_path):
    vault = _vault(tmp_path)
    vault.set("A_KEY", "same-value")
    first = dict(vault._entries["A_KEY"])
    vault.set("A_KEY", "same-value")
    second = dict(vault._entries["A_KEY"])
    assert first["ciphertext"] != second["ciphertext"]
    assert first["salt"] != second["salt"]
    assert vault.get("A_KEY") == "same-value"
