"""TASK-DB-002 — watch-envelope table tests (scoping doc section 5).

Runs in CI against the test suite's explicit SQLite URL (see
``IntelX/tests/conftest.py``). Tests are NOT run by this authoring
pass — they are written for CI (see MANIFEST.md).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from intelx.db.models import WatchEnvelope
from intelx.db.session import get_sessionmaker
from intelx.watches.db_seen_store import DbSeenStore
from intelx.watches.engine import (
    WATCH_AI_MODEL_RELEASES,
    FeedItem,
    SeenStore,
    build_envelope,
)

NOW = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)


@pytest.fixture
def db_session_factory():
    """Get active async sessionmaker (same pattern as test_repos.py)."""
    return get_sessionmaker()


def make_envelope() -> dict:
    item = FeedItem(
        url="https://example.com/gpt9-turbo",
        title="Introducing GPT-9 Turbo for developers via the API",
        summary="The newest model is here.",
        published_at=NOW,
        publisher="Example RSS",
        source_feed="https://feed.example/rss.xml",
    )
    return build_envelope(
        WATCH_AI_MODEL_RELEASES, item, 5, ["release:+5"], NOW
    )


@pytest.mark.asyncio
async def test_db002_watch_envelope_idempotent(
    db_session_factory, tmp_path: Path
) -> None:
    """Scoping test 3: the same dedupe_key inserted twice yields one row.

    The unique ``dedupe_key`` is the idempotency guard that replaces
    "already in the file" — a re-delivered envelope must not duplicate.
    """
    store = DbSeenStore(
        db_session_factory, file_store=SeenStore(tmp_path / "state.json")
    )
    envelope = make_envelope()
    assert await store.record_envelope(envelope) is True
    assert await store.record_envelope(envelope) is False

    async with db_session_factory() as session:
        rows = (
            await session.execute(select(WatchEnvelope))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].dedupe_key == envelope["dedupe_key"]
    assert rows[0].envelope_id == envelope["envelope_id"]


@pytest.mark.asyncio
async def test_db002_watch_envelope_roundtrip(
    db_session_factory, tmp_path: Path
) -> None:
    """The stored envelope reads back verbatim (outbox-history mirror)."""
    store = DbSeenStore(
        db_session_factory, file_store=SeenStore(tmp_path / "state.json")
    )
    envelope = make_envelope()
    assert await store.record_envelope(envelope) is True

    async with db_session_factory() as session:
        row = (
            await session.execute(
                select(WatchEnvelope).where(
                    WatchEnvelope.dedupe_key == envelope["dedupe_key"]
                )
            )
        ).scalars().one()
    assert row.envelope_json == envelope
    assert row.title == envelope["title"]
    assert row.url == envelope["url"]
    assert row.score == envelope["score"]
    assert row.alert_class == envelope["alert_class"]


@pytest.mark.asyncio
async def test_db002_watch_envelope_db_down_returns_false(tmp_path: Path) -> None:
    """With the DB unreachable, record_envelope fails safe (not raise).

    The envelope is already in the JSONL outbox — the DB row is a
    mirror, so a DB outage must never fail the poll. The failure is
    logged + counted (fallback_counts()["envelope"] == 1).
    """

    def broken_factory():
        raise RuntimeError("simulated DB outage")

    store = DbSeenStore(
        broken_factory, file_store=SeenStore(tmp_path / "state.json")
    )
    assert await store.record_envelope(make_envelope()) is False
    assert store.fallback_counts()["envelope"] == 1
    assert store.degraded is True
