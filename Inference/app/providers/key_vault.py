"""Encrypted-at-rest vault for Inference provider keys (TASK-IG2-INF-02).

Pattern adopted from FreeLLMAPI (see ~/workspace/ig-references/repos/
freellmapi.md): provider API keys stored *encrypted* instead of as plaintext
values in env files, decrypted in memory only at use.

Why this exists
---------------
The fleet's provider keys have already needed one consolidation/rotation
episode (2026-11-15/16). Today every Inference key sits in plaintext in the
service ``.env``: any single file leak — a stray backup, a log bundle, a
mis-shared archive — exposes the whole pool. This vault shrinks that blast
radius: the on-disk artifact is ciphertext, and the only secret needed to
open it (the master key) lives solely in the service environment
(``INFERENCE_KEY_VAULT_MASTER_KEY``), never in the vault file and never in
the repo.

Pool separation is structural, not conventional
------------------------------------------------
A vault entry is keyed by the *exact settings field name* it feeds
(``GEMINI_API_KEYS``, ``THIRD_PARTY_GEMINI_KEYS``, ``GROQ_API_KEY``, ...).
The FRIDAY / Inference / ``THIRD_PARTY_*`` key pools are separate security
domains and are **never merged**: an entry decrypts into exactly the one
field it was stored under, and :func:`apply_vault_to_settings` never moves
a value across fields. Callers keep using ``settings.get_provider_keys()``
exactly as before.

Cryptography (stdlib only — no new dependency)
----------------------------------------------
The fleet venv does not carry the ``cryptography`` package, and this module
must run on a ~956MB Python 3.10 host, so the construction uses only
``hashlib`` / ``hmac`` / ``secrets``:

* Key derivation: PBKDF2-HMAC-SHA256, 200,000 iterations, per-entry random
  16-byte salt, deriving 64 bytes split into an encryption key and a MAC key.
* Encryption: HMAC-SHA256 in counter mode as the keystream PRF
  (``HMAC(enc_key, nonce || counter_be32)`` blocks XORed with the plaintext),
  per-entry random 16-byte nonce.
* Integrity: encrypt-then-MAC — ``HMAC(mac_key, domain || salt || nonce ||
  ciphertext)`` verified with :func:`hmac.compare_digest` *before* any
  decryption. Any tampering or a wrong master key raises
  :class:`VaultIntegrityError`; no partial plaintext is ever returned.

This provides confidentiality and integrity for data at rest. It is not a
KMS and does not protect against an attacker who can read the running
process's memory or the master-key environment variable itself.

Usage
-----
Operator flow (values are read from a hidden prompt / stdin, never argv)::

    INFERENCE_KEY_VAULT_MASTER_KEY=... python -m app.providers.key_vault set GEMINI_API_KEYS
    INFERENCE_KEY_VAULT_MASTER_KEY=... python -m app.providers.key_vault list
    INFERENCE_KEY_VAULT_MASTER_KEY=... python -m app.providers.key_vault verify

At startup, ``app.main`` calls :func:`apply_vault_to_settings`, which fills
*only currently-empty* settings fields from the vault: a real environment
value always wins, so the vault is a store, not an override.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

VAULT_FORMAT = "friday-inference-key-vault"
VAULT_VERSION = 1
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16
_NONCE_BYTES = 16
_DOMAIN = b"friday-inference-key-vault/v1"

_DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / ".data" / "key_vault.json"
VAULT_PATH = Path(os.environ.get("INFERENCE_KEY_VAULT_FILE", str(_DEFAULT_VAULT_PATH)))
MASTER_KEY_ENV = "INFERENCE_KEY_VAULT_MASTER_KEY"


class VaultError(Exception):
    """Base class for vault failures."""


class VaultIntegrityError(VaultError):
    """Ciphertext failed authentication (tampered file or wrong master key)."""


class VaultNotConfiguredError(VaultError):
    """The vault or its master key is not configured."""


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def _derive_keys(master_key: str, salt: bytes) -> tuple[bytes, bytes]:
    material = hashlib.pbkdf2_hmac(
        "sha256", master_key.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=64
    )
    return material[:32], material[32:]


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hmac.new(enc_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def _xor(data: bytes, stream: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, stream))


def _encrypt_entry(master_key: str, plaintext: str) -> dict[str, Any]:
    salt = secrets.token_bytes(_SALT_BYTES)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    enc_key, mac_key = _derive_keys(master_key, salt)
    raw = plaintext.encode("utf-8")
    ciphertext = _xor(raw, _keystream(enc_key, nonce, len(raw)))
    tag = hmac.new(mac_key, _DOMAIN + salt + nonce + ciphertext, hashlib.sha256).digest()
    return {
        "version": VAULT_VERSION,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(ciphertext),
        "tag": _b64e(tag),
        "updated_at": time.time(),
    }


def _decrypt_entry(master_key: str, entry: dict[str, Any]) -> str:
    try:
        salt = _b64d(entry["salt"])
        nonce = _b64d(entry["nonce"])
        ciphertext = _b64d(entry["ciphertext"])
        tag = _b64d(entry["tag"])
    except (KeyError, ValueError) as exc:
        raise VaultIntegrityError("vault entry is malformed") from exc
    enc_key, mac_key = _derive_keys(master_key, salt)
    expected = hmac.new(mac_key, _DOMAIN + salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise VaultIntegrityError(
            "vault entry failed authentication (tampered ciphertext or wrong master key)"
        )
    return _xor(ciphertext, _keystream(enc_key, nonce, len(ciphertext))).decode("utf-8")


def key_fingerprint(value: str) -> str:
    """Non-reversible identity for a stored value (same convention as the quota ledger)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


