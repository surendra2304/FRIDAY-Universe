"""
Cortex/apps/api/src/cortex_api/agent_budgets.py — Per-agent budgets with
enforcement (Paperclip pattern).

TASK-IG2-COR-01: Paperclip (paperclipai/paperclip, MIT) runs agent teams
with per-agent budgets and governance. FRIDAY cannot run another Node
orchestration server on ~1GB VMs, so the pattern lands here as a Cortex
ledger instead: every one of the 10 agents gets a daily budget of LLM
tokens and task count, usage is tracked in one ledger, and when an agent
exhausts its budget its non-critical work is auto-paused for the rest of
the day — one hungry agent can no longer starve the other nine (free-tier
quota exhaustion has already cascaded into fleet-wide voice failures).

Semantics
---------
- ``record_usage`` is the enforcement point for the dispatch path: if the
  requested usage would breach either budget, the agent is paused, a
  breach alert is recorded (once per agent per day), and the request is
  denied — the usage is NOT recorded.
- Critical work is never hard-blocked: it is recorded, allowed, and
  flagged ``critical_override`` so the breach stays visible.
- Counters reset on UTC day rollover; a pause lasts only for its day.
- Unknown agents are rejected (ValueError): an agent with no budget line
  must not spend unbudgeted quota by accident.

Persistence: the ledger core talks to a ``BudgetStore`` protocol. The
default store is in-memory (single-process Cortex); production wiring
should back it with Cortex's Oracle schema (repo rule: no local SQLite
files for Cortex data) — the protocol is the seam for that.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

# The 10 fleet agents (AGENTS.yaml v3.0.0).
FLEET_AGENTS: tuple[str, ...] = (
    "FRIDAY", "Inference", "Memora", "Stratex", "Futuris",
    "IntelX", "Forge", "Sentinel", "Cortex", "VyralX",
)

# Default daily budgets: (llm_tokens, tasks). Sized for free-tier pools:
# FRIDAY (voice + orchestration) and Inference (the gateway itself) get
# the largest lines; quiet agents get small ones so a runaway loop is
# caught early. Override per agent via env, e.g.
# CORTEX_AGENT_BUDGET_STRATEX_TOKENS=900000.
_DEFAULT_BUDGETS: dict[str, tuple[int, int]] = {
    "FRIDAY": (2_000_000, 2_000),
    "Inference": (5_000_000, 5_000),
    "Memora": (500_000, 500),
    "Stratex": (750_000, 750),
    "Futuris": (750_000, 750),
    "IntelX": (1_000_000, 1_000),
    "Forge": (1_500_000, 1_000),
    "Sentinel": (500_000, 500),
    "Cortex": (750_000, 750),
    "VyralX": (1_000_000, 1_000),
}


@dataclass(frozen=True)
class AgentBudget:
    agent: str
    daily_token_budget: int
    daily_task_budget: int


def default_budgets() -> dict[str, AgentBudget]:
    """Fleet default budgets with per-agent env overrides."""
    budgets: dict[str, AgentBudget] = {}
    for agent, (tokens, tasks) in _DEFAULT_BUDGETS.items():
        token_override = os.environ.get(f"CORTEX_AGENT_BUDGET_{agent.upper()}_TOKENS")
        task_override = os.environ.get(f"CORTEX_AGENT_BUDGET_{agent.upper()}_TASKS")
        budgets[agent] = AgentBudget(
            agent=agent,
            daily_token_budget=int(token_override) if token_override else tokens,
            daily_task_budget=int(task_override) if task_override else tasks,
        )
    return budgets


@dataclass
class BudgetDecision:
    allowed: bool
    reason: str            # ok | token_budget_exceeded | task_budget_exceeded | paused | critical_override
    agent: str
    tokens_used: int
    tokens_remaining: int
    tasks_used: int
    tasks_remaining: int
    paused: bool
    critical_override: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed, "reason": self.reason,
            "agent": self.agent, "tokens_used": self.tokens_used,
            "tokens_remaining": self.tokens_remaining,
            "tasks_used": self.tasks_used,
            "tasks_remaining": self.tasks_remaining,
            "paused": self.paused,
            "critical_override": self.critical_override,
        }


class BudgetStore(Protocol):
    def load(self) -> dict[str, Any]: ...
    def save(self, state: dict[str, Any]) -> None: ...


class InMemoryBudgetStore:
    """Single-process store (default). See module docstring for the
    production (Oracle-schema) persistence seam."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        return self._state

    def save(self, state: dict[str, Any]) -> None:
        self._state = state


