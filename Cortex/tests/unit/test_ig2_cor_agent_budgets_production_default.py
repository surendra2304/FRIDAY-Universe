"""TASK-IG2-COR-01 follow-up — pin the production ledger's store selection.

PR #770 wired the budget ledger into production, and its supervisor
review confirmed BY INSPECTION that ``_build_production_ledger()``
defaults to the durable ``DatabaseBudgetStore`` — with
``CORTEX_AGENT_BUDGET_STORE=memory`` as the operator escape hatch back
to the in-memory store. Nothing pinned that selection: flipping the
default would have failed no test and silently cost the fleet its
restart-surviving budget state. These tests pin it — the default test
fails if the default selection is flipped.

Only the *selection* is pinned here. ``DatabaseBudgetStore.load`` is
stubbed so building the production ledger never opens a database
connection; the store's own I/O, restart restore and loud degradation
are covered by ``test_ig2_cor_agent_budgets_wiring.py``.
"""

from __future__ import annotations

import pytest

from cortex_api.agent_budgets import (
    DatabaseBudgetStore,
    InMemoryBudgetStore,
    _build_production_ledger,
)

ENV_VAR = "CORTEX_AGENT_BUDGET_STORE"


@pytest.fixture(autouse=True)
def _no_database_io(monkeypatch):
    # Selection is what is pinned; the store's database I/O is covered
    # by the wiring tests. Stub load() so constructing the production
    # ledger stays hermetic.
    monkeypatch.setattr(DatabaseBudgetStore, "load", lambda self: {})


def test_default_selection_is_the_durable_database_store(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)

    ledger = _build_production_ledger()

    assert isinstance(ledger.store, DatabaseBudgetStore)
    assert ledger.store_status()["backend"] == "database"


@pytest.mark.parametrize("value", ["db", "database", "anything-else"])
def test_any_non_memory_value_keeps_the_durable_store(monkeypatch, value):
    monkeypatch.setenv(ENV_VAR, value)

    ledger = _build_production_ledger()

    assert isinstance(ledger.store, DatabaseBudgetStore)


@pytest.mark.parametrize("value", ["memory", "MEMORY", " Memory "])
def test_memory_escape_hatch_selects_the_in_memory_store(monkeypatch, value):
    monkeypatch.setenv(ENV_VAR, value)

    ledger = _build_production_ledger()

    assert isinstance(ledger.store, InMemoryBudgetStore)
    assert not isinstance(ledger.store, DatabaseBudgetStore)
    assert ledger.store_status()["backend"] == "memory"
