"""
Unit tests for Project FORGE Memora Cognitive Memory Integration.
Tests universal client connection, memory recording, memory recall,
context prompt generation, and SQLite local fallback.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.memora_client import MemoraClient, get_memora_client


def test_forge_named_key_is_used_for_memora_identity():
    from app.core.config import Settings

    settings = Settings(_env_file=None, FORGE_API_KEY="forge-agent-key")
    assert settings.memora_api_key == "forge-agent-key"


@pytest.mark.asyncio
async def test_memora_client_local_fallback(tmp_path: Path):
    """Verify MemoraClient seamlessly falls back to local SQLite when cloud is unreachable."""
    db_file = tmp_path / "test_memora.db"
    client = MemoraClient(
        base_url="http://invalid-host-unreachable.example.com",
        api_key="test_api_key",
        local_db_path=str(db_file),
    )

    # 1. Record interaction
    event_id = await client.a_record_interaction(
        user_input="Build a 3D cyberpunk developer portfolio",
        agent_output="Synthesized index.html, style.css, and app.js with Three.js WebGL.",
        agent_name="forge",
        event_type="software_build",
        tags=["portfolio", "3d"],
        metadata={"framework": "Three.js"},
    )
    assert event_id is not None
    eid = event_id if isinstance(event_id, str) else event_id.get("id")
    assert eid is not None
    assert db_file.exists()

    # 2. Record fact
    fact_id = await client.a_record_fact(
        fact_text="User prefers dark cyberpunk aesthetics with cyan and magenta accents.",
        agent_name="forge",
        category="preference",
        importance=0.98,
    )
    assert fact_id is not None
    fid = fact_id if isinstance(fact_id, str) else fact_id.get("id")
    assert fid is not None

    # 3. Recall memories
    recalled = await client.a_recall_memories(
        query="cyberpunk portfolio preferences",
        agent_name="forge",
        limit=5,
    )
    assert len(recalled) >= 1
    assert any("cyberpunk" in m.content.lower() for m in recalled)

    # 4. Build context prompt
    prompt_ctx = await client.a_build_context_prompt(
        query="cyberpunk portfolio",
        agent_name="forge",
    )
    assert "Memora Cognitive Memory Context" in prompt_ctx
    assert "cyberpunk" in prompt_ctx.lower()


@pytest.mark.asyncio
async def test_memora_client_cloud_mock():
    """Verify MemoraClient cloud HTTP integration when cloud API responds successfully."""
    client = MemoraClient(
        base_url="https://memora-cloud.example.com",
        api_key="memora_test_key",
    )

    mock_resp = {
        "status": "success",
        "memories": [
            {
                "memory_id": "mem-101",
                "content": "Architecture pattern: E-Commerce requires cart drawer and product grid.",
                "source": "fact",
                "similarity": 0.94,
                "metadata": {"domain": "ecommerce"},
            },
            {
                "memory_id": "mem-102",
                "content": "User prefers Three.js 3D canvas for interactive showcases.",
                "source": "preference",
                "similarity": 0.89,
                "metadata": {"type": "3d"},
            },
        ],
    }

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = mock_resp

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_http_resp

        recalled = await client.a_recall_memories(query="e-commerce store architecture")
        assert len(recalled) == 2
        assert recalled[0].memory_id == "mem-101"
        assert "E-Commerce requires cart drawer" in recalled[0].content
        assert recalled[0].similarity == 0.94

        prompt_str = await client.a_build_context_prompt(query="e-commerce store architecture")
        assert "Memora Cognitive Memory Context" in prompt_str
        assert "cart drawer" in prompt_str


def test_get_memora_client_singleton():
    """Verify get_memora_client returns a valid singleton client instance."""
    c1 = get_memora_client()
    c2 = get_memora_client()
    assert c1 is c2
    assert isinstance(c1, MemoraClient)


# ---------------------------------------------------------------------------
# Recall must survive hostile queries
# ---------------------------------------------------------------------------


def _make_local_db(tmp_path) -> str:
    import sqlite3

    db = tmp_path / "memora.db"
    con = sqlite3.connect(str(db))
    con.executescript(
        """
        CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT, namespace TEXT);
        CREATE TABLE memory_records (
            id TEXT PRIMARY KEY, owner_id TEXT, node_id TEXT, memory_type TEXT,
            content_text TEXT, source TEXT, importance REAL,
            lifecycle_state TEXT, namespace TEXT, created_at TEXT
        );
        INSERT INTO agents VALUES ('a1','forge','default');
        INSERT INTO memory_records VALUES (
            'm1','a1',NULL,'lesson',
            'CLI apps must handle KeyboardInterrupt and expose --help',
            'agent:forge',0.9,'active','default','2026-01-01'
        );
        """
    )
    con.commit()
    con.close()
    return str(db)


def test_recall_survives_a_degenerate_query(tmp_path):
    """A 2 000-word goal must not break recall.

    The recall query built one LIKE clause per keyword, so a hostile goal
    produced thousands of clauses and SQLite rejected the whole statement with
    "Expression tree is too large (maximum depth 1000)". Recall then returned
    nothing for those tasks -- silently.
    """
    from app.integrations.memora_client import MemoraClient

    client = MemoraClient()
    client.local_db_path = _make_local_db(tmp_path)

    for hostile in ("app " * 2000, "x" * 5000, " ".join(f"w{i}" for i in range(3000))):
        results = client._recall_locally("forge", hostile, 10)
        assert isinstance(results, list)


def test_recall_still_finds_the_real_memory(tmp_path):
    """The cap must not cost recall for ordinary queries."""
    from app.integrations.memora_client import MemoraClient

    client = MemoraClient()
    client.local_db_path = _make_local_db(tmp_path)
    results = client._recall_locally("forge", "CLI apps KeyboardInterrupt", 10)
    assert len(results) == 1
    assert "KeyboardInterrupt" in results[0].content_text
