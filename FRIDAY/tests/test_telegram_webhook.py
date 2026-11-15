"""TASK-FRD-TGWEBHOOK — webhook mode for FRIDAY's Telegram gateway.

Contracts locked here:
- webhook mode is opt-in: TELEGRAM_WEBHOOK_URL set flips the gateway
  from long polling to webhook registration; unset, start() behaves
  exactly as before (deleteWebhook + polling thread);
- in webhook mode start() registers the webhook (URL + secret_token)
  and NEVER long-polls and NEVER calls deleteWebhook — with a webhook
  set, Telegram itself rejects the rival poller's getUpdates;
- the POST /telegram-webhook route verifies the
  X-Telegram-Bot-Api-Secret-Token header (403 on mismatch, 400 on a
  malformed body, 404 while webhook mode is off) and feeds updates
  into the SAME handling path the poller uses (owner gate + brain);
- duplicate webhook deliveries are dropped by update_id.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.proactive import telegram_gateway as tg  # noqa: E402

WEBHOOK_URL = "https://friday-universe.duckdns.org/friday/telegram-webhook"
WEBHOOK_SECRET = "test-webhook-secret"


def _update(update_id: int, text: str, sender_id: str = "6341781431", chat_id: str = "6341781431") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "text": text,
            "chat": {"id": int(chat_id)},
            "from": {"id": int(sender_id), "first_name": "Owner"},
        },
    }


def _gateway(monkeypatch: pytest.MonkeyPatch, brain=None) -> tg.TelegramGateway:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
    g = tg.TelegramGateway()
    if brain is not None:
        g.set_brain(brain)
    return g


def _webhook_env(monkeypatch: pytest.MonkeyPatch, secret: bool = True) -> None:
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", WEBHOOK_URL)
    if secret:
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", WEBHOOK_SECRET)
    else:
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)


class _RecordingSender:
    """Capture send_message calls without touching the network."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def __call__(self, text: str, chat_id: str | None = None) -> bool:
        self.sent.append(text)
        return True


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# ---------------------------------------------------------------------------
# webhook configuration
# ---------------------------------------------------------------------------

