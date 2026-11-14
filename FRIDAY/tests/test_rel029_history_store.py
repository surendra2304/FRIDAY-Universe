"""TASK-REL-029 unit tests for ConversationHistoryStore.

The store is exercised against the sanctioned test-only SQLite backend
(production runs the identical class against Oracle via
``friday.core.oracle``). Covered: round-trip fidelity, newest-first
ordering, finalize-as-update, upsert fallback, durable clear, the
10000-entry growth bound, and the failure contract (``False``/``None``,
never an exception into the chat path).
"""

from __future__ import annotations

import os

import pytest

from friday.api import history_store
from friday.api.history_store import ConversationHistoryStore


def _entry(entry_id: str, user: str, reply: str = "", **over) -> dict:
    base = {
        "id": entry_id,
        "timestamp": "2026-11-15T00:00:00+00:00",
        "user_input": user,
        "friday_reply": reply,
        "input_type": "text",
        "status": "success",
        "agents_involved": [],
        "metadata": {},
    }
    base.update(over)
    return base


@pytest.fixture()
def store(tmp_path) -> ConversationHistoryStore:
    return ConversationHistoryStore(db_path=str(tmp_path / "hist.db"))


def test_insert_and_load_roundtrip(store):
    assert store.backend == "sqlite"
    assert store.insert_entry(
        _entry("e1", "hello", "hi there", agents_involved=["friday"], metadata={"k": 1})
    )
    assert store.insert_entry(_entry("e2", "again", "yo"))

    rows = store.load_recent()
    assert rows is not None
    assert [r["id"] for r in rows] == ["e2", "e1"]  # newest first
    first = rows[1]
    assert first["user_input"] == "hello"
    assert first["friday_reply"] == "hi there"
    assert first["agents_involved"] == ["friday"]
    assert first["metadata"] == {"k": 1}
    assert first["status"] == "success"


def test_empty_reply_roundtrips_as_empty_string(store):
    # Pending turns store friday_reply="" — Oracle would keep that as NULL;
    # the store boundary must hand "" back either way.
    assert store.insert_entry(_entry("e1", "pending turn", "", status="pending"))
    rows = store.load_recent()
    assert rows[0]["friday_reply"] == ""
    assert rows[0]["status"] == "pending"


def test_update_finalizes_entry(store):
    assert store.insert_entry(_entry("e1", "q", "", status="pending"))
    assert store.update_entry(
        _entry("e1", "q", "the answer", status="success", agents_involved=["forge"])
    )
    rows = store.load_recent()
    assert rows[0]["friday_reply"] == "the answer"
    assert rows[0]["status"] == "success"
    assert rows[0]["agents_involved"] == ["forge"]


def test_update_missing_returns_false_and_upsert_inserts(store):
    assert store.update_entry(_entry("nope", "q", "a")) is False
    assert store.upsert_entry(_entry("nope", "q", "a")) is True
    rows = store.load_recent()
    assert [r["id"] for r in rows] == ["nope"]
    # Upsert on an existing row updates in place — still exactly one row.
    assert store.upsert_entry(_entry("nope", "q", "a2")) is True
    rows = store.load_recent()
    assert len(rows) == 1
    assert rows[0]["friday_reply"] == "a2"


def test_delete_all(store):
    assert store.insert_entry(_entry("e1", "one", "1"))
    assert store.insert_entry(_entry("e2", "two", "2"))
    assert store.delete_all() is True
    assert store.load_recent() == []


def test_growth_is_bounded(store, monkeypatch):
    monkeypatch.setattr(history_store, "MAX_HISTORY_ENTRIES", 5)
    for i in range(8):
        assert store.insert_entry(_entry(f"e{i}", f"turn {i}", f"r{i}"))
    rows = store.load_recent(100)
    assert len(rows) == 5
    assert [r["id"] for r in rows] == ["e7", "e6", "e5", "e4", "e3"]


def test_load_limit(store):
    for i in range(4):
        assert store.insert_entry(_entry(f"e{i}", f"turn {i}", ""))
    rows = store.load_recent(2)
    assert [r["id"] for r in rows] == ["e3", "e2"]


def test_store_failure_returns_false_and_none(tmp_path):
    db_file = tmp_path / "hist.db"
    broken = ConversationHistoryStore(db_path=str(db_file))
    assert broken.insert_entry(_entry("e1", "x", "y"))
    # Sabotage the backend after construction: the file becomes a directory.
    os.remove(db_file)
    os.mkdir(db_file)
    assert broken.insert_entry(_entry("e2", "x", "y")) is False
    assert broken.update_entry(_entry("e1", "x", "y")) is False
    assert broken.load_recent() is None
