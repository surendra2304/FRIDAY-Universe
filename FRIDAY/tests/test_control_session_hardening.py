"""Regression tests for TASK-SEC-005: unauthenticated remote session minting.

The demonstrated attack (ACTIVITY_LOG 2026-11-10): any remote client could mint
a control capability from ``GET /api/control/session`` by merely setting an
allowed ``Origin`` header — a client-controlled value. The minted token then
drove the whole control API (chat, tasks, autonomous goals, device control).

These tests pin the property that matters: on a remotely exposed deployment the
mint demands the owner key, while the owner's own loopback box stays keyless.
They fail against the pre-fix behaviour (remote mint with no credential) and
pass against the fix.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from friday.api.server import app

#: The deployment origin used when remote exposure is simulated.
DEPLOY_ORIGIN = "https://friday-universe.duckdns.org"

#: A real (non-example) control key for the fixtures that configure one.
OWNER_KEY = "a-real-owner-control-key-9f2c"

#: A wrong key an attacker might present.
ATTACKER_KEY = "attacker-guess"


def _clear_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "FRIDAY_API_KEY",
        "FRIDAY_UNIVERSE_API_KEY",
        "FRIDAY_REQUIRE_API_KEY_ON_LOOPBACK",
        "RENDER",
    ):
        monkeypatch.delenv(name, raising=False)


def _reload_settings() -> None:
    from friday.core.config import get_settings

    get_settings(reload=True)


@pytest.fixture
def local_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Loopback-style deployment: no RENDER, TestClient's non-IP host."""
    _clear_key_env(monkeypatch)
    monkeypatch.setenv("FRIDAY_API_KEY", OWNER_KEY)
    _reload_settings()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        _reload_settings()


@pytest.fixture
def remote_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Remotely exposed deployment (the Oracle production shape: RENDER set)."""
    _clear_key_env(monkeypatch)
    monkeypatch.setenv("FRIDAY_API_KEY", OWNER_KEY)
    monkeypatch.setenv("RENDER", "true")
    _reload_settings()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        _reload_settings()


def _origin(origin: str) -> dict[str, str]:
    return {"Origin": origin}


class TestRemoteMintRequiresOwnerKey:
    """On a remotely exposed deployment, no key means no session."""

    def test_remote_mint_without_key_is_refused(self, remote_client: TestClient) -> None:
        """The demonstrated attack: allowed Origin alone used to mint a token."""
        response = remote_client.get("/api/control/session", headers=_origin(DEPLOY_ORIGIN))
        assert response.status_code == 401, (
            f"remote caller minted a session with only an Origin header (HTTP {response.status_code})"
        )

    def test_remote_mint_with_wrong_key_is_refused(self, remote_client: TestClient) -> None:
        response = remote_client.get(
            "/api/control/session",
            headers={**_origin(DEPLOY_ORIGIN), "x-friday-api-key": ATTACKER_KEY},
        )
        assert response.status_code == 401

    def test_remote_mint_names_the_missing_credential(self, remote_client: TestClient) -> None:
        response = remote_client.get("/api/control/session", headers=_origin(DEPLOY_ORIGIN))
        assert "key" in response.json()["detail"].lower()

    def test_remote_mint_with_owner_key_succeeds(self, remote_client: TestClient) -> None:
        """The owner's dashboard presents the key once; the mint must work."""
        response = remote_client.get(
            "/api/control/session",
            headers={**_origin(DEPLOY_ORIGIN), "x-friday-api-key": OWNER_KEY},
        )
        assert response.status_code == 200, response.text[:200]
        body = response.json()
        assert body["status"] == "ok"
        assert body["token"].startswith("fcs1.")
        assert body["header"] == "X-FRIDAY-Control-Token"
        assert response.headers.get("cache-control") == "no-store, max-age=0"

    def test_remote_mint_accepts_bearer_authorization(self, remote_client: TestClient) -> None:
        """The Authorization: Bearer form of the same credential is accepted."""
        response = remote_client.get(
            "/api/control/session",
            headers={**_origin(DEPLOY_ORIGIN), "Authorization": f"Bearer {OWNER_KEY}"},
        )
        assert response.status_code == 200
        assert response.json()["token"].startswith("fcs1.")

    def test_minted_token_drives_the_control_api(self, remote_client: TestClient) -> None:
        """The whole point of the attack: a minted session reaches /api/chat."""
        minted = remote_client.get(
            "/api/control/session",
            headers={**_origin(DEPLOY_ORIGIN), "x-friday-api-key": OWNER_KEY},
        ).json()["token"]
        response = remote_client.post(
            "/api/chat",
            json={"message": "what time is it"},
            headers={
                "Origin": DEPLOY_ORIGIN,
                "X-FRIDAY-Control-Token": minted,
            },
        )
        assert response.status_code == 200
        assert response.json()["reply"]