class TestWebhookConfig:
    def test_webhook_mode_off_by_default(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_WEBHOOK_URL", raising=False)
        g = _gateway(monkeypatch)
        assert g.webhook_mode is False

    def test_webhook_mode_on_when_url_set(self, monkeypatch):
        _webhook_env(monkeypatch)
        g = _gateway(monkeypatch)
        assert g.webhook_mode is True

    def test_secret_matches_only_the_configured_secret(self, monkeypatch):
        _webhook_env(monkeypatch)
        g = _gateway(monkeypatch)
        assert g.webhook_secret_matches(WEBHOOK_SECRET) is True
        assert g.webhook_secret_matches("wrong-secret") is False
        assert g.webhook_secret_matches(None) is False
        assert g.webhook_secret_matches("") is False

    def test_secret_check_passes_when_no_secret_configured(self, monkeypatch):
        _webhook_env(monkeypatch, secret=False)
        g = _gateway(monkeypatch)
        assert g.webhook_secret_matches(None) is True


# ---------------------------------------------------------------------------
# start(): mode selection
# ---------------------------------------------------------------------------

class TestStartModes:
    def _stub_api(self, monkeypatch, g) -> list[tuple[str, dict]]:
        calls: list[tuple[str, dict]] = []
        monkeypatch.setattr(
            g,
            "_api",
            lambda method, params: (calls.append((method, params)) or {"ok": True, "result": []}),
        )
        return calls

    def test_webhook_start_registers_and_never_polls(self, monkeypatch):
        _webhook_env(monkeypatch)
        g = _gateway(monkeypatch)
        calls = self._stub_api(monkeypatch, g)
        assert g.start() is True
        try:
            methods = [m for m, _ in calls]
            assert methods == ["setWebhook"], f"webhook mode must only register, got {methods}"
            payload = calls[0][1]
            assert payload["url"] == WEBHOOK_URL
            assert payload["secret_token"] == WEBHOOK_SECRET
            assert payload["allowed_updates"] == ["message", "edited_message"]
            assert g._thread is None, "webhook mode must not start a polling thread"
            assert g.running is True
        finally:
            g.stop()

    def test_polling_start_is_unchanged_when_webhook_unset(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_WEBHOOK_URL", raising=False)
        g = _gateway(monkeypatch)
        calls = self._stub_api(monkeypatch, g)
        assert g.start() is True
        try:
            methods = [m for m, _ in calls]
            assert "deleteWebhook" in methods, "polling mode still clears stale webhooks"
            assert "setWebhook" not in methods
            assert g._thread is not None and g._thread.is_alive()
        finally:
            g.stop()

    def test_set_webhook_omits_secret_token_when_unset(self, monkeypatch):
        _webhook_env(monkeypatch, secret=False)
        g = _gateway(monkeypatch)
        calls = self._stub_api(monkeypatch, g)
        assert g.set_webhook() is True
        payload = calls[0][1]
        assert payload["url"] == WEBHOOK_URL
        assert "secret_token" not in payload

    def test_set_webhook_without_url_is_a_no_op(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_WEBHOOK_URL", raising=False)
        g = _gateway(monkeypatch)
        calls = self._stub_api(monkeypatch, g)
        assert g.set_webhook() is False
        assert calls == []


# ---------------------------------------------------------------------------
# process_webhook_update(): the same handling path as the poller
# ---------------------------------------------------------------------------

class TestProcessWebhookUpdate:
    def test_owner_update_reaches_the_brain_and_replies(self, monkeypatch):
        brain = lambda cmd: {"reply": f"echo:{cmd}", "metadata": {}}  # noqa: E731
        g = _gateway(monkeypatch, brain)
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        assert g.process_webhook_update(_update(101, "what time is it?")) is True
        assert _wait_for(lambda: bool(sent.sent)), "webhook dispatch never replied"
        assert "echo:what time is it?" in sent.sent[0]

    def test_duplicate_delivery_is_dropped(self, monkeypatch):
        replies: list[str] = []
        brain = lambda cmd: {"reply": replies.append(cmd) or "ok", "metadata": {}}  # noqa: E731
        g = _gateway(monkeypatch, brain)
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        update = _update(102, "hello")
        assert g.process_webhook_update(update) is True
        assert _wait_for(lambda: bool(sent.sent))
        assert g.process_webhook_update(update) is False, "same update_id must be dropped"
        time.sleep(0.2)
        assert replies == ["hello"], "the brain must see a duplicated update only once"

    def test_non_owner_is_refused_and_never_reaches_the_brain(self, monkeypatch):
        brain = MagicMock(side_effect=AssertionError("brain must not be called"))
        g = _gateway(monkeypatch, brain)
        sent = _RecordingSender()
        monkeypatch.setattr(g, "send_message", sent)
        assert g.process_webhook_update(_update(103, "shut down the fleet", sender_id="99999")) is True
        assert _wait_for(lambda: bool(sent.sent)), "non-owner must receive the refusal line"
        assert "Surendra" in sent.sent[0]
        brain.assert_not_called()

    def test_non_dict_update_is_rejected(self, monkeypatch):
        g = _gateway(monkeypatch)
        assert g.process_webhook_update("not-a-dict") is False  # type: ignore[arg-type]
        assert g.process_webhook_update(None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# POST /telegram-webhook route
# ---------------------------------------------------------------------------

@pytest.fixture()
def route_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient with the singleton's dispatch stubbed (no network, no
    lifespan side effects) but the REAL secret/mode checks in force."""
    from fastapi.testclient import TestClient

    from friday.api.server import app
    from friday.proactive.telegram_gateway import telegram_gateway

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
    dispatched: list[dict] = []
    monkeypatch.setattr(
        telegram_gateway,
        "process_webhook_update",
        lambda update: (dispatched.append(update) or True),
    )
    client = TestClient(app)
    client.dispatched = dispatched  # type: ignore[attr-defined]
    return client


class TestWebhookRoute:
    def test_route_404_while_webhook_mode_off(self, route_client, monkeypatch):
        monkeypatch.delenv("TELEGRAM_WEBHOOK_URL", raising=False)
        resp = route_client.post("/telegram-webhook", json=_update(201, "hi"))
        assert resp.status_code == 404
        assert route_client.dispatched == []

    def test_route_rejects_mismatched_secret_with_403(self, route_client, monkeypatch):
        _webhook_env(monkeypatch)
        resp = route_client.post(
            "/telegram-webhook",
            json=_update(202, "hi"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert resp.status_code == 403
        assert route_client.dispatched == [], "a rejected POST must never be dispatched"

    def test_route_rejects_missing_secret_with_403(self, route_client, monkeypatch):
        _webhook_env(monkeypatch)
        resp = route_client.post("/telegram-webhook", json=_update(203, "hi"))
        assert resp.status_code == 403
        assert route_client.dispatched == []

    def test_route_400_on_malformed_body(self, route_client, monkeypatch):
        _webhook_env(monkeypatch)
        resp = route_client.post(
            "/telegram-webhook",
            content="this is not json",
            headers={
                "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400
        assert route_client.dispatched == []

    def test_route_accepts_and_dispatches_a_valid_update(self, route_client, monkeypatch):
        _webhook_env(monkeypatch)
        update = _update(204, "what time is it?")
        resp = route_client.post(
            "/telegram-webhook",
            json=update,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert route_client.dispatched == [update]
