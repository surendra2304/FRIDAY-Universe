"""TASK-REL-041 tests: conversation-history writes under parallel load.

Regression target (found by TASK-REL-039's live barrage, 2026-11-15):
during 19 concurrent /api/chat turns, ``friday.api.history_store`` logged
16 ORA-00060 deadlock warnings and the victim writes returned ``False`` —
per REL-029's design those turns stayed memory-only and would have been
lost on the next restart. The store's Oracle writes ran fully
concurrently (one pooled connection per ``asyncio.to_thread`` writer), so
the insert-plus-cap-trim transactions deadlocked each other.

The production Oracle is modelled with a fake SQLAlchemy engine that
reproduces the observed behaviour:

* each ``engine.begin()`` is an independent transaction, statements take
  a few milliseconds (the loaded host measured ~29 ms upserts);
* with ``deadlock_on_overlap``, a transaction that begins while another
  write transaction is active is the deadlock victim: its statement
  raises ORA-00060, exactly the error the production journal showed;
* ``fail_next`` injects transient ORA-00060s regardless of overlap,
  modelling a writer *outside* this process (the case the in-process
  lock cannot prevent and the bounded retry exists for).

The fix under test: writes are serialised process-wide
(``history_store._WRITE_LOCK``) and transient Oracle lock errors are
retried with bounded backoff inside the store.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from sqlalchemy.exc import OperationalError

from friday.api import history_store
from friday.api.history_store import ConversationHistoryStore


def _entry(entry_id: str, user: str = "turn", reply: str = "") -> dict:
    return {
        "id": entry_id,
        "timestamp": "2026-11-15T04:29:20+00:00",
        "user_input": user,
        "friday_reply": reply,
        "input_type": "text",
        "status": "success",
        "agents_involved": [],
        "metadata": {},
    }


def _ora(code: str, text: str) -> OperationalError:
    return OperationalError("stmt", {}, Exception(f"{code}: {text}"))


class _FakeResult:
    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount


class _FakeConnection:
    def __init__(self, engine: "_FakeEngine", doomed: bool) -> None:
        self._engine = engine
        self._doomed = doomed

    def execute(self, stmt, params=None):  # noqa: ANN001 - fake DBAPI surface
        eng = self._engine
        if eng.fail_next > 0:
            eng.fail_next -= 1
            raise _ora("ORA-00060", "deadlock detected while waiting for resource")
        if eng.always_raise is not None:
            raise eng.always_raise
        if self._doomed:
            raise _ora("ORA-00060", "deadlock detected while waiting for resource")
        time.sleep(eng.statement_seconds)
        return _FakeResult(rowcount=eng.rowcount)


class _BeginContext:
    def __init__(self, engine: "_FakeEngine") -> None:
        self._engine = engine

    def __enter__(self) -> _FakeConnection:
        eng = self._engine
        with eng._mu:
            eng.begin_calls += 1
            eng.active += 1
            eng.max_active = max(eng.max_active, eng.active)
            doomed = eng.deadlock_on_overlap and eng.active > 1
        return _FakeConnection(eng, doomed)

    def __exit__(self, *exc) -> bool:
        with self._engine._mu:
            self._engine.active -= 1
        return False


class _FakeEngine:
    """Minimal stand-in for the SQLAlchemy engine the store writes through."""

    def __init__(
        self,
        *,
        statement_seconds: float = 0.02,
        deadlock_on_overlap: bool = True,
        rowcount: int = 1,
    ) -> None:
        self.statement_seconds = statement_seconds
        self.deadlock_on_overlap = deadlock_on_overlap
        self.rowcount = rowcount
        self.fail_next = 0
        self.always_raise: Exception | None = None
        self.begin_calls = 0
        self.active = 0
        self.max_active = 0
        self._mu = threading.Lock()

    def begin(self) -> _BeginContext:
        return _BeginContext(self)


@pytest.fixture()
def oracle_store(monkeypatch):
    """A store on the Oracle backend, backed by the fake engine."""
    # raising=False: on clean main the constant does not exist yet, and the
    # defect tests must fail on behaviour there, not on the patch itself.
    monkeypatch.setattr(
        history_store, "_WRITE_RETRY_BASE_SECONDS", 0.001, raising=False
    )
    store = ConversationHistoryStore()
    engine = _FakeEngine()
    store._oracle_engine = engine
    return store, engine


def _run_threads(n: int, fn) -> list:
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def worker(i: int) -> None:
        barrier.wait(timeout=30)
        results[i] = fn(i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


# ----------------------------------------------------------------------
# Defect tests — each fails on clean main, passes with the REL-041 fix
# ----------------------------------------------------------------------
def test_concurrent_inserts_are_serialised_and_all_land(oracle_store):
    store, engine = oracle_store
    results = _run_threads(12, lambda i: store.insert_entry(_entry(f"c{i}")))
    assert results == [True] * 12
    # Serialised: never two write transactions in flight at once.
    assert engine.max_active == 1


def test_async_wrappers_concurrent_inserts_all_land(oracle_store):
    store, engine = oracle_store

    async def barrage():
        return await asyncio.gather(
            *(store.insert_entry_async(_entry(f"a{i}")) for i in range(10))
        )

    results = asyncio.run(barrage())
    assert list(results) == [True] * 10
    assert engine.max_active == 1


def test_insert_retries_transient_deadlock(oracle_store):
    store, engine = oracle_store
    engine.fail_next = 2  # a cross-process writer kills the first 2 attempts
    assert store.insert_entry(_entry("r1")) is True
    assert engine.begin_calls >= 3  # 2 victim attempts + the one that landed


def test_update_retries_transient_deadlock(oracle_store):
    store, engine = oracle_store
    engine.fail_next = 1
    assert store.update_entry(_entry("r2", reply="final")) is True
    assert engine.begin_calls >= 2


# ----------------------------------------------------------------------
# Guards — behaviour that must hold before and after the fix
# ----------------------------------------------------------------------
def test_concurrent_sqlite_writers_all_land(tmp_path):
    """The real store on the sanctioned SQLite backend, hit in parallel.

    Mirrors the production call shape (many threads, one store, insert
    then upsert per turn): every write must land and every row must be
    readable afterwards. (This one passes on clean main too — SQLite's
    writer behaviour differs from Oracle's; it guards the shared public
    write path the lock now wraps.)
    """
    store = ConversationHistoryStore(db_path=str(tmp_path / "hist.db"))

    def work(i: int) -> bool:
        if not store.insert_entry(_entry(f"s{i}", user=f"turn {i}")):
            return False
        return store.upsert_entry(_entry(f"s{i}", user=f"turn {i}", reply=f"r{i}"))

    results = _run_threads(16, work)
    assert results == [True] * 16
    rows = store.load_recent(100)
    assert rows is not None and len(rows) == 16
    assert {r["id"] for r in rows} == {f"s{i}" for i in range(16)}
    assert all(r["friday_reply"] == f"r{r['id'][1:]}" for r in rows)


def test_non_transient_error_is_not_retried(oracle_store):
    store, engine = oracle_store
    engine.always_raise = _ora("ORA-00001", "unique constraint violated")
    assert store.insert_entry(_entry("u1")) is False
    assert engine.begin_calls == 1  # no retry on a permanent error


def test_update_miss_still_returns_false(oracle_store):
    store, engine = oracle_store
    engine.rowcount = 0
    assert store.update_entry(_entry("ghost")) is False


def test_deadlock_detector_recognises_wrapped_errors():
    wrapped = OperationalError(
        "INSERT INTO conversation_history ...",
        {},
        Exception("ORA-00060: deadlock detected while waiting for resource"),
    )
    assert history_store._is_transient_lock_error(wrapped) is True
    assert history_store._is_transient_lock_error(
        _ora("ORA-00054", "resource busy and acquire with NOWAIT specified")
    ) is True
    assert history_store._is_transient_lock_error(
        _ora("ORA-00001", "unique constraint violated")
    ) is False
    assert history_store._is_transient_lock_error(ValueError("boom")) is False
