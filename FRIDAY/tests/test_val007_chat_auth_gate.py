"""Regression tests for TASK-VAL-007: the D-023 auth gate on POST /api/chat.

VAL-005 finding F2: an unauthenticated remote client got a live conversational
reply from ``POST /friday/api/chat`` (HTTP 200, ``fast_path: true``) by sending
no key and no cookie — the gateway's own ``Origin`` header, or none at all,
was enough. The endpoint was origin-gated only, and an ``Origin`` header is a
client-controlled value, not an authentication boundary (the same flaw D-023
fixed for the ``/api/control/session`` mint in TASK-SEC-005). Worse, ``/api/chat``
is not a greeting-only surface: it drives the full command pipeline.

These tests pin the property that matters: on a remotely exposed deployment the
chat endpoint demands the owner key or a valid fcs1 control token, while the
owner's own loopback box stays keyless. The refused cases replay the exact
validator probe shape (``{"message": "hello FRIDAY"}``, gateway ``Origin``,
no credential). They fail against the pre-fix behaviour (remote chat with no
credential returns 200) and pass against the fix.
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


def _chat_headers(origin: str = DEPLOY_ORIGIN, **extra: str) -> dict[str, str]:
    return {"Origin": origin, **extra}


class TestRemoteChatRequiresOwnerCredential:
    """On a remotely exposed deployment, no credential means no live reply."""

    def test_remote_chat_without_credential_is_refused(self, remote_client: TestClient) -> None:
        """The VAL-005 attack replay: the validator probe shape, no key, no cookie."""
        response = remote_client.post(
            "/api/chat",
            json={"message": "hello FRIDAY"},
            headers=_chat_headers(),
        )
        assert response.status_code == 401, (
            f"remote caller got a live chat reply with only an Origin header "
            f"(HTTP {response.status_code}): {response.text[:200]}"
        )

    def test_remote_chat_without_origin_is_refused_too(self, remote_client: TestClient) -> None:
        """No Origin at all is the curl case — still judged by the key rule."""
        response = remote_client.post("/api/chat", json={"message": "hello FRIDAY"})
        assert response.status_code == 401

    def test_remote_chat_with_wrong_key_is_refused(self, remote_client: TestClient) -> None:
        response = remote_client.post(
            "/api/chat",
            json={"message": "hello FRIDAY"},
            headers=_chat_headers(**{"x-friday-api-key": ATTACKER_KEY}),
        )
        assert response.status_code == 401

    def test_remote_chat_refusal_names_the_missing_credential(
        self, remote_client: TestClient
    ) -> None:
        response = remote_client.post(
            "/api/chat",
            json={"message": "hello FRIDAY"},
            headers=_chat_headers(),
        )
        assert "key" in response.json()["detail"].lower()

    def test_remote_chat_with_owner_key_succeeds(self, remote_client: TestClient) -> None:
        response = remote_client.post(
            "/api/chat",
            json={"message": "what time is it"},
            headers=_chat_headers(**{"x-friday-api-key": OWNER_KEY}),
        )
        assert response.status_code == 200, response.text[:200]
        assert response.json()["reply"]

    def test_remote_chat_accepts_bearer_authorization(self, remote_client: TestClient) -> None:
        response = remote_client.post(
            "/api/chat",
            json={"message": "what time is it"},
            headers=_chat_headers(**{"Authorization": f"Bearer {OWNER_KEY}"}),
        )
        assert response.status_code == 200
        assert response.json()["reply"]

    def test_minted_token_drives_chat(self, remote_client: TestClient) -> None:
        """The D-023 flow end to end: mint with the key, chat with the token."""
        minted = remote_client.get(
            "/api/control/session",
            headers={**_origin(DEPLOY_ORIGIN), "x-friday-api-key": OWNER_KEY},
        ).json()["token"]
        assert minted.startswith("fcs1.")
        response = remote_client.post(
            "/api/chat",
            json={"message": "what time is it"},
            headers=_chat_headers(**{"X-FRIDAY-Control-Token": minted}),
        )
        assert response.status_code == 200
        assert response.json()["reply"]


class TestRemoteChatStillNeedsAllowedOrigin:
    """The origin gate stays in front of the key check: defence in depth."""

    def test_forged_foreign_origin_is_refused_even_with_key(
        self, remote_client: TestClient
    ) -> None:
        response = remote_client.post(
            "/api/chat",
            json={"message": "hello FRIDAY"},
            headers=_chat_headers(
                "https://attacker.example", **{"x-friday-api-key": OWNER_KEY}
            ),
        )
        assert response.status_code == 403

    def test_null_origin_is_refused_even_with_key(self, remote_client: TestClient) -> None:
        response = remote_client.post(
            "/api/chat",
            json={"message": "hello FRIDAY"},
            headers=_chat_headers("null", **{"x-friday-api-key": OWNER_KEY}),
        )
        assert response.status_code == 403


class TestLoopbackChatStaysKeyless:
    """The owner on the box itself keeps the friction-free flow."""

    def test_loopback_chat_without_key_succeeds(self, local_client: TestClient) -> None:
        response = local_client.post(
            "/api/chat",
            json={"message": "what time is it"},
            headers=_origin("http://testserver"),
        )
        assert response.status_code == 200, response.text[:200]
        assert response.json()["reply"]

    def test_loopback_chat_rejects_foreign_origin(self, local_client: TestClient) -> None:
        response = local_client.post(
            "/api/chat",
            json={"message": "what time is it"},
            headers=_origin("https://attacker.example"),
        )
        assert response.status_code == 403


class TestFailClosedWithoutUsableKey:
    """No usable key configured means no remote chat surface at all."""

    def test_remote_chat_fails_closed_without_key_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clear_key_env(monkeypatch)
        monkeypatch.setenv("RENDER", "true")
        _reload_settings()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/chat",
                    json={"message": "hello FRIDAY"},
                    headers=_chat_headers(),
                )
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
                response = client.post(
                    "/api/chat",
                    json={"message": "hello FRIDAY"},
                    headers=_chat_headers(),
                )
                assert response.status_code == 503
        finally:
            _reload_settings()
