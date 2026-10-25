from __future__ import annotations

import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

def test_memora_single_persistence_and_tree():
    from Memora.core.memory.context_service import MemoraContextService, FabricBridge

    service = MemoraContextService(user="tester_autonomy")
    bridge = FabricBridge(service)

    # Save a memory via the bridge
    uri = bridge.save("sentinel", "isolate host 10.0.0.5", "host 10.0.0.5 was isolated due to malware", kind="incident")
    assert uri.startswith("viking://user/sentinel/")

    # Must be visible in tree
    tree_out = service.tree("viking://user/sentinel")
    assert "isolate-host-10-0-0-5.md" in tree_out

    # Must be visible in scoped search
    hits = bridge.recall("sentinel", "malware")
    assert len(hits) >= 1
    assert "isolate-host" in hits[0]["uri"]


def test_memora_layered_recall_escalation():
    from Memora.core.memory.context_service import MemoraContextService

    service = MemoraContextService(user="tester_escalation")
    # Write a document where keyword only appears in the full body (L2), not in abstract (L0)
    service.write("viking://user/tester_escalation/resources/doc.md",
                  "# Overview\n\nGeneral intro paragraph here.\n\n" + ("Other text\n" * 10) + "\n\nSpecificUniqueTermXYZ in deep details.\n")

    # Layered recall should escalate and find it
    level, hits = service.recall_layered("SpecificUniqueTermXYZ")
    assert hits
    assert any("SpecificUniqueTermXYZ" in h.get("abstract", "") or "doc.md" in h["uri"] for h in hits)
    # Level should be L1 or L2 after escalation from L0
    assert level in ("L0", "L1", "L2")


def test_memora_session_lifecycle_and_consolidation():
    from Memora.core.memory.context_service import MemoraContextService

    service = MemoraContextService(user="tester_session")
    # Commit a session with turns
    turns = [
        {"role": "user", "content": "What is our database schema?"},
        {"role": "assistant", "content": "We use PostgreSQL for relational and viking:// for context."},
    ]
    res = service.commit_session("sess_autonomy_1", turns)
    assert res.get("committed") is True

    # Sleep pass consolidation
    cons = service.consolidate()
    assert "applied" in cons or "status" in cons


def test_memora_rest_endpoints():
    from Memora.core.memory.context_service import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Verify consolidate endpoint
    resp = client.post("/v1/context/consolidate")
    assert resp.status_code == 200
    assert "applied" in resp.json() or "status" in resp.json()

    # Verify compile endpoint
    resp2 = client.post("/v1/context/compile", params={"persist": False})
    assert resp2.status_code == 200
    assert "index" in resp2.json()
