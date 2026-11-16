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
production ledger (the module-level ``ledger`` the mounted API and the
FRIDAY task path share) is backed by ``DatabaseBudgetStore``, which
persists the state dict in Cortex's own database (the
``agent_budget_state`` table — repo rule: no local SQLite files for
Cortex data), so a Cortex restart no longer resets the budgets.
``BudgetLedger()`` with no store still defaults to the in-memory store
for library use and tests; ``CORTEX_AGENT_BUDGET_STORE=memory`` forces
the production instance back to in-memory as an operator escape hatch.

Dispatch path: ``cortex_api.friday_router.process_task_envelope`` — the
executor behind the FRIDAY Universal Task Protocol endpoint — charges
every executed envelope to the Cortex budget line through this ledger
(see that module for the gate). Direct LLM-backed callers report token
usage through ``POST /api/v1/cortex/budgets/usage``.

Breach alerts: recording an alert in-ledger is not dispatch. The
production ledger carries a ``WebhookBreachAlertSink`` that delivers
each breach over Cortex's existing operator escalation channel — the
``SELF_HEALING_ESCALATION_WEBHOOK`` webhook that
``cortex_core.resilience.EscalationNotifier`` delivers self-healing
escalations to — and every delivery outcome (including "no channel
configured") is recorded on the ledger and exposed via
``GET /api/v1/cortex/budgets`` instead of vanishing silently.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

logger = logging.getLogger("cortex-agent-budgets")

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
    """Single-process store (the ``BudgetLedger()`` default). State is
    lost on restart — see ``DatabaseBudgetStore`` for the durable
    production backing."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        return self._state

    def save(self, state: dict[str, Any]) -> None:
        self._state = state

    def status(self) -> dict[str, Any]:
        return {"backend": "memory", "durable": False}


class DatabaseBudgetStore:
    """Durable ``BudgetStore`` backed by Cortex's own database.

    Persists the ledger state dict as the single row of
    ``agent_budget_state`` (``cortex_api.db_models.AgentBudgetStateModel``)
    through the app's async session factory, so the state lives in the
    same database as every other Cortex table (Oracle in production).

    The ``BudgetStore`` protocol is synchronous while the engine is
    async, so all I/O runs on a dedicated daemon thread with its own
    event loop; callers block on the result with a bounded timeout.

    Degradation is honest, never silent: any failure (database
    unreachable, table not yet migrated, timeout) is logged, counted in
    ``status()``, and the store falls back to its in-process mirror so
    enforcement keeps working — with ``durable`` in the status saying
    plainly whether the last save actually reached the database.
    """

    ROW_ID = "agent_budgets"

    def __init__(
        self,
        session_factory: Any = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        # session_factory: an async_sessionmaker; None resolves lazily to
        # cortex_api.config.AsyncSessionLocal (imported on first use so
        # importing this module never touches the database).
        self._session_factory = session_factory
        self._timeout = timeout_seconds
        self._mirror: dict[str, Any] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()
        self.durable = False
        self.load_errors = 0
        self.save_errors = 0
        self.last_error: str | None = None

    # -- async plumbing ----------------------------------------------------
    def _factory(self) -> Any:
        if self._session_factory is not None:
            return self._session_factory
        from cortex_api.config import AsyncSessionLocal

        return AsyncSessionLocal

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            with self._loop_lock:
                if self._loop is None:
                    loop = asyncio.new_event_loop()
                    thread = threading.Thread(
                        target=loop.run_forever,
                        name="cortex-budget-store",
                        daemon=True,
                    )
                    thread.start()
                    self._loop = loop
        return self._loop

    def _run(self, coro: Any) -> Any:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=self._timeout)

    async def _load_async(self) -> dict[str, Any]:
        from cortex_api.db_models import AgentBudgetStateModel

        async with self._factory()() as session:
            row = await session.get(AgentBudgetStateModel, self.ROW_ID)
            if row is None or not isinstance(row.state, dict):
                return {}
            return dict(row.state)

    async def _save_async(self, state: dict[str, Any]) -> None:
        from cortex_api.db_models import AgentBudgetStateModel

        async with self._factory()() as session:
            row = await session.get(AgentBudgetStateModel, self.ROW_ID)
            if row is None:
                session.add(AgentBudgetStateModel(id=self.ROW_ID, state=state))
            else:
                row.state = state
            await session.commit()

    # -- BudgetStore protocol ------------------------------------------------
    def load(self) -> dict[str, Any]:
        try:
            state = self._run(self._load_async())
        except Exception as exc:  # noqa: BLE001 - degradation is the design
            self.load_errors += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "agent budget store: database load failed (%s); "
                "falling back to the in-process mirror",
                self.last_error,
            )
            return dict(self._mirror)
        self._mirror = state
        self.durable = True
        self.last_error = None
        return dict(state)

    def save(self, state: dict[str, Any]) -> None:
        self._mirror = dict(state)
        try:
            self._run(self._save_async(dict(state)))
        except Exception as exc:  # noqa: BLE001 - never break enforcement
            self.save_errors += 1
            self.durable = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "agent budget store: database save failed (%s); "
                "state kept in the in-process mirror only",
                self.last_error,
            )
            return
        self.durable = True
        self.last_error = None

    def status(self) -> dict[str, Any]:
        return {
            "backend": "database",
            "durable": self.durable,
            "load_errors": self.load_errors,
            "save_errors": self.save_errors,
            "last_error": self.last_error,
        }


# A breach-alert sink receives the alert dict and returns a delivery
# record dict (delivered / detail / channel). It must never raise into
# the ledger; the ledger also guards the call.
AlertSink = Callable[[dict[str, Any]], "dict[str, Any] | None"]


class WebhookBreachAlertSink:
    """Dispatches budget-breach alerts over Cortex's operator channel.

    The channel is the ``SELF_HEALING_ESCALATION_WEBHOOK`` webhook — the
    same one ``cortex_core.resilience.EscalationNotifier`` delivers
    self-healing escalations to — so budget breaches reach the operator
    wherever Cortex escalations already go. Mirrors the notifier's
    honesty rule: with no channel configured the delivery record says
    ``delivered: False`` with the reason instead of pretending. When the
    configured URL is a Telegram ``sendMessage`` URL the payload is
    translated to ``{chat_id, text}`` first (see
    ``cortex_core.resilience.telegram_delivery_payload``).
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if webhook_url is None:
            webhook_url = os.environ.get("SELF_HEALING_ESCALATION_WEBHOOK", "")
        self.webhook_url = webhook_url.strip() or None
        self.timeout_seconds = timeout_seconds

    @property
    def channel(self) -> str:
        return self.webhook_url or "none"

    def __call__(self, alert: dict[str, Any]) -> dict[str, Any]:
        record: dict[str, Any] = {
            "agent": alert.get("agent"),
            "date": alert.get("date"),
            "reason": alert.get("reason"),
            "channel": self.channel,
        }
        if self.webhook_url is None:
            record.update({
                "delivered": False,
                "detail": (
                    "no escalation channel configured "
                    "(SELF_HEALING_ESCALATION_WEBHOOK is unset)"
                ),
            })
            return record
        payload = {
            "subsystem": "agent_budgets",
            "reason": alert.get("reason"),
            "agent": alert.get("agent"),
            "message": alert.get("message"),
            "alert": alert,
        }
        from cortex_core.resilience import (
            is_telegram_send_message_url,
            telegram_delivery_payload,
        )

        if is_telegram_send_message_url(self.webhook_url):
            # Telegram's sendMessage needs {chat_id, text}; the generic
            # payload above is rejected with HTTP 400 (TASK-COR-010).
            payload, error = telegram_delivery_payload(payload)
            if payload is None:
                record.update({"delivered": False, "detail": error})
                return record
        try:
            import httpx

            # trust_env=False: the escalation webhook is a configured
            # operator endpoint — ambient HTTP(S)_PROXY variables (CI
            # sandboxes, egress gateways) must not intercept or break
            # alert delivery.
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            delivered = 200 <= response.status_code < 300
            record.update({
                "delivered": delivered,
                "status_code": response.status_code,
                "detail": (
                    "delivered" if delivered
                    else f"channel returned {response.status_code}"
                ),
            })
        except Exception as exc:  # noqa: BLE001 - delivery failure is data
            record.update({
                "delivered": False,
                "detail": f"{type(exc).__name__}: {exc}",
            })
        return record


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
        alert_sink: AlertSink | None = None,
    ) -> None:
        self.budgets = budgets if budgets is not None else default_budgets()
        self.store = store if store is not None else InMemoryBudgetStore()
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.alert_sink = alert_sink
        stored = self.store.load() or {}
        self._usage: dict[str, _DayUsage] = {
            agent: _DayUsage.from_dict(data)
            for agent, data in stored.get("usage", {}).items()
            if agent in self.budgets
        }
        # Alert history and delivery outcomes are ledger state too: they
        # persist with the usage counters so a restart neither loses the
        # record of a breach nor re-dispatches it.
        self._alerts: list[dict[str, Any]] = list(stored.get("alerts", []))
        self._alert_deliveries: list[dict[str, Any]] = list(
            stored.get("alert_deliveries", [])
        )

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
            "alerts": self._alerts[-50:],
            "alert_deliveries": self._alert_deliveries[-50:],
        })

    def _dispatch_alert(self, alert: dict[str, Any]) -> None:
        """Hand a breach alert to the alert sink and record the outcome.

        Dispatch must never break enforcement (the same rule Sentinel's
        alerting follows): a missing or failing sink produces a delivery
        record with ``delivered: False`` and the reason, not an exception.
        """
        record: dict[str, Any] = {
            "agent": alert["agent"],
            "date": alert["date"],
            "reason": alert["reason"],
            "at": self._now_fn().isoformat(),
            "channel": "none",
            "delivered": False,
            "detail": "no alert sink configured",
        }
        if self.alert_sink is not None:
            try:
                result = self.alert_sink(dict(alert))
                if isinstance(result, dict):
                    record.update(result)
                    record.setdefault("at", self._now_fn().isoformat())
            except Exception as exc:  # noqa: BLE001 - dispatch is best-effort
                record.update({
                    "delivered": False,
                    "detail": f"alert sink raised {type(exc).__name__}: {exc}",
                })
                logger.error(
                    "agent budget breach alert dispatch failed for %s: %s",
                    alert["agent"], record["detail"],
                )
        self._alert_deliveries.append(record)
        self._alert_deliveries = self._alert_deliveries[-50:]

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
            alert = {
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
            }
            self._alerts.append(alert)
            self._dispatch_alert(alert)
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

    def alert_deliveries(self) -> list[dict[str, Any]]:
        """One record per breach-alert dispatch attempt (oldest first)."""
        return list(self._alert_deliveries)

    def store_status(self) -> dict[str, Any]:
        status = getattr(self.store, "status", None)
        if callable(status):
            return status()
        return {"backend": type(self.store).__name__, "durable": False}

    def reset_agent(self, agent: str) -> None:
        """Operator override: clear today's usage and unpause an agent."""
        self._budget_for(agent)
        self._usage[agent] = _DayUsage(date=self._today())
        self._persist()


