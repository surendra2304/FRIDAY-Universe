"""Escalation delivery records must never carry the webhook URL.

Both escalation producers — ``EscalationNotifier`` (self-healing) and
``WebhookBreachAlertSink`` (budget breaches) — record ``channel`` in
delivery records that persist (the budget store) and are endpoint-exposed
(``GET /api/v1/cortex/budgets``, the notifier status surface). A Telegram
``sendMessage`` URL embeds the bot token in its path, so the record may
only name the channel by its redacted descriptor (kind + host). Delivery
itself must still post to the full URL taken from the environment.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from cortex_api.agent_budgets import (
    FLEET_AGENTS,
    AgentBudget,
    BudgetLedger,
    InMemoryBudgetStore,
    WebhookBreachAlertSink,
)
from cortex_core.resilience import EscalationNotifier, channel_descriptor

TOKEN = "123456789:FAKEtoken_MARKER_zzz"
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
GENERIC_URL = "https://hooks.example.net/ops/SECRETpath123?key=SECRETquery456"


def _run(coro):
    return asyncio.run(coro)


# ── descriptor shapes ────────────────────────────────────────────────────


def test_channel_descriptor_shapes():
    assert channel_descriptor(None) == "none"
    assert channel_descriptor("") == "none"
    assert channel_descriptor(TELEGRAM_URL) == "telegram:api.telegram.org"
    assert channel_descriptor(GENERIC_URL) == "webhook:hooks.example.net"
    assert channel_descriptor("http://127.0.0.1:9000/escalate") == "webhook:127.0.0.1"
    # Unparseable values are never echoed back — they could be anything.
    assert channel_descriptor("not a url at all") == "webhook:unknown"


# ── EscalationNotifier ───────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeClient:
    """Stands in for httpx.AsyncClient; records calls or raises on demand."""

    calls: list[dict] = []
    status_code = 200
    raise_on_post: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):
        if _FakeClient.raise_on_post is not None:
            raise _FakeClient.raise_on_post
        _FakeClient.calls.append({"url": url, "json": json})
        return _FakeResponse(_FakeClient.status_code)


@pytest.fixture()
def fake_http(monkeypatch):
    import httpx

    _FakeClient.calls = []
    _FakeClient.status_code = 200
    _FakeClient.raise_on_post = None
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    yield _FakeClient
    _FakeClient.calls = []
    _FakeClient.raise_on_post = None


def test_notifier_record_and_status_redacted_delivery_uses_full_url(fake_http):
    notifier = EscalationNotifier(webhook_url=TELEGRAM_URL, dedupe_window_seconds=0)
    record = _run(notifier.deliver({"subsystem": "redis", "reason": "down"}))

    assert record["delivered"] is True
    assert record["channel"] == "telegram:api.telegram.org"
    blob = json.dumps(record) + json.dumps(notifier.status())
    assert TOKEN not in blob
    assert "/sendMessage" not in blob
    assert "bot" + TOKEN.split(":")[0] not in blob
    # Delivery itself still went to the full URL from the environment.
    assert fake_http.calls[0]["url"] == TELEGRAM_URL
    assert notifier.status()["channel"] == "telegram:api.telegram.org"
    assert notifier.status()["channel_configured"] is True


def test_notifier_generic_webhook_record_is_host_only(fake_http):
    notifier = EscalationNotifier(webhook_url=GENERIC_URL, dedupe_window_seconds=0)
    record = _run(notifier.deliver({"subsystem": "redis", "reason": "down"}))

    assert record["channel"] == "webhook:hooks.example.net"
    blob = json.dumps(record)
    assert "SECRETpath123" not in blob
    assert "SECRETquery456" not in blob
    assert fake_http.calls[0]["url"] == GENERIC_URL


def test_notifier_exception_detail_is_scrubbed(fake_http):
    fake_http.raise_on_post = ConnectionError(f"dial failed for {TELEGRAM_URL}")
    notifier = EscalationNotifier(webhook_url=TELEGRAM_URL, dedupe_window_seconds=0)
    record = _run(notifier.deliver({"subsystem": "redis", "reason": "down"}))

    assert record["delivered"] is False
    assert TOKEN not in json.dumps(record)
    assert "telegram:api.telegram.org" in record["detail"]


# ── WebhookBreachAlertSink ───────────────────────────────────────────────


class _FakePostResponse:
    status_code = 200


@pytest.fixture()
def fake_post(monkeypatch):
    import httpx

    calls: list[dict] = []

    def _post(url, json=None, timeout=None, trust_env=None):
        calls.append({"url": url, "json": json})
        return _FakePostResponse()

    monkeypatch.setattr(httpx, "post", _post)
    return calls


def _alert() -> dict:
    return {
        "agent": "Cortex",
        "date": "2026-11-17",
        "reason": "task_budget_exceeded",
        "message": "Cortex exhausted its daily budget",
    }


def test_sink_record_redacted_but_posts_to_full_url(fake_post):
    sink = WebhookBreachAlertSink(webhook_url=TELEGRAM_URL)
    record = sink(_alert())

    assert record["delivered"] is True
    assert record["channel"] == "telegram:api.telegram.org"
    blob = json.dumps(record)
    assert TOKEN not in blob
    assert "/sendMessage" not in blob
    assert fake_post[0]["url"] == TELEGRAM_URL


def test_sink_generic_webhook_record_is_host_only(fake_post):
    sink = WebhookBreachAlertSink(webhook_url=GENERIC_URL)
    record = sink(_alert())

    assert record["channel"] == "webhook:hooks.example.net"
    blob = json.dumps(record)
    assert "SECRETpath123" not in blob
    assert "SECRETquery456" not in blob


def test_sink_exception_detail_is_scrubbed(monkeypatch):
    import httpx

    def _boom(url, json=None, timeout=None, trust_env=None):
        raise RuntimeError(f"POST {TELEGRAM_URL} failed")

    monkeypatch.setattr(httpx, "post", _boom)
    sink = WebhookBreachAlertSink(webhook_url=TELEGRAM_URL)
    record = sink(_alert())

    assert record["delivered"] is False
    assert TOKEN not in json.dumps(record)
    assert "telegram:api.telegram.org" in record["detail"]


def test_sink_without_a_channel_still_records_none():
    sink = WebhookBreachAlertSink(webhook_url="")
    record = sink(_alert())
    assert record["channel"] == "none"
    assert record["delivered"] is False


def test_breach_delivery_persists_redacted_through_the_ledger(fake_post):
    budgets = {
        agent: AgentBudget(agent, daily_token_budget=1_000_000, daily_task_budget=1)
        for agent in FLEET_AGENTS
    }
    store = InMemoryBudgetStore()
    ledger = BudgetLedger(
        budgets=budgets,
        store=store,
        alert_sink=WebhookBreachAlertSink(webhook_url=TELEGRAM_URL),
    )
    ledger.record_usage("Cortex", tokens=0, tasks=1)
    ledger.record_usage("Cortex", tokens=0, tasks=1)  # breach → dispatch

    deliveries = ledger.alert_deliveries()
    assert len(deliveries) == 1
    assert deliveries[0]["channel"] == "telegram:api.telegram.org"
    # The persisted state is what the budgets endpoint serves — no token.
    assert TOKEN not in json.dumps(store.load())
    assert TOKEN not in json.dumps(deliveries)
    assert fake_post[0]["url"] == TELEGRAM_URL
