from __future__ import annotations

import pytest

from apps.api.routers.memory_access_controller import engine


@pytest.fixture(autouse=True)
def reset_process_local_access_engine():
    engine._grants.clear()
    engine._requests.clear()
    engine._audit.clear()
    yield
    engine._grants.clear()
    engine._requests.clear()
    engine._audit.clear()


def _headers(monkeypatch, agent_name: str) -> dict[str, str]:
    key = f"test-{agent_name}-api-key"
    monkeypatch.setenv("MEMORA_ALLOW_ANONYMOUS_DEV", "0")
    monkeypatch.setenv(f"{agent_name.upper()}_API_KEY", key)
    return {"X-Agent-Name": agent_name, "X-API-Key": key}


def test_all_access_controller_routes_reject_missing_credentials(client, monkeypatch):
    monkeypatch.setenv("MEMORA_ALLOW_ANONYMOUS_DEV", "0")
    responses = [
        client.post("/api/v1/memora/access/grants", params={"subject": "forge", "scope": "memora://forge/private"}),
        client.delete("/api/v1/memora/access/grants/missing"),
        client.get("/api/v1/memora/access/check", params={"subject": "forge", "scope": "memora://forge/private"}),
        client.post("/api/v1/memora/access/requests", params={"subject": "forge", "scope": "memora://forge/private", "permission": "read"}),
        client.post("/api/v1/memora/access/requests/missing/approve"),
        client.get("/api/v1/memora/access/audit"),
        client.get("/api/v1/memora/access/report"),
    ]
    assert [response.status_code for response in responses] == [401] * len(responses)


def test_non_admin_cannot_grant_revoke_approve_or_inspect_global_audit(client, monkeypatch):
    headers = _headers(monkeypatch, "forge")
    existing_grant = engine.grant_access("forge", "memora://forge/private")
    existing_request = engine.request_access("forge", "memora://forge/private", "read")

    grant_response = client.post(
        "/api/v1/memora/access/grants",
        params={"subject": "intelx", "scope": "memora://intelx/private"},
        headers=headers,
    )
    revoke_response = client.delete(f"/api/v1/memora/access/grants/{existing_grant}", headers=headers)
    approve_response = client.post(f"/api/v1/memora/access/requests/{existing_request}/approve", headers=headers)
    audit_response = client.get("/api/v1/memora/access/audit", headers=headers)
    report_response = client.get("/api/v1/memora/access/report", headers=headers)

    assert grant_response.status_code == 403
    assert revoke_response.status_code == 403
    assert existing_grant in engine._grants
    assert approve_response.status_code == 403
    assert engine._requests[existing_request].status == "pending"
    assert audit_response.status_code == 403
    assert report_response.status_code == 403


def test_agent_cannot_request_or_check_access_as_another_subject(client, monkeypatch):
    headers = _headers(monkeypatch, "forge")
    spoofed_request = client.post(
        "/api/v1/memora/access/requests",
        params={"subject": "intelx", "scope": "memora://intelx/private", "permission": "read"},
        headers=headers,
    )
    own_request = client.post(
        "/api/v1/memora/access/requests",
        params={"subject": "forge", "scope": "memora://forge/private", "permission": "read"},
        headers=headers,
    )
    spoofed_check = client.get(
        "/api/v1/memora/access/check",
        params={"subject": "intelx", "scope": "memora://intelx/private"},
        headers=headers,
    )
    own_check = client.get(
        "/api/v1/memora/access/check",
        params={"subject": "forge", "scope": "memora://forge/private"},
        headers=headers,
    )

    assert spoofed_request.status_code == 403
    assert own_request.status_code == 200
    assert engine._requests[own_request.json()["request_id"]].subject == "forge"
    assert spoofed_check.status_code == 403
    assert own_check.status_code == 200
    assert own_check.json()["subject"] == "forge"


def test_memora_admin_can_manage_grants_and_approve_requests_as_itself(client, monkeypatch):
    headers = _headers(monkeypatch, "memora")
    request_id = engine.request_access("forge", "memora://forge/private", "read")

    spoofed_grant = client.post(
        "/api/v1/memora/access/grants",
        params={"subject": "forge", "scope": "memora://forge/private", "granted_by": "intelx"},
        headers=headers,
    )
    grant_response = client.post(
        "/api/v1/memora/access/grants",
        params={"subject": "forge", "scope": "memora://forge/private", "granted_by": "system"},
        headers=headers,
    )
    spoofed_approval = client.post(
        f"/api/v1/memora/access/requests/{request_id}/approve",
        params={"decided_by": "intelx"},
        headers=headers,
    )
    approval = client.post(
        f"/api/v1/memora/access/requests/{request_id}/approve",
        params={"decided_by": "system"},
        headers=headers,
    )

    assert spoofed_grant.status_code == 403
    assert grant_response.status_code == 200
    grant = engine._grants[grant_response.json()["grant_id"]]
    assert grant.granted_by == "memora"
    assert spoofed_approval.status_code == 403
    assert approval.status_code == 200
    assert approval.json()["decided_by"] == "memora"
    assert engine._requests[request_id].decided_by == "memora"
    assert client.get("/api/v1/memora/access/audit", headers=headers).status_code == 200
    report = client.get("/api/v1/memora/access/report", headers=headers)
    assert report.status_code == 200
    assert report.json()["authority"] == "process_local_compatibility_only"

    revoked = client.delete(f"/api/v1/memora/access/grants/{grant.grant_id}", headers=headers)
    assert revoked.status_code == 200
    assert grant.grant_id not in engine._grants
