from __future__ import annotations

from typing import Any

import pytest

from core.identity.service import IdentityService
from storage.convergence.horizon_sweeper import horizon_sweeper


@pytest.fixture
def memora_and_foreign_tenant(test_db):
    """Provision the API-bound Memora service principal and a separate tenant."""
    service = IdentityService.register_agent(
        test_db,
        "memora",
        role="supervisor",
        tenant_id="default",
    )
    foreign_agent = IdentityService.register_agent(
        test_db,
        "forge",
        role="worker",
        tenant_id="foreign-customer",
    )
    assert service.tenant_id == "default"
    assert foreign_agent.tenant_id == "foreign-customer"
    return service, foreign_agent


def test_api_horizon_sweep_rejects_foreign_tenant_before_worker_runs(
    client,
    memora_and_foreign_tenant,
    monkeypatch,
):
    """A Memora credential must not turn the API into a cross-tenant sweeper."""
    calls: list[dict[str, Any]] = []

    def record_sweep(db, tenant_id=None, now=None):
        calls.append({"tenant_id": tenant_id})
        return {
            "status": "completed",
            "tenants_scanned": 1,
            "total_condensed": 0,
            "details": [],
        }

    monkeypatch.setattr(horizon_sweeper, "run_sweep_pass", record_sweep)

    response = client.post(
        "/v1/memories/sweep-horizon",
        json={"tenant_id": "foreign-customer"},
        headers={"X-Agent-Name": "memora"},
    )

    assert response.status_code == 403, response.text
    assert calls == [], "The sweeper must not run for a rejected foreign-tenant request."


@pytest.mark.parametrize("body", [{"tenant_id": "default"}, {}])
def test_api_horizon_sweep_is_pinned_to_authenticated_service_tenant(
    client,
    memora_and_foreign_tenant,
    monkeypatch,
    body,
):
    """Omitted or explicit matching tenant both run only for the bound tenant."""
    calls: list[str | None] = []

    def record_sweep(db, tenant_id=None, now=None):
        calls.append(tenant_id)
        return {
            "status": "completed",
            "tenants_scanned": 1,
            "total_condensed": 0,
            "details": [],
        }

    monkeypatch.setattr(horizon_sweeper, "run_sweep_pass", record_sweep)

    response = client.post(
        "/v1/memories/sweep-horizon",
        json=body,
        headers={"X-Agent-Name": "memora"},
    )

    assert response.status_code == 200, response.text
    assert calls == ["default"]
    assert response.json()["sweep_result"]["tenants_scanned"] == 1
