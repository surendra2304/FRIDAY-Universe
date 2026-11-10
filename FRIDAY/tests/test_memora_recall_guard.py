"""TASK-BRAIN-002 (owner directive 2026-11-11 IST): recall must not crash on
the Oracle backend.

Production runs MemoraClient with the ORACLE local fallback, where
``local_db_path`` is None. Both ``recall_memories`` and ``recall_experience``
guarded the local path with ``os.path.exists(self.local_db_path)`` —
``os.path.exists(None)`` raises ``TypeError``, which meant: whenever the
remote Memora search timed out (0.8 s), recall CRASHED instead of falling
back to Oracle. That crash has been silently swallowed by callers for weeks
— the owner's "it is not keeping memory" bug. These tests pin the guard.
"""

from __future__ import annotations

from unittest.mock import patch

from friday.memory.memora_client import MemoraClient


def _oracle_backend_client() -> MemoraClient:
    """A client shaped like production: remote on, ORACLE local fallback."""
    client = MemoraClient.__new__(MemoraClient)
    client.remote_enabled = True
    client.base_url = "http://127.0.0.1:8002"
    client.api_key = None
    client.timeout = 3.5
    client.local_db_path = None  # the production Oracle shape
    client._backend = "oracle"
    client._schema_ready = True
    return client


def test_recall_memories_does_not_crash_when_local_db_path_is_none() -> None:
    client = _oracle_backend_client()
    # Remote search unreachable AND local path None: the old code raised
    # TypeError here. It must instead fall back to the oracle query —
    # which we stub to return one row.
    with patch.object(client, "_recall_locally", return_value=[{"content_text": "likes masala chai"}]) as local:
        hits = client.recall_memories("friday", "chai preference", limit=5)
    assert hits == [{"content_text": "likes masala chai"}]
    local.assert_called_once()


def test_recall_experience_does_not_crash_when_local_db_path_is_none() -> None:
    client = _oracle_backend_client()
    with patch.object(client, "_recall_experience_locally", return_value=[{"content_text": "lesson"}]) as local:
        hits = client.recall_experience("friday", "deploy", limit=5)
    assert hits == [{"content_text": "lesson"}]
    local.assert_called_once()


def test_recall_surfaces_local_failure_as_empty_not_crash() -> None:
    client = _oracle_backend_client()
    with patch.object(client, "_recall_locally", side_effect=RuntimeError("oracle down")):
        assert client.recall_memories("friday", "anything", limit=5) == []
