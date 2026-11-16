"""TASK-IG2-COR-01 wiring — closing the three gaps that kept COR-01 PARTIAL.

The budget ledger shipped in PR #703 as a library: correct, tested, and
unused by the running system. These tests pin the wiring, each at the
production path it closes:

1. NO PRODUCTION CALLER — envelopes driven through the real
   ``process_task_envelope`` executor are gated and charged to the
   Cortex budget line; a breach denies the envelope with HTTP 429
   before any task is created.
2. IN-MEMORY STORE ONLY — ``DatabaseBudgetStore`` round-trips ledger
   state through a real database so a restart (new store + ledger
   objects, same database) restores counters, pauses and alerts; and
   it degrades to its mirror, loudly, when the database is down.
3. BREACH ALERTS NEVER DISPATCHED — a breach hands exactly one alert
   to the ledger's sink; the production sink delivers it over Cortex's
   operator escalation webhook, and every outcome is recorded.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from cortex_api import friday_router as fr
from cortex_api.agent_budgets import (
    FLEET_AGENTS,
    AgentBudget,
    BudgetLedger,
    DatabaseBudgetStore,
    InMemoryBudgetStore,
    WebhookBreachAlertSink,
)
from cortex_api.db_models import AgentBudgetStateModel
from cortex_core.task_manager import global_task_manager


def _budgets(task_budget: int = 3, token_budget: int = 1_000_000):
    return {
        agent: AgentBudget(
            agent, daily_token_budget=token_budget, daily_task_budget=task_budget
        )
        for agent in FLEET_AGENTS
    }


def _ledger(task_budget: int = 3, sink=None, store=None):
    return BudgetLedger(
        budgets=_budgets(task_budget=task_budget),
        store=store if store is not None else InMemoryBudgetStore(),
        alert_sink=sink,
    )


def _envelope(task_id: str, **overrides):
    fields = {
        "task_id": task_id,
        "action": "recommend_intervention",
        "payload": {"property_id": "site_storefront"},
    }
    fields.update(overrides)
    return fr.FridayTaskEnvelope(**fields)


# ── Gap 1: the dispatch path actually calls the gate ─────────────────────


@pytest.mark.asyncio
async def test_envelope_execution_is_charged_to_the_cortex_budget(monkeypatch):
    ledger = _ledger(task_budget=3)
    monkeypatch.setattr(fr, "agent_budget_ledger", ledger)

    resp = await fr.process_task_envelope(_envelope("wiring_charge_1"))

    assert resp.task_id == "wiring_charge_1"
    snapshot = ledger.usage_snapshot("Cortex")
    assert snapshot["tasks_used"] == 1
    assert snapshot["tasks_remaining"] == 2


@pytest.mark.asyncio
async def test_envelope_is_denied_with_429_once_the_budget_is_spent(monkeypatch):
    ledger = _ledger(task_budget=1)
    monkeypatch.setattr(fr, "agent_budget_ledger", ledger)

    await fr.process_task_envelope(_envelope("wiring_deny_1"))
    with pytest.raises(HTTPException) as excinfo:
        await fr.process_task_envelope(_envelope("wiring_deny_2"))

    assert excinfo.value.status_code == 429
    assert "agent budget" in excinfo.value.detail
    # The denied envelope never reached routing: no task was created and
    # the denied usage was not recorded.
    assert global_task_manager.get_task("wiring_deny_2") is None
    assert ledger.usage_snapshot("Cortex")["tasks_used"] == 1


@pytest.mark.asyncio
async def test_critical_envelope_still_executes_while_paused(monkeypatch):
    ledger = _ledger(task_budget=1)
    monkeypatch.setattr(fr, "agent_budget_ledger", ledger)

    await fr.process_task_envelope(_envelope("wiring_crit_1"))
    # A further non-critical envelope breaches the budget and pauses Cortex.
    with pytest.raises(HTTPException):
        await fr.process_task_envelope(_envelope("wiring_crit_2"))
    assert ledger.check("Cortex").allowed is False
    assert ledger.check("Cortex").reason == "paused"

    resp = await fr.process_task_envelope(
        _envelope("wiring_crit_3", priority="CRITICAL")
    )
    assert resp.task_id == "wiring_crit_3"
    # The override is visible in the accounting, not silent.
    assert ledger.usage_snapshot("Cortex")["tasks_used"] == 2


@pytest.mark.asyncio
async def test_health_summary_and_dry_run_are_never_gated(monkeypatch):
    ledger = _ledger(task_budget=1)
    monkeypatch.setattr(fr, "agent_budget_ledger", ledger)

    await fr.process_task_envelope(_envelope("wiring_exempt_1"))
    with pytest.raises(HTTPException):
        await fr.process_task_envelope(_envelope("wiring_exempt_2"))
    assert ledger.check("Cortex").reason == "paused"  # budget breached

    health = await fr.process_task_envelope(
        _envelope("wiring_exempt_health", action="health_summary")
    )
    assert health.status == "SUCCESS"

    await fr.process_task_envelope(_envelope("wiring_exempt_dry", dry_run=True))
    # Neither exempt call consumed budget.
    assert ledger.usage_snapshot("Cortex")["tasks_used"] == 1


# ── Gap 2: budget state survives a restart ───────────────────────────────


def _db_session_factory(tmp_path):
    # NullPool (the Cortex conftest pattern): every session opens a fresh
    # connection on the calling loop — the store drives this engine from
    # its own thread's loop, never the test's.
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/budgets.db", poolclass=NullPool
    )

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda c: AgentBudgetStateModel.__table__.create(c, checkfirst=True)
            )

    asyncio.run(_create())
    return async_sessionmaker(engine, expire_on_commit=False)


def test_database_store_restores_state_across_a_restart(tmp_path):
    factory = _db_session_factory(tmp_path)

    store1 = DatabaseBudgetStore(session_factory=factory)
    ledger1 = BudgetLedger(budgets=_budgets(), store=store1)
    ledger1.record_usage("Stratex", tokens=400, tasks=1)
    decision = ledger1.record_usage("Cortex", tokens=0, tasks=3)
    assert decision.allowed  # third task still fits the budget of 3
    breach = ledger1.record_usage("Cortex", tokens=0, tasks=1)
    assert breach.allowed is False and breach.reason == "task_budget_exceeded"
    assert store1.status()["durable"] is True

    # Simulated restart: brand-new store and ledger over the same database.
    store2 = DatabaseBudgetStore(session_factory=factory)
    ledger2 = BudgetLedger(budgets=_budgets(), store=store2)

    snapshot = ledger2.usage_snapshot("Stratex")
    assert snapshot["tokens_used"] == 400 and snapshot["tasks_used"] == 1
    # The pause and the breach record survived too.
    assert ledger2.check("Cortex").allowed is False
    assert ledger2.check("Cortex").reason == "paused"
    assert [a["agent"] for a in ledger2.alerts()] == ["Cortex"]


def test_database_store_degrades_to_mirror_when_database_is_down():
    def dead_factory():
        raise RuntimeError("database is down")

    store = DatabaseBudgetStore(session_factory=dead_factory)
    ledger = BudgetLedger(budgets=_budgets(), store=store)
    decision = ledger.record_usage("Stratex", tokens=10, tasks=1)

    # Enforcement never depends on the store being up…
    assert decision.allowed and decision.tokens_used == 10
    # …but the degradation is explicit, not silent.
    status = store.status()
    assert status["durable"] is False
    assert status["save_errors"] >= 1
    assert "database is down" in (status["last_error"] or "")


# ── Gap 3: breach alerts are dispatched, not just recorded ───────────────


def test_breach_dispatches_exactly_one_alert_to_the_sink():
    sent: list[dict] = []

    def sink(alert):
        sent.append(alert)
        return {"delivered": True, "channel": "test", "detail": "delivered"}

    ledger = _ledger(task_budget=1, sink=sink)
    ledger.record_usage("Stratex", tokens=0, tasks=1)
    denied = ledger.record_usage("Stratex", tokens=0, tasks=1)
    assert denied.allowed is False

    assert len(sent) == 1
    assert sent[0]["agent"] == "Stratex"
    assert sent[0]["reason"] == "task_budget_exceeded"
    assert "auto-paused" in sent[0]["message"]

    # Further denied work the same day does not re-dispatch.
    ledger.record_usage("Stratex", tokens=0, tasks=1)
    assert len(sent) == 1
    deliveries = ledger.alert_deliveries()
    assert len(deliveries) == 1 and deliveries[0]["delivered"] is True


def test_sink_failure_never_breaks_the_gate():
    def broken_sink(alert):
        raise RuntimeError("channel exploded")

    ledger = _ledger(task_budget=1, sink=broken_sink)
    ledger.record_usage("Stratex", tokens=0, tasks=1)
    denied = ledger.record_usage("Stratex", tokens=0, tasks=1)

    assert denied.allowed is False and denied.paused is True
    deliveries = ledger.alert_deliveries()
    assert len(deliveries) == 1
    assert deliveries[0]["delivered"] is False
    assert "alert sink raised" in deliveries[0]["detail"]


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


def test_production_sink_delivers_the_breach_over_the_webhook():
    _CaptureHandler.captured = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/escalate"
        sink = WebhookBreachAlertSink(webhook_url=url)
        ledger = _ledger(task_budget=1, sink=sink)
        ledger.record_usage("Cortex", tokens=0, tasks=1)
        ledger.record_usage("Cortex", tokens=0, tasks=1)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert len(_CaptureHandler.captured) == 1
    payload = _CaptureHandler.captured[0]
    assert payload["subsystem"] == "agent_budgets"
    assert payload["agent"] == "Cortex"
    assert "exhausted its daily budget" in payload["message"]
    deliveries = ledger.alert_deliveries()
    assert deliveries[0]["delivered"] is True
    assert deliveries[0]["status_code"] == 200


def test_production_sink_without_a_channel_records_not_delivered():
    sink = WebhookBreachAlertSink(webhook_url="")
    ledger = _ledger(task_budget=1, sink=sink)
    ledger.record_usage("Cortex", tokens=0, tasks=1)
    ledger.record_usage("Cortex", tokens=0, tasks=1)

    deliveries = ledger.alert_deliveries()
    assert len(deliveries) == 1
    assert deliveries[0]["delivered"] is False
    assert deliveries[0]["channel"] == "none"
    assert "SELF_HEALING_ESCALATION_WEBHOOK" in deliveries[0]["detail"]


@pytest.mark.asyncio
async def test_breach_on_the_envelope_path_dispatches_the_alert(monkeypatch):
    sent: list[dict] = []

    def sink(alert):
        sent.append(alert)
        return {"delivered": True, "channel": "test", "detail": "delivered"}

    ledger = _ledger(task_budget=1, sink=sink)
    monkeypatch.setattr(fr, "agent_budget_ledger", ledger)

    await fr.process_task_envelope(_envelope("wiring_alert_1"))
    with pytest.raises(HTTPException):
        await fr.process_task_envelope(_envelope("wiring_alert_2"))

    assert len(sent) == 1 and sent[0]["agent"] == "Cortex"


# ── Gap 3b: the production sink speaks Telegram when the channel is Telegram ──

_TELEGRAM_URL = "https://api.telegram.org/bot123456:SECRET-TOKEN/sendMessage"


class _FakeSyncResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def _capture_httpx_post(monkeypatch, status_code: int = 200, body=None):
    """Stand in for the sync ``httpx.post`` the sink uses; records calls."""
    import httpx

    calls: list[dict] = []

    def _post(url, json=None, timeout=None, trust_env=None):
        calls.append({"url": url, "json": json})
        return _FakeSyncResponse(status_code, {"ok": True, "result": {}} if body is None else body)

    monkeypatch.setattr(httpx, "post", _post)
    return calls


def test_production_sink_telegram_mode_posts_chat_id_and_text(monkeypatch):
    calls = _capture_httpx_post(monkeypatch, status_code=200, body={"ok": True, "result": {"message_id": 7}})
    sink = WebhookBreachAlertSink(webhook_url=_TELEGRAM_URL, telegram_chat_id="4242")
    ledger = _ledger(task_budget=1, sink=sink)
    ledger.record_usage("Cortex", tokens=0, tasks=1)
    ledger.record_usage("Cortex", tokens=0, tasks=1)

    assert len(calls) == 1
    assert calls[0]["url"] == _TELEGRAM_URL
    body = calls[0]["json"]
    assert set(body) == {"chat_id", "text"}
    assert body["chat_id"] == "4242"
    assert "Subsystem: agent_budgets (agent: Cortex)" in body["text"]
    assert "exhausted its daily budget" in body["text"]

    deliveries = ledger.alert_deliveries()
    assert deliveries[0]["delivered"] is True
    # The delivery record must never carry the bot token.
    assert "SECRET-TOKEN" not in json.dumps(deliveries)
    assert deliveries[0]["channel"] == "https://api.telegram.org/bot***/sendMessage"


def test_production_sink_telegram_ok_false_is_not_delivered(monkeypatch):
    calls = _capture_httpx_post(
        monkeypatch,
        status_code=400,
        body={"ok": False, "error_code": 400, "description": "Bad Request: chat not found"},
    )
    sink = WebhookBreachAlertSink(webhook_url=_TELEGRAM_URL, telegram_chat_id="4242")
    ledger = _ledger(task_budget=1, sink=sink)
    ledger.record_usage("Cortex", tokens=0, tasks=1)
    ledger.record_usage("Cortex", tokens=0, tasks=1)

    assert len(calls) == 1
    deliveries = ledger.alert_deliveries()
    assert deliveries[0]["delivered"] is False
    assert deliveries[0]["status_code"] == 400
    assert "chat not found" in deliveries[0]["detail"]


def test_production_sink_non_telegram_payload_is_unchanged(monkeypatch):
    """Regression guard: generic-webhook mode keeps today's payload shape."""
    calls = _capture_httpx_post(monkeypatch, status_code=200)
    sink = WebhookBreachAlertSink(webhook_url="http://ops.local/alerts")
    ledger = _ledger(task_budget=1, sink=sink)
    ledger.record_usage("Cortex", tokens=0, tasks=1)
    ledger.record_usage("Cortex", tokens=0, tasks=1)

    assert len(calls) == 1
    payload = calls[0]["json"]
    assert set(payload) == {"subsystem", "reason", "agent", "message", "alert"}
    assert payload["subsystem"] == "agent_budgets"
    assert payload["agent"] == "Cortex"
    assert ledger.alert_deliveries()[0]["delivered"] is True