def _build_production_ledger() -> BudgetLedger:
    """The shared production ledger: durable store + dispatching sink.

    ``CORTEX_AGENT_BUDGET_STORE=memory`` is the operator escape hatch
    back to the in-memory store; anything else uses the database store
    (which itself degrades to its mirror, loudly, if the database is
    unreachable — enforcement never depends on the store being up).
    """
    sink = WebhookBreachAlertSink()
    if os.environ.get("CORTEX_AGENT_BUDGET_STORE", "db").strip().lower() == "memory":
        return BudgetLedger(alert_sink=sink)
    return BudgetLedger(store=DatabaseBudgetStore(), alert_sink=sink)


# ── HTTP surface ─────────────────────────────────────────────────────────
try:  # pragma: no cover - exercised via the mounted app in integration tests
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    router = APIRouter(tags=["Agent Budgets"])
    ledger = _build_production_ledger()

    class UsageRequest(BaseModel):
        agent: str
        tokens: int = 0
        tasks: int = 1
        critical: bool = False

    @router.get("/api/v1/cortex/budgets")
    async def list_budgets() -> dict[str, Any]:
        return {
            "budgets": ledger.all_usage(),
            "alerts": ledger.alerts(),
            "alert_deliveries": ledger.alert_deliveries(),
            "store": ledger.store_status(),
        }

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
