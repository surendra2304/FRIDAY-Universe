"""DB-backed seen-store for IntelX standing watches (TASK-DB-002).

Decision D1, option (a): one writer, one truth. When an Oracle DSN is
configured, the watch poller reads/writes seen-store entries in the
``watch_seen`` table (Autonomous DB #2, INTELX schema) and fired
envelopes in ``watch_envelopes``. When the database is unreachable, the
store falls back to the JSON file (``state.json``) — and the fallback
is *observable*: every fallback logs a warning and increments a
counter (``fallback_counts()``). A silent permanent fallback is the
failure mode TASK-DB-001 is hunting in Stratex; it is not repeated
here. The JSONL outbox is untouched by this module: envelopes are
still appended to the file outbox first (TASK-PRO-001's delivery
contract), and the DB envelope row is a durable mirror.

Interface: the synchronous ``section`` / ``mark`` / ``alerts_today``
methods match ``intelx.watches.engine.SeenStore`` exactly, so the
poller's dedupe / budget logic reads the same section shape
(``{"seen": {...}, "title_fps": {...}, "alerts_by_day": {...}}``).
Persistence is async (``load`` / ``save`` are coroutines) because the
IntelX DB layer is async SQLAlchemy — the poller is already async, so
the wiring leg awaits them (see "Wiring" below). The file store keeps
working unchanged in tests and standalone runs: if no session factory
is given, this store behaves as a thin cache over the file store.

One deliberate difference from the file store, recorded here and in
the evidence doc: ``mark`` preserves ``first_seen`` when an item is
re-marked (the file store overwrites it with "now"). ``first_seen``
means first contact; re-marks do not occur in the poll flow because
duplicates are skipped before ``mark`` is called, so the difference
is unobservable in production and the DB value stays truthful.

Wiring (follow-up leg, not this file): ``WatchService`` should accept
an optional ``seen_store``; at poll start ``await store.load(watch.id)``,
at poll end ``await store.save()`` (replacing the synchronous
``self.store.save()``), and after each ``outbox.append(envelope)``
``await store.record_envelope(envelope)``. Until that wiring lands,
the file store remains the live path and this module is exercised by
its tests only.
"""

from __future__ import annotations

import copy
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from intelx.db.models import WatchEnvelope, WatchSeen
from intelx.watches.engine import (
    IST,
    PRUNE_DAYS,
    UTC,
    FeedItem,
    SeenStore,
    default_state_path,
    title_fingerprint,
    url_fingerprint,
)

logger = logging.getLogger("intelx.watches")

# Statuses whose rows are never pruned (mirrors SeenStore.save()).
_RETAINED_STATUSES = ("alerted", "suppressed_budget")

