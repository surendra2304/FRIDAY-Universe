"""TASK-IG-FRD-002 — Persistent follow-up tracking (IG corpus, DeZzk3XxkrI).

Project JARVIS's whole pitch is "the coworker who never forgets the
follow-up". FRIDAY's A12 sweep (``proactive/followup.py``) pings about
stale *fleet task-ledger* records — it knows nothing about the follow-ups
the OWNER delegates in conversation ("chase the landlord about the
deposit", "check whether the invoice got paid"). Those lived only in the
chat transcript and were dropped the moment the session ended.

This module makes an owner follow-up a first-class, persistent object:

- Restart-safe file-backed registry (atomic JSON writes, the mission
  queue's pattern): id, title, detail, created_at, due_at, status
  (open / done / dropped), source, and a full history.
- Every create and every close is mirrored into Memora through the fixed
  episodic write path (``MemoraClient.record_fact`` with category
  ``followup`` — the MEM-008-fixed path that sends memory_type
  ``episodic``). The mirror is best-effort and HONEST: the outcome
  (``ok`` / ``failed`` + the error) is stored on the record itself. The
  file registry is the source of truth; a Memora outage degrades the
  mirror, never the follow-up, and never reports a mirror that did not
  happen.
- ``due_followups()`` is the sweep surface consumed by the
  ``followup_list`` tool: open follow-ups whose due time has passed (plus
  undated ones older than ``UNDATED_STALE_HOURS``), oldest first. A quiet
  registry returns an empty list — no invented pings.
- Closing is explicit only: ``complete`` (the owner says it's handled)
  or ``drop`` (the owner abandons it). Nothing auto-closes, nothing is
  hard-deleted — closed records stay in the file for audit.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_DROPPED = "dropped"

#: An undated follow-up older than this counts as due for the sweep —
#: "no date" must not mean "never surfaced".
UNDATED_STALE_HOURS = 48.0


class _MemoraLike(Protocol):
    """The subset of MemoraClient the mirror needs (fakes implement it)."""

    def record_fact(
        self,
        agent_name: str,
        fact_text: str,
        category: str = "preference",
        importance: float = 0.95,
    ) -> dict[str, Any]: ...


def _default_store_path() -> str:
    """Runtime-data resolution, same convention as the mission queue."""
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "followups", "registry.json"))
    here = os.path.dirname(__file__)  # .../friday/proactive
    return os.path.abspath(
        os.path.join(here, "..", "..", ".data", "followups", "registry.json")
    )


def _now() -> float:
    return time.time()


class FollowUpRegistry:
    """File-backed registry of owner follow-ups with a Memora mirror."""

    def __init__(
        self,
        store_path: Optional[str] = None,
        *,
        memora_client: Optional[_MemoraLike] = None,
        agent_name: str = "friday",
    ) -> None:
        self._path = store_path or _default_store_path()
        self._lock = threading.RLock()
        self._cache: Optional[list[dict[str, Any]]] = None
        self._memora = memora_client
        self._agent_name = agent_name
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = list(data.get("followups") or [])
        except FileNotFoundError:
            self._cache = []
        except Exception as exc:
            logger.warning(
                "[FOLLOWUP] registry unreadable (%s) — starting empty, file untouched",
                exc,
            )
            self._cache = []
        return self._cache

    def _save(self, items: list[dict[str, Any]]) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"followups": items, "saved_at": _now()}, f, indent=2)
        os.replace(tmp, self._path)

    # ------------------------------------------------------------------
    # Memora mirror (best-effort, honestly reported)
    # ------------------------------------------------------------------
    def _mirror(self, record: dict[str, Any], event: str) -> dict[str, Any]:
        """Mirror one lifecycle event into Memora's episodic store.

        Returns {status: ok|failed|unavailable, detail}. Never raises:
        the registry write has already happened and stands on its own.
        """
        if self._memora is None:
            return {"status": "unavailable", "detail": "no Memora client wired"}
        text = (
            f"FOLLOWUP ({event}): {record['title']}"
            + (f" — {record['detail']}" if record.get("detail") else "")
            + (f" [id {record['id']}]")
        )
        try:
            result = self._memora.record_fact(
                self._agent_name, text, category="followup", importance=0.9
            )
        except Exception as exc:
            return {"status": "failed", "detail": f"{type(exc).__name__}: {exc}"}
        if not isinstance(result, dict):
            return {"status": "failed", "detail": f"unexpected result: {result!r:.120}"}
        status = str(result.get("status") or "")
        if status == "success":
            return {"status": "ok", "detail": f"memora id {result.get('id') or '?'}"}
        if status == "local_only":
            # Stored in FRIDAY's local memory with a queued re-sync — a
            # real store, reported as what it is, not as a cloud write.
            return {
                "status": "ok",
                "detail": f"local_only (sync pending), id {result.get('id') or '?'}",
            }
        return {
            "status": "failed",
            "detail": str(result.get("error") or f"status {status or 'unknown'}")[:300],
        }

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def add(
        self,
        title: str,
        detail: str = "",
        *,
        due_at: Optional[float] = None,
        source: str = "chat",
    ) -> dict[str, Any]:
        title_text = (title or "").strip()
        if not title_text:
            raise ValueError("a follow-up needs a title")
        record = {
            "id": f"fu-{uuid.uuid4().hex[:10]}",
            "title": title_text,
            "detail": (detail or "").strip(),
            "status": STATUS_OPEN,
            "source": source,
            "created_at": _now(),
            "due_at": due_at,
            "closed_at": None,
            "history": [{"at": _now(), "event": "created", "detail": source}],
            "memora_mirror": {},
        }
        record["memora_mirror"] = self._mirror(record, "open")
        with self._lock:
            items = self._load()
            items.append(record)
            self._save(items)
        return json.loads(json.dumps(record))

    def get(self, followup_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            for item in self._load():
                if item.get("id") == followup_id:
                    return json.loads(json.dumps(item))
        return None

    def list(self, status: Optional[str] = STATUS_OPEN) -> list[dict[str, Any]]:
        with self._lock:
            items = json.loads(json.dumps(self._load()))
        if status:
            items = [i for i in items if i.get("status") == status]
        items.sort(key=lambda i: i.get("created_at") or 0)
        return items

    def _close(self, followup_id: str, status: str, note: str) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            for item in items:
                if item.get("id") == followup_id:
                    if item.get("status") != STATUS_OPEN:
                        raise ValueError(
                            f"follow-up {followup_id} is already {item.get('status')}"
                        )
                    item["status"] = status
                    item["closed_at"] = _now()
                    item.setdefault("history", []).append(
                        {"at": _now(), "event": status, "detail": note}
                    )
                    item["memora_mirror"] = self._mirror(item, status)
                    self._save(items)
                    return json.loads(json.dumps(item))
        raise KeyError(f"no follow-up with id {followup_id!r}")

    def complete(self, followup_id: str, note: str = "") -> dict[str, Any]:
        return self._close(followup_id, STATUS_DONE, note or "marked done")

    def drop(self, followup_id: str, note: str = "") -> dict[str, Any]:
        return self._close(followup_id, STATUS_DROPPED, note or "dropped by owner")

    # ------------------------------------------------------------------
    # sweep surface (morning brief / notifications)
    # ------------------------------------------------------------------
    def due_followups(
        self,
        *,
        now_epoch: Optional[float] = None,
        undated_stale_hours: float = UNDATED_STALE_HOURS,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Open follow-ups that need the owner's eye now, oldest first.

        Due = has a due_at in the past, or has no due_at and is older
        than the stale window. Returns [] when nothing is due.
        """
        now = now_epoch if now_epoch is not None else _now()
        due: list[dict[str, Any]] = []
        for item in self.list(status=STATUS_OPEN):
            due_at = item.get("due_at")
            if due_at is not None:
                if float(due_at) <= now:
                    due.append(item)
            elif (now - float(item.get("created_at") or now)) >= undated_stale_hours * 3600:
                due.append(item)
        return due[:limit]


def default_registry() -> FollowUpRegistry:
    """Registry wired to the real Memora client when one is resolvable.

    The Memora client is constructed lazily and failures degrade to an
    unmirrored registry — construction problems must never take the
    follow-up surface down with them.
    """
    client: Optional[_MemoraLike] = None
    try:
        from friday.memory.memora_client import MemoraClient

        client = MemoraClient()
    except Exception as exc:
        logger.warning("[FOLLOWUP] Memora client unavailable (%s) — mirror off", exc)
    return FollowUpRegistry(memora_client=client)


def format_followup(item: dict[str, Any]) -> str:
    """One-line human rendering for briefs and chat answers."""
    age_h = max(0.0, (_now() - float(item.get("created_at") or _now())) / 3600.0)
    due = ""
    if item.get("due_at"):
        due = f", due {'overdue' if float(item['due_at']) < _now() else 'at ' + time.strftime('%Y-%m-%d %H:%M', time.localtime(float(item['due_at'])))}"
    return (
        f"[{item.get('status')}] {item.get('title')} "
        f"(id {item.get('id')}, open for {age_h:.0f}h{due})"
    )
