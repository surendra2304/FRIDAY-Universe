"""TASK-COR-010 — Telegram-shaped payload mode for the escalation webhook.

The fleet's operator channel is Telegram via the FRIDAY bot. Telegram's
``sendMessage`` requires ``chat_id`` and ``text``; the generic escalation
payloads carry neither and are rejected with HTTP 400 (verified locally
against the documented parameter handling). These tests pin the
translation both producers apply when ``SELF_HEALING_ESCALATION_WEBHOOK``
points at a Telegram ``sendMessage`` URL:

* ``cortex_core.resilience.EscalationNotifier`` (self-healing escalations)
* ``cortex_api.agent_budgets.WebhookBreachAlertSink`` (budget breaches)

Detection is by the real URL's host + method; delivery tests monkeypatch
the detector so the real classes can run against a local capture server.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import cortex_core.resilience as resilience
from cortex_api.agent_budgets import WebhookBreachAlertSink
from cortex_core.resilience import (
    TELEGRAM_CHAT_ID_ENV,
    EscalationNotifier,
    format_escalation_text,
    is_telegram_send_message_url,
    telegram_delivery_payload,
)

ESCALATION = {
    "subsystem": "database",
    "reason": "3 repair attempts did not restore health",
    "at": "2026-11-16T18:00:00+00:00",
}

ALERT = {
    "agent": "Futuris",
    "date": "2026-11-16",
    "reason": "daily token budget exhausted",
    "tokens_used": 500000,
    "token_budget": 500000,
    "tasks_used": 12,
    "task_budget": 40,
    "message": (
        "Futuris exhausted its daily budget (daily token budget "
        "exhausted); non-critical work auto-paused until UTC day rollover."
    ),
}


# ── URL detection ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://api.telegram.org/bot123456:ABC-DEF/sendMessage",
        "https://api.telegram.org/bot123456:ABC-DEF/sendMessage/",
        "https://API.TELEGRAM.ORG/bot1:x/sendMessage",
    ],
)
def test_detects_telegram_send_message_urls(url):
    assert is_telegram_send_message_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://api.telegram.org/bot123456:ABC-DEF/getMe",
        "https://api.telegram.org.evil.example/bot1:x/sendMessage",
        "https://sub.api.telegram.org/bot1:x/sendMessage",
        "https://example.com/ops/alerts",
        "http://127.0.0.1:9000/sendMessage",
        "",
        None,
    ],
)
def test_rejects_non_telegram_urls(url):
    assert is_telegram_send_message_url(url) is False


# ── Payload construction ─────────────────────────────────────────────────────


def test_payload_requires_the_chat_id_env(monkeypatch):
    monkeypatch.delenv(TELEGRAM_CHAT_ID_ENV, raising=False)
    payload, error = telegram_delivery_payload(dict(ESCALATION))
    assert payload is None
    assert TELEGRAM_CHAT_ID_ENV in error


def test_payload_numeric_chat_id_becomes_an_int(monkeypatch):
    monkeypatch.setenv(TELEGRAM_CHAT_ID_ENV, "-1001234567890")
    payload, error = telegram_delivery_payload(dict(ESCALATION))
    assert error is None
    assert payload["chat_id"] == -1001234567890
    assert "database" in payload["text"]
    assert "3 repair attempts did not restore health" in payload["text"]


def test_payload_channel_username_stays_a_string(monkeypatch):
    monkeypatch.setenv(TELEGRAM_CHAT_ID_ENV, "@ops_channel")
    payload, _ = telegram_delivery_payload(dict(ESCALATION))
    assert payload["chat_id"] == "@ops_channel"


def test_text_for_breach_payload_names_agent_and_message():
    text = format_escalation_text({"subsystem": "agent_budgets", **ALERT})
    assert "Futuris" in text
    assert "exhausted its daily budget" in text
    # The reason is already inside the message — not repeated as its own line.
    assert text.count("daily token budget exhausted") == 1


def test_text_is_truncated_to_telegrams_limit():
    text = format_escalation_text({"subsystem": "x", "reason": "r" * 10000})
    assert len(text) == 4096
    assert text.endswith("...")


# ── Delivery: capture server ─────────────────────────────────────────────────


class _CaptureHandler(BaseHTTPRequestHandler):
    captured: list[dict] = []

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        type(self).captured.append(json.loads(body.decode("utf-8")))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):  # keep the test output clean
        pass


class _capture_server:
    def __enter__(self):
        _CaptureHandler.captured = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_address[1]}/bot1:x/sendMessage"

    def __exit__(self, *exc):
        self._server.shutdown()
        self._thread.join(timeout=5)


@pytest.fixture
def telegram_mode(monkeypatch):
    """Force Telegram detection so the real classes can target localhost."""
    monkeypatch.setattr(resilience, "is_telegram_send_message_url", lambda url: True)


@pytest.mark.asyncio
async def test_notifier_sends_telegram_shape(monkeypatch, telegram_mode):
    monkeypatch.setenv(TELEGRAM_CHAT_ID_ENV, "12345")
    with _capture_server() as url:
        notifier = EscalationNotifier(webhook_url=url)
        record = await notifier.deliver(dict(ESCALATION))
    assert record["delivered"] is True
    assert len(_CaptureHandler.captured) == 1
    body = _CaptureHandler.captured[0]
    assert set(body) == {"chat_id", "text"}
    assert body["chat_id"] == 12345
    assert "database" in body["text"]


@pytest.mark.asyncio
async def test_notifier_without_chat_id_sends_nothing(monkeypatch, telegram_mode):
    monkeypatch.delenv(TELEGRAM_CHAT_ID_ENV, raising=False)
    with _capture_server() as url:
        notifier = EscalationNotifier(webhook_url=url)
        record = await notifier.deliver(dict(ESCALATION))
    assert record["delivered"] is False
    assert TELEGRAM_CHAT_ID_ENV in record["detail"]
    assert _CaptureHandler.captured == []


def test_sink_sends_telegram_shape(monkeypatch, telegram_mode):
    monkeypatch.setenv(TELEGRAM_CHAT_ID_ENV, "12345")
    with _capture_server() as url:
        sink = WebhookBreachAlertSink(webhook_url=url)
        record = sink(dict(ALERT))
    assert record["delivered"] is True
    assert len(_CaptureHandler.captured) == 1
    body = _CaptureHandler.captured[0]
    assert set(body) == {"chat_id", "text"}
    assert body["chat_id"] == 12345
    assert "Futuris" in body["text"]
    assert "exhausted its daily budget" in body["text"]


def test_sink_without_chat_id_sends_nothing(monkeypatch, telegram_mode):
    monkeypatch.delenv(TELEGRAM_CHAT_ID_ENV, raising=False)
    with _capture_server() as url:
        sink = WebhookBreachAlertSink(webhook_url=url)
        record = sink(dict(ALERT))
    assert record["delivered"] is False
    assert TELEGRAM_CHAT_ID_ENV in record["detail"]
    assert _CaptureHandler.captured == []


@pytest.mark.asyncio
async def test_notifier_generic_webhook_payload_is_unchanged():
    with _capture_server() as url:
        notifier = EscalationNotifier(webhook_url=url)
        record = await notifier.deliver(dict(ESCALATION))
    assert record["delivered"] is True
    assert _CaptureHandler.captured == [ESCALATION]