_FALLBACK_KEYS = ("load", "save", "envelope", "prune")


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO timestamp from a cached seen record (None stays None)."""
    if not value:
        return None
    return datetime.fromisoformat(value)


def _as_utc(value: datetime | None) -> datetime | None:
    """Treat a naive datetime (SQLite read-back) as UTC; aware values pass through."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def count_file_records(
    state_path: Path | str | None,
    outbox_path: Path | str | None,
    forecast_state_path: Path | str | None = None,
) -> dict[str, Any]:
    """Dry-run accounting for the file -> DB migration (TASK-DB-002).

    Counts the records per class that the migration leg must move, without
    writing anything: seen-store entries (``state.json``), outbox
    envelopes (``outbox.jsonl``), and — when a Futuris state file is
    given — ``forecast_state.json`` forecasts / actuals / calibration
    entries. Files that do not exist count as zero; files that exist
    but cannot be parsed are listed under ``unreadable_files`` so the
    migration evidence names them instead of silently dropping them.
    """
    counts: dict[str, Any] = {
        "seen_entries": 0,
        "envelopes": 0,
        "forecasts": 0,
        "actuals": 0,
        "calibration": 0,
        "unreadable_files": [],
    }
    if state_path is not None:
        path = Path(state_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for section in data.get("watches", {}).values():
                    counts["seen_entries"] += len(section.get("seen", {}))
            except (json.JSONDecodeError, OSError, AttributeError, TypeError):
                counts["unreadable_files"].append(str(path))
    if outbox_path is not None:
        path = Path(outbox_path)
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                counts["envelopes"] = sum(1 for line in lines if line.strip())
            except OSError:
                counts["unreadable_files"].append(str(path))
    if forecast_state_path is not None:
        path = Path(forecast_state_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                counts["forecasts"] = len(data.get("forecasts", {}))
                counts["actuals"] = sum(
                    len(v) for v in data.get("actuals", {}).values()
                )
                counts["calibration"] = len(data.get("calibration", {}))
            except (json.JSONDecodeError, OSError, AttributeError, TypeError):
                counts["unreadable_files"].append(str(path))
    return counts


class DbSeenStore:
    """Seen-store backed by ``watch_seen`` / ``watch_envelopes``.

    ``session_factory`` is a callable returning an async SQLAlchemy
    session context manager (``intelx.db.session.get_sessionmaker`` in
    production; the test suite passes the same factory bound to its
    explicit SQLite URL). When it is None, or the database raises, the
    store degrades to the file store — loudly, never silently.
    """

    def __init__(
        self,
        session_factory: Any | None = None,
        *,
        file_store: SeenStore | None = None,
        state_path: Path | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._file_store = file_store or SeenStore(state_path or default_state_path())
        # In-memory sections, same shape as SeenStore: per watch id,
        # {"seen": {fp: record}, "title_fps": {tfp: fp},
        #  "alerts_by_day": {iso-day: count}}.
        self._cache: dict[str, dict[str, Any]] = {}
        self._dirty: set[tuple[str, str]] = set()
        self._fallback_counts: Counter[str] = Counter()
        self._degraded = False

    # -- fallback observability -------------------------------------------

    @property
    def degraded(self) -> bool:
        """True while the store is serving from the file fallback."""
        return self._degraded

    def fallback_counts(self) -> dict[str, int]:
        """How many times each DB operation fell back to the file store.

        Keys: ``load``, ``save``, ``envelope``, ``prune``. All zeros in
        a healthy run; any non-zero value must be explained in the
        evidence doc (risk R2 in the TASK-DB-002 scoping doc).
        """
        return {key: int(self._fallback_counts.get(key, 0)) for key in _FALLBACK_KEYS}

    def _fall_back(self, kind: str, exc: Exception, what: str) -> None:
        self._fallback_counts[kind] += 1
        self._degraded = True
        logger.warning(
            "[Watch] DB seen-store %s failed (%s); falling back to file store "
            "(fallback #%d for %s)",
            what,
            exc,
            self._fallback_counts[kind],
            kind,
        )

    def _resolve_session_factory(self) -> Any:
        if self._session_factory is not None:
            return self._session_factory
        from intelx.db.session import get_sessionmaker

        self._session_factory = get_sessionmaker()
        return self._session_factory

    # -- SeenStore-compatible synchronous interface ------------------------

    def section(self, watch_id: str) -> dict[str, Any]:
        """Return the in-memory section for a watch (same shape as SeenStore)."""
        return self._cache.setdefault(
            watch_id, {"seen": {}, "title_fps": {}, "alerts_by_day": {}}
        )

    def mark(
        self,
        watch_id: str,
        item: FeedItem,
        status: str,
        *,
        fired_at: datetime | None = None,
    ) -> None:
        """Record an item's status, exactly as SeenStore.mark does.

        Deliberate difference (documented in the module docstring):
        ``first_seen`` is preserved when an already-known fingerprint is
        re-marked; the file store overwrites it with "now".
        """
        section = self.section(watch_id)
        fp = url_fingerprint(item.url)
        now = datetime.now(UTC)
        existing = section["seen"].get(fp)
        section["seen"][fp] = {
            "status": status,
            "title": item.title,
            "url": item.url,
            "first_seen": (
                existing.get("first_seen") if existing else now.isoformat()
            ),
            "fired_at": _iso(fired_at),
        }
        tfp = title_fingerprint(item.title)
        if tfp:
            section["title_fps"][tfp] = fp
        if status == "alerted" and fired_at is not None:
            day = fired_at.astimezone(IST).date().isoformat()
            section["alerts_by_day"][day] = section["alerts_by_day"].get(day, 0) + 1
        self._dirty.add((watch_id, fp))

    def alerts_today(self, watch_id: str, now: datetime) -> int:
        """Alerts already fired for this watch today (IST), from the cache."""
        day = now.astimezone(IST).date().isoformat()
        return int(self.section(watch_id)["alerts_by_day"].get(day, 0))

    # -- async persistence ---------------------------------------------------

    async def load(self, watch_id: str) -> None:
        """Hydrate one watch's section from ``watch_seen``.

        On DB failure the section is copied from the file store instead
        (logged + counted); the poller then works off the file truth
        for this poll, exactly as it does today.
        """
        factory = self._resolve_session_factory()
        try:
            async with factory() as session:
                rows = (
                    await session.execute(
                        select(WatchSeen).where(WatchSeen.watch_id == watch_id)
                    )
                ).scalars().all()
        except Exception as exc:  # DB unreachable: fall back, loudly.
            self._fall_back("load", exc, f"load watch {watch_id!r}")
            self._cache[watch_id] = copy.deepcopy(
                self._file_store.section(watch_id)
            )
            return
        section: dict[str, Any] = {"seen": {}, "title_fps": {}, "alerts_by_day": {}}
        for row in rows:
            first_seen = _as_utc(row.first_seen)
            fired_at = _as_utc(row.fired_at)
            section["seen"][row.fingerprint] = {
                "status": row.status,
                "title": None,
                "url": None,
                "first_seen": _iso(first_seen),
                "fired_at": _iso(fired_at),
            }
            if row.title_fingerprint:
                section["title_fps"][row.title_fingerprint] = row.fingerprint
            if row.status == "alerted" and fired_at is not None:
                day = fired_at.astimezone(IST).date().isoformat()
                section["alerts_by_day"][day] = section["alerts_by_day"].get(day, 0) + 1
        self._cache[watch_id] = section
        self._degraded = False

    async def save(self) -> None:
        """Flush dirty seen entries to ``watch_seen`` and prune old rows.

        Deletes rows older than PRUNE_DAYS whose status is not
        ``alerted`` / ``suppressed_budget`` first (the same retention
        rule as ``SeenStore.save``), then upserts the dirty
        (watch, fingerprint) pairs — so a just-marked row survives
        this save even if its preserved ``first_seen`` is old. On DB
        failure the cache is mirrored into the file store and the file
        store saves instead — the file remains a complete fallback,
        and the failure is logged + counted.
        """
        factory = self._resolve_session_factory()
        dirty = sorted(self._dirty)
        cutoff = datetime.now(UTC) - timedelta(days=PRUNE_DAYS)
        try:
            async with factory() as session:
                # Prune BEFORE merging: a just-marked row must survive
                # this save even if its preserved first_seen is old
                # (the file store likewise never prunes a row it has
                # just marked). Rows not touched this poll are pruned.
                await session.execute(
                    delete(WatchSeen).where(
                        WatchSeen.first_seen < cutoff,
                        WatchSeen.status.notin_(_RETAINED_STATUSES),
                    )
                )
                for watch_id, fp in dirty:
                    rec = self._cache.get(watch_id, {}).get("seen", {}).get(fp)
                    if rec is None:
                        continue
                    await session.merge(
                        WatchSeen(
                            watch_id=watch_id,
                            fingerprint=fp,
                            title_fingerprint=_title_fp_of(rec),
                            status=rec["status"],
                            first_seen=_parse_dt(rec.get("first_seen"))
                            or datetime.now(UTC),
                            fired_at=_parse_dt(rec.get("fired_at")),
                        )
                    )
                await session.commit()
        except Exception as exc:  # DB unreachable: fall back, loudly.
            self._fall_back("save", exc, "save")
            self._mirror_to_file()
            self._file_store.save()
            return
        self._dirty.clear()
        self._degraded = False

    async def record_envelope(self, envelope: dict[str, Any]) -> bool:
        """Mirror one fired envelope into ``watch_envelopes``.

        Returns True when a new row was inserted, False when the
        ``dedupe_key`` was already present (idempotent re-delivery) or
        when the DB was unreachable (logged + counted; the envelope is
        already in the JSONL outbox, which stays the delivery record).
        """
        factory = self._resolve_session_factory()
        dedupe_key = envelope.get("dedupe_key")
        try:
            async with factory() as session:
                existing = (
                    await session.execute(
                        select(WatchEnvelope).where(
                            WatchEnvelope.dedupe_key == dedupe_key
                        )
                    )
                ).scalars().first()
                if existing is not None:
                    return False
                row = WatchEnvelope(
                    envelope_id=envelope["envelope_id"],
                    watch_id=envelope["watch_id"],
                    dedupe_key=dedupe_key,
                    title=envelope.get("title"),
                    summary=envelope.get("summary"),
                    url=envelope.get("url"),
                    publisher=envelope.get("publisher"),
                    published_at=_parse_dt(envelope.get("published_at")),
                    fired_at=_parse_dt(envelope.get("fired_at")),
                    score=envelope.get("score"),
                    score_reasons=envelope.get("score_reasons"),
                    alert_class=envelope.get("alert_class"),
                    severity=envelope.get("severity"),
                    envelope_json=envelope,
                )
                session.add(row)
                await session.commit()
                return True
        except IntegrityError:
            # Lost a race with a concurrent insert of the same key.
            return False
        except Exception as exc:  # DB unreachable: fall back, loudly.
            self._fall_back("envelope", exc, "record envelope")
            return False

    async def prune(self, *, days: int = PRUNE_DAYS) -> int:
        """Delete non-retained ``watch_seen`` rows older than ``days``.

        Returns the number of rows deleted (0 on DB failure, which is
        logged + counted; the file store's own prune still runs when the
        store next saves through the file path).
        """
        factory = self._resolve_session_factory()
        cutoff = datetime.now(UTC) - timedelta(days=days)
        try:
            async with factory() as session:
                result = await session.execute(
                    delete(WatchSeen).where(
                        WatchSeen.first_seen < cutoff,
                        WatchSeen.status.notin_(_RETAINED_STATUSES),
                    )
                )
                await session.commit()
                return int(result.rowcount or 0)
        except Exception as exc:  # DB unreachable: fall back, loudly.
            self._fall_back("prune", exc, "prune")
            return 0

    # -- file-fallback mirroring ---------------------------------------------

    def _mirror_to_file(self) -> None:
        """Copy the in-memory cache into the file store's data.

        Used only on DB failure during save(), so the JSON file stays a
        complete fallback. The file store's own save() then prunes and
        writes it atomically, exactly as the file path does today.
        """
        for watch_id, section in self._cache.items():
            target = self._file_store.section(watch_id)
            target["seen"] = copy.deepcopy(section.get("seen", {}))
            target["title_fps"] = copy.deepcopy(section.get("title_fps", {}))
            target["alerts_by_day"] = copy.deepcopy(section.get("alerts_by_day", {}))


def _title_fp_of(record: dict[str, Any]) -> str | None:
    """Title fingerprint for a cached seen record (None if not computable)."""
    title = record.get("title")
    if not title:
        return None
    return title_fingerprint(title)