@dataclass
class _DayUsage:
    date: str
    tokens_used: int = 0
    tasks_used: int = 0
    paused: bool = False
    breach_alerted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.date, "tokens_used": self.tokens_used,
            "tasks_used": self.tasks_used, "paused": self.paused,
            "breach_alerted": self.breach_alerted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "_DayUsage":
        return cls(
            date=str(data["date"]), tokens_used=int(data.get("tokens_used", 0)),
            tasks_used=int(data.get("tasks_used", 0)),
            paused=bool(data.get("paused", False)),
            breach_alerted=bool(data.get("breach_alerted", False)),
        )


class BudgetLedger:
    """One ledger tracking every agent's daily budget with enforcement."""

    def __init__(
        self,
        budgets: dict[str, AgentBudget] | None = None,
        store: BudgetStore | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.budgets = budgets if budgets is not None else default_budgets()
        self.store = store if store is not None else InMemoryBudgetStore()
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._alerts: list[dict[str, Any]] = []
        stored = self.store.load() or {}
        self._usage: dict[str, _DayUsage] = {
            agent: _DayUsage.from_dict(data)
            for agent, data in stored.get("usage", {}).items()
            if agent in self.budgets
        }

    # -- internals ---------------------------------------------------------
    def _today(self) -> str:
        return self._now_fn().date().isoformat()

    def _budget_for(self, agent: str) -> AgentBudget:
        try:
            return self.budgets[agent]
        except KeyError:
            raise ValueError(
                f"unknown agent {agent!r}: no budget line exists for it"
            ) from None

    def _usage_for(self, agent: str) -> _DayUsage:
        usage = self._usage.get(agent)
        if usage is None or usage.date != self._today():
            usage = _DayUsage(date=self._today())
            self._usage[agent] = usage
        return usage

    def _persist(self) -> None:
        self.store.save({
            "usage": {a: u.as_dict() for a, u in self._usage.items()},
        })

    def _decision(
        self, budget: AgentBudget, usage: _DayUsage, allowed: bool,
        reason: str, critical_override: bool = False,
    ) -> BudgetDecision:
        return BudgetDecision(
            allowed=allowed, reason=reason, agent=budget.agent,
            tokens_used=usage.tokens_used,
            tokens_remaining=max(
                0, budget.daily_token_budget - usage.tokens_used
            ),
            tasks_used=usage.tasks_used,
            tasks_remaining=max(
                0, budget.daily_task_budget - usage.tasks_used
            ),
            paused=usage.paused, critical_override=critical_override,
        )

    def _breach(
        self, budget: AgentBudget, usage: _DayUsage, reason: str,
    ) -> None:
        usage.paused = True
        if not usage.breach_alerted:
            usage.breach_alerted = True
            self._alerts.append({
                "agent": budget.agent, "date": usage.date, "reason": reason,
                "tokens_used": usage.tokens_used,
                "token_budget": budget.daily_token_budget,
                "tasks_used": usage.tasks_used,
                "task_budget": budget.daily_task_budget,
                "message": (
                    f"{budget.agent} exhausted its daily budget "
                    f"({reason}); non-critical work auto-paused until "
                    "UTC day rollover."
                ),
            })
        self._persist()

    # -- enforcement -------------------------------------------------------
    def check(self, agent: str, *, critical: bool = False) -> BudgetDecision:
        """Would a unit of work be allowed right now? (No recording.)"""
        budget = self._budget_for(agent)
        usage = self._usage_for(agent)
        if usage.paused and not critical:
            return self._decision(budget, usage, False, "paused")
        if usage.paused and critical:
            return self._decision(
                budget, usage, True, "critical_override", critical_override=True
            )
        return self._decision(budget, usage, True, "ok")

    def record_usage(
        self, agent: str, *, tokens: int = 0, tasks: int = 1,
        critical: bool = False,
    ) -> BudgetDecision:
        """Record usage, enforcing the budget. The dispatch-path gate."""
        if tokens < 0 or tasks < 0:
            raise ValueError("usage cannot be negative")
        budget = self._budget_for(agent)
        usage = self._usage_for(agent)

        if usage.paused:
            if not critical:
                return self._decision(budget, usage, False, "paused")
            usage.tokens_used += tokens
            usage.tasks_used += tasks
            self._persist()
            return self._decision(
                budget, usage, True, "critical_override", critical_override=True
            )

        over_tokens = usage.tokens_used + tokens > budget.daily_token_budget
        over_tasks = usage.tasks_used + tasks > budget.daily_task_budget
        if over_tokens or over_tasks:
            reason = (
                "token_budget_exceeded" if over_tokens
                else "task_budget_exceeded"
            )
            self._breach(budget, usage, reason)
            if not critical:
                return self._decision(budget, usage, False, reason)
            usage.tokens_used += tokens
            usage.tasks_used += tasks
            self._persist()
            return self._decision(
                budget, usage, True, "critical_override", critical_override=True
            )

        usage.tokens_used += tokens
        usage.tasks_used += tasks
        self._persist()
        return self._decision(budget, usage, True, "ok")

    # -- reporting ---------------------------------------------------------
    def usage_snapshot(self, agent: str) -> dict[str, Any]:
        budget = self._budget_for(agent)
        return self._decision(
            budget, self._usage_for(agent), True, "ok"
        ).as_dict() | {
            "token_budget": budget.daily_token_budget,
            "task_budget": budget.daily_task_budget,
            "date": self._today(),
        }

    def all_usage(self) -> dict[str, Any]:
        return {agent: self.usage_snapshot(agent) for agent in self.budgets}

    def alerts(self) -> list[dict[str, Any]]:
        return list(self._alerts)

    def reset_agent(self, agent: str) -> None:
        """Operator override: clear today's usage and unpause an agent."""
        self._budget_for(agent)
        self._usage[agent] = _DayUsage(date=self._today())
        self._persist()


# ── HTTP surface ─────────────────────────────────────────────────────────
try:  # pragma: no cover - exercised via the mounted app in integration tests
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    router = APIRouter(tags=["Agent Budgets"])
    ledger = BudgetLedger()

    class UsageRequest(BaseModel):
        agent: str
        tokens: int = 0
        tasks: int = 1
        critical: bool = False

    @router.get("/api/v1/cortex/budgets")
    async def list_budgets() -> dict[str, Any]:
        return {"budgets": ledger.all_usage(), "alerts": ledger.alerts()}

    @router.get("/api/v1/cortex/budgets/{agent}")
    async def get_budget(agent: str) -> dict[str, Any]:
        try:
            return ledger.usage_snapshot(agent)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post("/api/v1/cortex/budgets/usage")
    async def post_usage(request: UsageRequest) -> dict[str, Any]:
        try:
            decision = ledger.record_usage(
                request.agent, tokens=request.tokens, tasks=request.tasks,
                critical=request.critical,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if not decision.allowed:
            raise HTTPException(status_code=429, detail=decision.as_dict())
        return decision.as_dict()

    @router.post("/api/v1/cortex/budgets/{agent}/reset")
    async def reset_budget(agent: str) -> dict[str, Any]:
        try:
            ledger.reset_agent(agent)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return ledger.usage_snapshot(agent)

except Exception:  # pragma: no cover - FastAPI unavailable in bare contexts
    router = None  # type: ignore[assignment]
    ledger = BudgetLedger()
