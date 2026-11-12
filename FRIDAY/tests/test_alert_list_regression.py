"""Regression: the "my alerts" listing branch (F6, batch 7).

Ruff's F821 found that the listing reply read ``_len`` from the left side of
an f-string replacement BEFORE the walrus on the right side assigned it, so
listing with at least one active rule raised NameError - silently swallowed
by the fast path's except, degrading the answer. This pins the real listing
through the /api/command surface with active rules in the store.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from friday.proactive.market_watch import AlertRule, alert_store


@pytest.fixture(autouse=True)
def clean_alert_store():
    """Isolate the shared alert store around each test."""
    before = list(alert_store.list())
    for rule in before:
        alert_store.remove(rule["rule_id"])
    yield
    for rule in list(alert_store.list()):
        alert_store.remove(rule["rule_id"])
    for rule in before:
        alert_store.add(AlertRule(**{k: rule[k] for k in ("symbol", "direction", "target")}))


def _client() -> TestClient:
    from friday.api.server import app

    return TestClient(app, raise_server_exceptions=False)


def test_my_alerts_lists_active_rules_without_error() -> None:
    """With rules active, the listing counts and names them (no NameError)."""
    alert_store.add(AlertRule("BTC", "above", 100000))
    alert_store.add(AlertRule("ETH", "below", 5000))

    client = _client()
    response = client.post("/api/command", json={"command": "my alerts"})
    assert response.status_code == 200
    data = response.json()
    reply = str(data.get("reply", ""))
    # The pre-fix bug returned a degraded non-alert answer (NameError swallowed).
    assert data["metadata"].get("alert_list") is True
    assert "You have 2 price alerts active" in reply
    assert "BTC" in reply and "ETH" in reply


def test_my_alerts_single_rule_uses_singular() -> None:
    """One active rule reads '1 price alert', not '1 alerts'."""
    alert_store.add(AlertRule("NIFTY", "below", 24500))

    client = _client()
    response = client.post("/api/command", json={"command": "my alerts"})
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"].get("alert_list") is True
    assert "You have 1 price alert active" in str(data.get("reply", ""))
