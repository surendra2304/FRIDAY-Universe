from __future__ import annotations

from core.identity.service import IdentityService
from apps.api.routers import v1_task


def test_task_store_receipt_reports_active_non_durable_sqlite_backend(
    client, test_db, monkeypatch
):
    """A local test write must never be reported as a durable Oracle write."""
    monkeypatch.delenv("MEMORA_ALLOW_ANONYMOUS_DEV", raising=False)
    monkeypatch.setenv("FORGE_API_KEY", "task-receipt-test-key")
    monkeypatch.setattr(
        v1_task,
        "storage_receipt",
        lambda: {
            "backend": "sqlite",
            "durable": False,
            "durability": "process_local",
        },
    )
    IdentityService.register_agent(test_db, "forge")

    response = client.post(
        "/v1/task/execute",
        headers={
            "X-Agent-Name": "forge",
            "X-API-Key": "task-receipt-test-key",
        },
        json={
            "action": "store",
            "payload": {
                "content": "synthetic task receipt storage-backend probe",
                "target_namespace_path": "memora://forge/private",
            },
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "SUCCESS", body
    evidence = body["receipt"]["verification_evidence"]
    assert evidence["backend"] == "sqlite"
    assert evidence["durable"] is False
    assert evidence["durability"] == "process_local"
    assert evidence["durable_write"] is False
