from __future__ import annotations

import pytest

from core.identity.service import IdentityService
from storage.relational.models import (
    AccessGrant,
    MemoryRecord,
    MemoryScopeType,
    MemorySharedAgent,
    NamespaceType,
)


@pytest.fixture
def sharing_mesh(client, test_db, monkeypatch):
    """Authenticated default-tenant agents for memory-share API regressions."""
    monkeypatch.delenv("MEMORA_ALLOW_ANONYMOUS_DEV", raising=False)
    monkeypatch.setenv("FRIDAY_API_KEY", "share-test-friday-key")
    monkeypatch.setenv("FORGE_API_KEY", "share-test-forge-key")
    monkeypatch.setenv("INTELX_API_KEY", "share-test-intelx-key")

    agents = {
        name: IdentityService.register_agent(test_db, name)
        for name in ("friday", "forge", "intelx")
    }
    return {
        "agents": agents,
        "headers": {
            name: {"X-Agent-Name": name, "X-API-Key": f"share-test-{name}-key"}
            for name in agents
        },
    }


def _record_count(test_db, marker: str) -> int:
    return test_db.query(MemoryRecord).filter(
        MemoryRecord.content_text == marker
    ).count()


def test_write_only_namespace_member_cannot_share_a_record_with_readers(
    client, test_db, sharing_mesh
):
    agents = sharing_mesh["agents"]
    namespace_path = "memora://friday/projects/write-only-share-boundary"
    namespace = IdentityService.resolve_namespace(
        test_db,
        namespace_path,
        owner_agent_id=agents["friday"].id,
        default_type=NamespaceType.PROJECT_PRIVATE,
        tenant_id="default",
    )
    IdentityService.grant_access(
        test_db,
        agent_id=agents["forge"].id,
        namespace_id=namespace.id,
        actions=["write"],
        tenant_id="default",
    )
    IdentityService.grant_access(
        test_db,
        agent_id=agents["intelx"].id,
        namespace_id=namespace.id,
        actions=["read", "query"],
        tenant_id="default",
    )

    marker = "synthetic write-only share escalation marker"
    response = client.post(
        "/v1/memories",
        headers=sharing_mesh["headers"]["forge"],
        json={
            "content_text": marker,
            "target_namespace_path": namespace_path,
            "shared_with": ["intelx"],
        },
    )

    assert response.status_code == 403, response.text
    assert _record_count(test_db, marker) == 0
    assert test_db.query(MemorySharedAgent).filter(
        MemorySharedAgent.tenant_id == "default",
        MemorySharedAgent.agent_name == "intelx",
    ).count() == 0


def test_explicit_wildcard_recipient_is_rejected_for_private_memory(
    client, test_db, sharing_mesh
):
    marker = "synthetic wildcard recipient must not widen visibility"
    response = client.post(
        "/v1/memories",
        headers=sharing_mesh["headers"]["friday"],
        json={
            "content_text": marker,
            "target_namespace_path": "memora://friday/private",
            "shared_with": ["*"],
        },
    )

    assert response.status_code == 403, response.text
    assert _record_count(test_db, marker) == 0


def test_share_recipient_must_be_registered_in_the_same_tenant(
    client, test_db, sharing_mesh
):
    IdentityService.register_agent(
        test_db, "shadow", tenant_id="tenant-outsider"
    )
    marker = "synthetic foreign-tenant share recipient marker"

    response = client.post(
        "/v1/memories",
        headers=sharing_mesh["headers"]["friday"],
        json={
            "content_text": marker,
            "target_namespace_path": "memora://friday/private",
            "shared_with": ["shadow"],
        },
    )

    assert response.status_code == 403, response.text
    assert _record_count(test_db, marker) == 0
    assert test_db.query(AccessGrant).filter(
        AccessGrant.tenant_id == "tenant-outsider"
    ).count() == 0


def test_owner_can_share_memory_with_registered_same_tenant_recipient(
    client, test_db, sharing_mesh
):
    marker = "synthetic explicitly shared memory for intelx"
    response = client.post(
        "/v1/memories",
        headers=sharing_mesh["headers"]["friday"],
        json={
            "content_text": marker,
            "target_namespace_path": "memora://friday/private",
            "shared_with": ["intelx"],
        },
    )

    assert response.status_code == 201, response.text
    memory_id = response.json()["id"]
    record = test_db.query(MemoryRecord).filter(
        MemoryRecord.id == memory_id,
        MemoryRecord.tenant_id == "default",
    ).one()
    assert record.scope == MemoryScopeType.SHARED

    recipient = sharing_mesh["agents"]["intelx"]
    grant = test_db.query(AccessGrant).filter(
        AccessGrant.tenant_id == "default",
        AccessGrant.agent_id == recipient.id,
        AccessGrant.namespace_id == record.namespace_id,
    ).one()
    assert set(grant.actions) == {"read", "query"}

    membership = test_db.query(MemorySharedAgent).filter(
        MemorySharedAgent.tenant_id == "default",
        MemorySharedAgent.memory_id == memory_id,
        MemorySharedAgent.agent_name == "intelx",
    ).one()
    assert membership.granted_by == "friday"

    recipient_read = client.get(
        f"/v1/memories/{memory_id}",
        headers=sharing_mesh["headers"]["intelx"],
    )
    stranger_read = client.get(
        f"/v1/memories/{memory_id}",
        headers=sharing_mesh["headers"]["forge"],
    )
    assert recipient_read.status_code == 200, recipient_read.text
    assert marker in recipient_read.text
    assert stranger_read.status_code == 404