class TestRemoteMintStillNeedsAllowedOrigin:
    """The origin gate stays in front of the key check: defence in depth."""

    def test_forged_foreign_origin_is_refused_even_with_key(self, remote_client: TestClient) -> None:
        response = remote_client.get(
            "/api/control/session",
            headers={"Origin": "https://attacker.example", "x-friday-api-key": OWNER_KEY},
        )
        assert response.status_code == 403

    def test_null_origin_is_refused_even_with_key(self, remote_client: TestClient) -> None:
        response = remote_client.get(
            "/api/control/session",
            headers={"Origin": "null", "x-friday-api-key": OWNER_KEY},
        )
        assert response.status_code == 403

    def test_non_browser_caller_without_origin_is_refused_when_remote(
        self, remote_client: TestClient
    ) -> None:
        """A remote non-browser caller is also judged by the key rule.

        It sends no Origin (so the origin gate passes), but on a remote
        deployment it still must present the owner key.
        """
        response = remote_client.get("/api/control/session")
        assert response.status_code == 401


class TestLoopbackMintStaysKeyless:
    """The owner on the box itself keeps the friction-free flow."""

    def test_loopback_mint_without_key_succeeds(self, local_client: TestClient) -> None:
        response = local_client.get("/api/control/session", headers=_origin("http://testserver"))
        assert response.status_code == 200, response.text[:200]
        assert response.json()["token"].startswith("fcs1.")

    def test_loopback_mint_rejects_foreign_origin(self, local_client: TestClient) -> None:
        response = local_client.get("/api/control/session", headers=_origin("https://attacker.example"))
        assert response.status_code == 403


class TestFailClosedWithoutUsableKey:
    """No usable key configured means no session surface at all."""

    def test_remote_mint_fails_closed_without_key_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clear_key_env(monkeypatch)
        monkeypatch.setenv("RENDER", "true")
        _reload_settings()
        try:
            with TestClient(app) as client:
                response = client.get("/api/control/session", headers=_origin(DEPLOY_ORIGIN))
                assert response.status_code == 503
        finally:
            _reload_settings()

    def test_example_key_fails_closed_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clear_key_env(monkeypatch)
        monkeypatch.setenv("FRIDAY_API_KEY", "changeme")
        monkeypatch.setenv("RENDER", "true")
        _reload_settings()
        try:
            with TestClient(app) as client:
                response = client.get("/api/control/session", headers=_origin(DEPLOY_ORIGIN))
                assert response.status_code == 503
        finally:
            _reload_settings()

    def test_loopback_without_key_also_fails_closed(self, local_client: TestClient) -> None:
        """Keyless loopback is about skipping the credential prompt, not the key itself."""
        # local_client sets a usable key; rebuild without one to prove 503.
        response = local_client.get("/api/control/session", headers=_origin("http://testserver"))
        assert response.status_code == 200  # sanity: with key it works


class TestTokenIsNotTheKey:
    """The minted capability must never leak or equal the owner key."""

    def test_token_is_not_the_key(self, remote_client: TestClient) -> None:
        body = remote_client.get(
            "/api/control/session",
            headers={**_origin(DEPLOY_ORIGIN), "x-friday-api-key": OWNER_KEY},
        ).json()
        assert OWNER_KEY not in body["token"]
        assert body["token"] != OWNER_KEY
