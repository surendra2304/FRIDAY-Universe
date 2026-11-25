"""TASK-DB-002 — DB-backed seen-store tests (scoping doc section 5).

These tests run in CI against the test suite's explicit SQLite URL
(see ``IntelX/tests/conftest.py``: ``INTELX_DB_URL`` is set to a
SQLite file and ``Base.metadata.create_all`` runs before every test,
so ``watch_seen`` exists here without any migration step). Production
code refuses SQLite outside tests; these tests use the explicit test
URL only. Tests are NOT run by this authoring pass — they are written
for CI (see MANIFEST.md).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete, select

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from intelx.db.models import WatchSeen
from intelx.db.session import get_sessionmaker
from intelx.watches.db_seen_store import DbSeenStore
from intelx.watches.engine import FeedItem, SeenStore

NOW = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)


@pytest.fixture
def db_session_factory():
    """Get active async sessionmaker (same pattern as test_repos.py)."""
    return get_sessionmaker()


def make_item(url: str, title: str) -> FeedItem:
    return FeedItem(
        url=url,
        title=title,
        summary="Test summary.",
        published_at=NOW,
        publisher="Example",
        source_feed="https://feed.example/rss.xml",
    )


def make_store(db_session_factory, tmp_path: Path) -> DbSeenStore:
    return DbSeenStore(
        db_session_factory,
        file_store=SeenStore(tmp_path / "state.json"),
    )


@pytest.mark.asyncio
async def test_db002_watch_seen_roundtrip(db_session_factory, tmp_path: Path) -> None:
    """Scoping test 1: a marked item reads back with fingerprint/status/first_seen."""
    store = make_store(db_session_factory, tmp_path)
    item = make_item(
        "https://example.com/gpt9-turbo",
        "Introducing GPT-9 Turbo for developers via the API, now generally available",
    )
    store.mark("ai-model-releases", item, "alerted", fired_at=NOW)
    await store.save()

    # A fresh store instance proves the read path goes through the DB,
    # not the first instance's in-memory cache.
    fresh = make_store(db_session_factory, tmp_path)
    await fresh.load("ai-model-releases")
    section = fresh.section("ai-model-releases")
    assert len(section["seen"]) == 1
    record = next(iter(section["seen"].values()))
    assert record["status"] == "alerted"
    assert record["first_seen"] is not None
    assert record["fired_at"] == NOW.isoformat()
    assert fresh.alerts_today("ai-model-releases", NOW) == 1
    assert fresh.fallback_counts() == {
        "load": 0,
        "save": 0,
        "envelope": 0,
        "prune": 0,
    }


@pytest.mark.asyncio
async def test_db002_watch_seen_dedupe(db_session_factory, tmp_path: Path) -> None:
    """Scoping test 2: the same URL fingerprint marked twice yields one row.

    The poller's duplicate check is ``fp in section["seen"]`` — after a
    save + reload the fingerprint must still be present, so the second
    poll treats the item as a duplicate instead of re-alerting.
    """
    store = make_store(db_session_factory, tmp_path)
    item = make_item("https://example.com/gpt9-turbo", "Introducing GPT-9 Turbo")
    store.mark("ai-model-releases", item, "below_threshold")
    store.mark("ai-model-releases", item, "alerted", fired_at=NOW)
    await store.save()

    async with db_session_factory() as session:
        rows = (
            await session.execute(select(WatchSeen))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "alerted"

    fresh = make_store(db_session_factory, tmp_path)
    await fresh.load("ai-model-releases")
    from intelx.watches.engine import url_fingerprint

    assert url_fingerprint(item.url) in fresh.section("ai-model-releases")["seen"]


@pytest.mark.asyncio
async def test_db002_watch_seen_prune(db_session_factory, tmp_path: Path) -> None:
    """Scoping test 4: records older than 90 days (non-alert) are pruned.

    Retention parity with the JSON file (``SeenStore.save`` prunes the
    same classes); ``alerted`` / ``suppressed_budget`` rows are kept.
    """
    store = make_store(db_session_factory, tmp_path)
    old = NOW - timedelta(days=100)
    recent = NOW - timedelta(days=10)
    async with db_session_factory() as session:
        session.add_all(
            [
                WatchSeen(
                    watch_id="ai-model-releases",
                    fingerprint="old-below",
                    status="below_threshold",
                    first_seen=old,
                ),
                WatchSeen(
                    watch_id="ai-model-releases",
                    fingerprint="old-alerted",
                    status="alerted",
                    first_seen=old,
                    fired_at=old,
                ),
                WatchSeen(
                    watch_id="ai-model-releases",
                    fingerprint="recent-below",
                    status="below_threshold",
                    first_seen=recent,
                ),
            ]
        )
        await session.commit()

    deleted = await store.prune()
    assert deleted == 1
    async with db_session_factory() as session:
        remaining = (
            await session.execute(select(WatchSeen.fingerprint))
        ).scalars().all()
    assert sorted(remaining) == ["old-alerted", "recent-below"]


@pytest.mark.asyncio
async def test_db002_seen_store_file_fallback(tmp_path: Path) -> None:
    """Scoping test 5: with the DB unreachable, the watch falls back to state.json.

    The fallback must be observable (logged + counted) and the file
    must remain a complete record — the poller still marks/alerts off
    the file truth. No database is touched here: the session factory
    raises on every call, which is exactly the "DB unreachable" shape.
    """

    def broken_factory():
        raise RuntimeError("simulated DB outage")

    state_path = tmp_path / "state.json"
    file_store = SeenStore(state_path)
    item_seen = make_item("https://example.com/old-story", "An older story we already saw")
    file_store.mark("ai-model-releases", item_seen, "alerted", fired_at=NOW)
    file_store.save()
    assert state_path.exists()

    store = DbSeenStore(broken_factory, file_store=file_store)
    await store.load("ai-model-releases")
    # The file's record is visible through the DB store's section shape.
    from intelx.watches.engine import url_fingerprint

    assert url_fingerprint(item_seen.url) in store.section("ai-model-releases")["seen"]
    assert store.degraded is True
    assert store.fallback_counts()["load"] == 1

    new_item = make_item("https://example.com/new-story", "A brand new story just published today")
    store.mark("ai-model-releases", new_item, "below_threshold")
    await store.save()
    assert store.fallback_counts()["save"] == 1

    # The file on disk now holds both records: the fallback is complete.
    on_disk = json.loads(state_path.read_text(encoding="utf-8"))
    seen = on_disk["watches"]["ai-model-releases"]["seen"]
    assert url_fingerprint(item_seen.url) in seen
    assert url_fingerprint(new_item.url) in seen
    assert seen[url_fingerprint(new_item.url)]["status"] == "below_threshold"