class KeyVault:
    """A JSON vault file of encrypted provider-key entries.

    Entry names are exact settings field names (``GEMINI_API_KEYS``,
    ``THIRD_PARTY_GEMINI_KEYS``, ...). Entries are independent: decrypting
    one never touches another, and no API combines entries across pools.
    """

    def __init__(self, path: Path | None = None, master_key: str | None = None) -> None:
        self._path = Path(path) if path is not None else VAULT_PATH
        self._master_key = master_key if master_key is not None else os.environ.get(MASTER_KEY_ENV)
        self._entries: dict[str, dict[str, Any]] = {}
        if self._path.exists():
            self._load()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            doc = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VaultError(f"cannot read vault file {self._path}: {exc}") from exc
        if doc.get("format") != VAULT_FORMAT or doc.get("version") != VAULT_VERSION:
            raise VaultError(f"unsupported vault format in {self._path}")
        entries = doc.get("entries")
        if not isinstance(entries, dict):
            raise VaultError(f"vault file {self._path} has no entries mapping")
        self._entries = entries

    def save(self) -> None:
        """Write the vault atomically-ish with owner-only permissions."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        doc = {"format": VAULT_FORMAT, "version": VAULT_VERSION, "entries": self._entries}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self._path)

    # ------------------------------------------------------------------
    # operations
    # ------------------------------------------------------------------
    def _require_master(self) -> str:
        if not self._master_key:
            raise VaultNotConfiguredError(
                f"master key is not configured: set {MASTER_KEY_ENV} in the service environment"
            )
        return self._master_key

    def set(self, env_name: str, value: str) -> None:
        """Encrypt ``value`` under entry ``env_name`` (in memory until :meth:`save`)."""
        name = env_name.strip().upper()
        if not name or not all(c.isalnum() or c == "_" for c in name):
            raise VaultError(f"invalid entry name {env_name!r}: expected a settings field name")
        if not value:
            raise VaultError("refusing to store an empty value")
        self._entries[name] = _encrypt_entry(self._require_master(), value)

    def get(self, env_name: str) -> str | None:
        """Decrypt one entry, or ``None`` when absent. Raises on tampering."""
        entry = self._entries.get(env_name.strip().upper())
        if entry is None:
            return None
        return _decrypt_entry(self._require_master(), entry)

    def delete(self, env_name: str) -> bool:
        return self._entries.pop(env_name.strip().upper(), None) is not None

    def names(self) -> list[str]:
        return sorted(self._entries)

    def verify_all(self) -> dict[str, str]:
        """Decrypt every entry; return ``{name: key_fingerprint}`` (never values)."""
        return {name: key_fingerprint(self.get(name) or "") for name in self.names()}


def vault_configured() -> bool:
    """Whether a vault file exists and a master key is present in the environment."""
    return VAULT_PATH.exists() and bool(os.environ.get(MASTER_KEY_ENV))


def apply_vault_to_settings(settings_obj: Any, vault: KeyVault | None = None) -> dict[str, Any]:
    """Fill empty settings fields from the vault at startup.

    Rules (all deliberate):

    * A field that already has a value — from the real environment or the
      ``.env`` file — is **never overwritten**; the vault is an at-rest
      store, not an override channel.
    * Each entry fills exactly the field it is named after, so the
      FRIDAY / Inference / ``THIRD_PARTY_*`` pools stay separate.
    * Failures are reported by entry *name* only. Values and fingerprints
      of values are never logged or returned here beyond what
      :meth:`KeyVault.verify_all` exposes to operators on request.

    Returns a report dict: ``{"applied": [...], "skipped_existing": [...],
    "errors": [{"name": ..., "error": ...}]}``.
    """
    report: dict[str, Any] = {"applied": [], "skipped_existing": [], "errors": []}
    if vault is None:
        if not vault_configured():
            return report
        vault = KeyVault()
    for name in vault.names():
        current = getattr(settings_obj, name, None)
        if current:
            report["skipped_existing"].append(name)
            continue
        try:
            value = vault.get(name)
        except VaultError as exc:
            report["errors"].append({"name": name, "error": str(exc)})
            continue
        if value is None:
            continue
        try:
            setattr(settings_obj, name, value)
        except Exception as exc:  # noqa: BLE001 - a frozen settings object must not kill startup
            report["errors"].append({"name": name, "error": f"cannot set field: {exc}"})
            continue
        report["applied"].append(name)
    return report


def main(argv: list[str] | None = None) -> int:
    """Operator CLI: ``python -m app.providers.key_vault {set|list|verify|delete}``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__.split("Usage")[1].split("At startup")[0].strip(), file=sys.stderr)
        return 2
    command, rest = args[0], args[1:]
    try:
        vault = KeyVault()
        if command == "set" and len(rest) == 1:
            value = getpass.getpass(f"Value for {rest[0]} (input hidden): ")
            vault.set(rest[0], value)
            vault.save()
            print(f"stored {rest[0].upper()} (fingerprint {key_fingerprint(value)})")
        elif command == "list" and not rest:
            for name in vault.names():
                print(name)
        elif command == "verify" and not rest:
            for name, fp in vault.verify_all().items():
                print(f"{name}: ok (fingerprint {fp})")
        elif command == "delete" and len(rest) == 1:
            if vault.delete(rest[0]):
                vault.save()
                print(f"deleted {rest[0].upper()}")
            else:
                print(f"no such entry: {rest[0].upper()}", file=sys.stderr)
                return 1
        else:
            print(f"unknown or malformed command: {' '.join(args)}", file=sys.stderr)
            return 2
    except VaultError as exc:
        print(f"vault error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
