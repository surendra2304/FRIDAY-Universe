"""
TASK-IG2-COR-01 — Per-agent budgets with enforcement (Paperclip pattern).

Each of the 10 agents gets a daily LLM-token + task-count budget tracked
in one Cortex ledger; breaching auto-pauses the agent's non-critical
work for the rest of the UTC day while critical work stays visible via
critical_override.
"""

from datetime import datetime, timedelta, timezone

import pytest

from cortex_api.agent_budgets import (
    FLEET_AGENTS,
    AgentBudget,
    BudgetLedger,
    InMemoryBudgetStore,
    default_budgets,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance_days(self, days: int) -> None:
        self.now += timedelta(days=days)


def small_ledger(clock=None):
    budgets = {
        agent: AgentBudget(agent, daily_token_budget=1_000, daily_task_budget=3)
        for agent in FLEET_AGENTS
    }
    return BudgetLedger(
        budgets=budgets, store=InMemoryBudgetStore(),
        now_fn=clock or FakeClock(),
    )


def test_default_budgets_cover_all_ten_agents():
    budgets = default_budgets()
    assert set(budgets) == set(FLEET_AGENTS)
    assert all(
        b.daily_token_budget > 0 and b.daily_task_budget > 0
        for b in budgets.values()
    )


def test_usage_within_budget_is_allowed_and_tracked():
    ledger = small_ledger()
    decision = ledger.record_usage("Stratex", tokens=400, tasks=1)
    assert decision.allowed and decision.reason == "ok"
    assert decision.tokens_used == 400 and decision.tokens_remaining == 600
    assert decision.tasks_used == 1 and decision.tasks_remaining == 2


def test_token_breach_pauses_and_denies_noncritical():
    ledger = small_ledger()
    ledger.record_usage("VyralX", tokens=900, tasks=1)
    decision = ledger.record_usage("VyralX", tokens=200, tasks=1)
    assert not decision.allowed
    assert decision.reason == "token_budget_exceeded"
    assert decision.paused is True
    # Denied usage is not recorded.
    assert decision.tokens_used == 900
    # And the agent stays paused for further non-critical work.
    follow_up = ledger.record_usage("VyralX", tokens=1, tasks=1)
    assert not follow_up.allowed and follow_up.reason == "paused"
    check = ledger.check("VyralX")
    assert not check.allowed and check.reason == "paused"


def test_task_breach_also_pauses():
    ledger = small_ledger()
    for _ in range(3):
        assert ledger.record_usage("Memora", tokens=10, tasks=1).allowed
    decision = ledger.record_usage("Memora", tokens=10, tasks=1)
    assert not decision.allowed
    assert decision.reason == "task_budget_exceeded"


def test_breach_alert_fires_once_per_agent_per_day():
    ledger = small_ledger()
    ledger.record_usage("Forge", tokens=2_000, tasks=1)
    ledger.record_usage("Forge", tokens=2_000, tasks=1)
    alerts = [a for a in ledger.alerts() if a["agent"] == "Forge"]
    assert len(alerts) == 1
    assert "auto-paused" in alerts[0]["message"]


def test_critical_work_overrides_pause_but_stays_visible():
    ledger = small_ledger()
    ledger.record_usage("FRIDAY", tokens=2_000, tasks=1)  # breach + pause
    decision = ledger.record_usage(
        "FRIDAY", tokens=100, tasks=1, critical=True
    )
    assert decision.allowed and decision.critical_override is True
    assert decision.paused is True
    assert decision.tokens_used == 100  # breach request itself not recorded,
    # only the critical override is


def test_budgets_are_per_agent():
    ledger = small_ledger()
    ledger.record_usage("IntelX", tokens=2_000, tasks=1)  # IntelX paused
    decision = ledger.record_usage("Futuris", tokens=500, tasks=1)
    assert decision.allowed and not decision.paused


def test_day_rollover_resets_usage_and_pause():
    clock = FakeClock()
    ledger = small_ledger(clock)
    ledger.record_usage("Cortex", tokens=2_000, tasks=1)
    assert ledger.check("Cortex").allowed is False
    clock.advance_days(1)
    decision = ledger.record_usage("Cortex", tokens=10, tasks=1)
    assert decision.allowed and decision.tokens_used == 10
    assert decision.paused is False


def test_unknown_agent_is_rejected():
    ledger = small_ledger()
    with pytest.raises(ValueError):
        ledger.record_usage("NotAnAgent", tokens=1, tasks=1)
    with pytest.raises(ValueError):
        ledger.usage_snapshot("NotAnAgent")


def test_negative_usage_is_rejected():
    ledger = small_ledger()
    with pytest.raises(ValueError):
        ledger.record_usage("Sentinel", tokens=-5, tasks=1)


def test_operator_reset_unpauses():
    ledger = small_ledger()
    ledger.record_usage("Inference", tokens=2_000, tasks=1)
    assert ledger.check("Inference").allowed is False
    ledger.reset_agent("Inference")
    assert ledger.check("Inference").allowed is True


def test_state_survives_ledger_recreation_via_store():
    store = InMemoryBudgetStore()
    budgets = {
        agent: AgentBudget(agent, 1_000, 3) for agent in FLEET_AGENTS
    }
    clock = FakeClock()
    BudgetLedger(budgets, store, clock).record_usage(
        "Stratex", tokens=700, tasks=2
    )
    snapshot = BudgetLedger(budgets, store, clock).usage_snapshot("Stratex")
    assert snapshot["tokens_used"] == 700 and snapshot["tasks_used"] == 2


def test_router_serves_budget_endpoints():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from cortex_api import agent_budgets

    if agent_budgets.router is None:
        pytest.skip("FastAPI unavailable")
    app = FastAPI()
    app.include_router(agent_budgets.router)
    client = TestClient(app)
    listing = client.get("/api/v1/cortex/budgets")
    assert listing.status_code == 200
    assert set(listing.json()["budgets"]) == set(FLEET_AGENTS)
    one = client.get("/api/v1/cortex/budgets/Stratex")
    assert one.status_code == 200 and one.json()["agent"] == "Stratex"
    missing = client.get("/api/v1/cortex/budgets/Nope")
    assert missing.status_code == 404


def test_router_post_usage_reports_tokens_and_enforces_token_budget(monkeypatch):
    """TASK-CTX-008: the token-reporting seam, proven through the HTTP surface.

    ``POST /api/v1/cortex/budgets/usage`` is the ledger's only token-reporting
    surface: no in-repo LLM caller produces tokens (Cortex's cognitive
    modules are deterministic heuristics), so the endpoint itself must be
    shown to charge tokens, enforce the token budget with 429, and fire
    the breach alert exactly once.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from cortex_api import agent_budgets

    if agent_budgets.router is None:
        pytest.skip("FastAPI unavailable")
    monkeypatch.setattr(agent_budgets, "ledger", small_ledger())
    app = FastAPI()
    app.include_router(agent_budgets.router)
    client = TestClient(app)

    ok = client.post(
        "/api/v1/cortex/budgets/usage",
        json={"agent": "Cortex", "tokens": 600, "tasks": 0},
    )
    assert ok.status_code == 200
    assert ok.json()["tokens_used"] == 600
    assert ok.json()["tokens_remaining"] == 400

    breach = client.post(
        "/api/v1/cortex/budgets/usage",
        json={"agent": "Cortex", "tokens": 500, "tasks": 0},
    )
    assert breach.status_code == 429

    snapshot = client.get("/api/v1/cortex/budgets/Cortex")
    assert snapshot.status_code == 200
    assert snapshot.json()["tokens_used"] == 600
    assert snapshot.json()["paused"] is True
    assert snapshot.json()["token_budget"] == 1_000

    assert [a["agent"] for a in agent_budgets.ledger.alerts()] == ["Cortex"]
