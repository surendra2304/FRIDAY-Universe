"""Pin: the production budget ledger's default store selection.

PR #770 (TASK-IG2-COR-01 wiring) made ``DatabaseBudgetStore`` the
production backing for the Cortex agent-budget ledger, so a Cortex
restart no longer resets every agent's daily counters, pauses and
breach alerts. Its reviewer noted that this selection was verified by
inspection only — no test failed if the default quietly changed.

These tests pin ``_build_production_ledger()`` exactly:

- env unset, empty, or set to anything other than ``memory``
  -> the database store is the production default;
- ``CORTEX_AGENT_BUDGET_STORE=memory`` (case/whitespace-insensitive)
  -> the in-memory store, and only that value, is the escape hatch;
- both branches carry the production ``WebhookBreachAlertSink``.

The real ``DatabaseBudgetStore`` is stubbed out: its ``load()`` does
real database I/O (that behaviour is already covered, against a real
SQLite database, in ``test_ig2_cor_agent_budgets_wiring.py``). Here
only the *selection* is under test, so the stub stands in for the class
the production builder must instantiate — if the builder stops
instantiating it by default, or starts instantiating it on the
``memory`` path, these tests fail.
"""

from __future__ import annotations

import pytest

from cortex_api import agent_budgets
from cortex_api.agent_budgets import (
    InMemoryBudgetStore,
    WebhookBreachAlertSink,
    _build_production_ledger,
)

_ENV = "CORTEX_AGENT_BUDGET_STORE"


class _StubDatabaseBudgetStore(InMemoryBudgetStore):
    """Selection stand-in for ``DatabaseBudgetStore`` (no DB I/O).

    Inherits the in-memory behaviour so ``BudgetLedger`` construction
    (which calls ``store.load()``) works unchanged, but reports the
    database backend in ``status()`` like the real store.
    """

    instances: list["_StubDatabaseBudgetStore"] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        type(self).instances.append(self)

    def status(self):  # noqa: D102 - mirrors DatabaseBudgetStore.status
        return {"backend": "database", "durable": False}


@pytest.fixture
def stub_db_store(monkeypatch):
    _StubDatabaseBudgetStore.instances = []
    monkeypatch.setattr(
        agent_budgets, "DatabaseBudgetStore", _StubDatabaseBudgetStore
    )
    return _StubDatabaseBudgetStore


def test_unset_env_selects_the_database_store_by_default(
    monkeypatch, stub_db_store
):
    monkeypatch.delenv(_ENV, raising=False)

    ledger = _build_production_ledger()

    assert len(stub_db_store.instances) == 1
    assert ledger.store is stub_db_store.instances[0]
    assert type(ledger.store) is _StubDatabaseBudgetStore
    assert ledger.store_status()["backend"] == "database"
    assert isinstance(ledger.alert_sink, WebhookBreachAlertSink)


@pytest.mark.parametrize("value", ["db", "database", "", "postgres", "memoryy"])
def test_any_non_memory_value_selects_the_database_store(
    monkeypatch, stub_db_store, value
):
    monkeypatch.setenv(_ENV, value)

    ledger = _build_production_ledger()

    assert len(stub_db_store.instances) == 1
    assert ledger.store is stub_db_store.instances[0]
    assert ledger.store_status()["backend"] == "database"


@pytest.mark.parametrize("value", ["memory", "Memory", "MEMORY", "  memory  "])
def test_memory_is_the_escape_hatch_to_the_in_memory_store(
    monkeypatch, stub_db_store, value
):
    monkeypatch.setenv(_ENV, value)

    ledger = _build_production_ledger()

    # The escape hatch must not construct the database store at all,
    # and the ledger falls back to BudgetLedger's in-memory default.
    assert stub_db_store.instances == []
    assert type(ledger.store) is InMemoryBudgetStore
    assert ledger.store_status() == {"backend": "memory", "durable": False}
    assert isinstance(ledger.alert_sink, WebhookBreachAlertSink)
