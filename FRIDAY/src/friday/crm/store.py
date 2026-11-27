"""CRM store for TASK-FRD-062 — contacts and deals in FRIDAY's Oracle schema.

Backend selection follows the established store pattern
(``friday.api.history_store`` / ``friday.agent.checkpoint``):

* no ``engine`` -> Oracle Autonomous Database, schema ``FRIDAY``, via the
  shared engine and the ``contacts`` / ``deals`` tables declared in
  :mod:`friday.core.oracle` (created idempotently by ``ensure_schema``).
  This is what the production agent gets.
* ``engine`` given -> the caller-supplied SQLAlchemy engine, used only
  inside a test run (gated by
  :func:`friday.core.oracle.ephemeral_backend_allowed`, exactly like the
  other test-only backends). Tests pass an in-memory SQLite engine and
  only the two CRM tables are created on it.

All queries are SQLAlchemy Core constructs (``select`` / ``insert`` /
``update``) so the same code compiles for Oracle and for SQLite in tests —
no raw SQL, no dialect-specific syntax.

Fail-closed rules (the acceptance script's failure cases live here, not
in the tools): an unknown contact/deal reference raises instead of being
guessed; an invalid deal stage raises with the valid list; a duplicate
email raises. Stage changes are append-only history in the deal's
``notes_json`` (capped), with ``stage_changed_at`` updated on every move.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from friday.core import oracle
from friday.core.exceptions import PersistenceConfigError

#: Deal pipeline stages, in order (board acceptance, TASK-FRD-062).
DEAL_STAGES: tuple[str, ...] = (
    "lead",
    "contacted",
    "proposal",
    "negotiation",
    "won",
    "lost",
)

#: Stage-history entries kept per deal (append-only, oldest dropped first).
STAGE_HISTORY_CAP = 20

#: Default list cap — the CRM is owner-scale; a voice read-back must stay short.
DEFAULT_LIMIT = 20

_store: "CrmStore | None" = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _like_escape(fragment: str) -> str:
    """Escape LIKE wildcards so a name fragment matches literally."""
    return (
        fragment.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


def _contact_from_row(row: dict[str, Any]) -> dict[str, Any]:
    email = row.get("email") or None
    phone = row.get("phone") or None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": email,
        "phone": phone,
        "company": row.get("company") or None,
        "source": row.get("source") or None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        # A contact with neither email nor phone cannot be reached; the
        # read-back says so instead of implying a channel exists.
        "unreachable": not email and not phone,
    }


def _deal_from_row(row: dict[str, Any]) -> dict[str, Any]:
    try:
        notes = json.loads(row.get("notes_json") or "{}")
    except (ValueError, TypeError):
        notes = {}
    if not isinstance(notes, dict):
        notes = {}
    return {
        "id": row["id"],
        "contact_id": row["contact_id"],
        "title": row["title"],
        "stage": row["stage"],
        "value_text": row.get("value_text") or None,
        "stage_history": list(notes.get("stage_history") or []),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "stage_changed_at": row["stage_changed_at"],
    }


class CrmStore:
    """Contacts and deals, one row per record, Oracle in production."""

    def __init__(self, engine: Any | None = None, *, dsn: str | None = None) -> None:
        self._dsn = dsn
        self._engine = engine
        self._lock = threading.RLock()
        if engine is not None:
            if not oracle.ephemeral_backend_allowed():
                raise PersistenceConfigError(
                    "CrmStore(engine=...) is test-only; omit engine so CRM "
                    "records are written to Oracle Autonomous Database."
                )
            # Test engine: create only the two CRM tables, not the whole
            # FRIDAY schema — the suite stays hermetic and fast.
            oracle.contacts_table.create(engine, checkfirst=True)
            oracle.deals_table.create(engine, checkfirst=True)

    @property
    def _resolved_engine(self) -> Any:
        if self._engine is None:
            self._engine = oracle.get_engine(self._dsn)
        return self._engine

    # ------------------------------------------------------------------
    # contacts
    # ------------------------------------------------------------------
    def add_contact(
        self,
        name: str,
        *,
        email: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        source: str = "chat",
    ) -> dict[str, Any]:
        """Insert a contact. Raises ValueError on a missing name or a duplicate email."""
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("a contact needs a name")
        clean_email = (email or "").strip().lower() or None
        clean_phone = (phone or "").strip() or None
        clean_company = (company or "").strip() or None
        now = _utcnow_iso()
        row = {
            "id": uuid.uuid4().hex,
            "name": clean_name,
            "email": clean_email,
            "phone": clean_phone,
            "company": clean_company,
            "source": (source or "chat").strip() or "chat",
            "notes_json": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            if clean_email is not None and self._get_by_email(clean_email) is not None:
                raise ValueError(
                    f"a contact with email {clean_email} already exists"
                )
            try:
                with self._resolved_engine.begin() as conn:
                    conn.execute(insert(oracle.contacts_table).values(**row))
            except IntegrityError as exc:
                raise ValueError(
                    f"a contact with email {clean_email} already exists"
                ) from exc
        return self.get_contact(row["id"])  # type: ignore[return-value]

    def _get_by_email(self, email: str) -> dict[str, Any] | None:
        with self._resolved_engine.connect() as conn:
            result = conn.execute(
                select(oracle.contacts_table).where(
                    oracle.contacts_table.c.email == email
                )
            ).mappings()
            rows = result.all()
        return _contact_from_row(dict(rows[0])) if rows else None

    def get_contact(self, contact_id: str) -> dict[str, Any] | None:
        with self._resolved_engine.connect() as conn:
            result = conn.execute(
                select(oracle.contacts_table).where(
                    oracle.contacts_table.c.id == contact_id
                )
            ).mappings()
            rows = result.all()
        return _contact_from_row(dict(rows[0])) if rows else None

    def find_contacts(
        self,
        query: str = "",
        *,
        company: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Contacts whose name contains ``query`` (case-insensitive), newest last."""
        stmt = select(oracle.contacts_table)
        fragment = (query or "").strip()
        if fragment:
            stmt = stmt.where(
                oracle.contacts_table.c.name.ilike(
                    f"%{_like_escape(fragment)}%", escape="\\"
                )
            )
        if company:
            stmt = stmt.where(
                oracle.contacts_table.c.company.ilike(
                    f"%{_like_escape(company.strip())}%", escape="\\"
                )
            )
        stmt = stmt.order_by(oracle.contacts_table.c.created_at).limit(limit)
        with self._resolved_engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_contact_from_row(dict(r)) for r in rows]

    def list_contacts(self, *, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
        return self.find_contacts(limit=limit)

    def resolve_contact(self, ref: str) -> dict[str, Any]:
        """Resolve an id or a name fragment to exactly one contact.

        Raises KeyError when nothing matches and ValueError when the
        fragment is ambiguous — the caller must ask the owner, never guess.
        """
        ref_text = (ref or "").strip()
        if not ref_text:
            raise KeyError("no contact reference given")
        direct = self.get_contact(ref_text)
        if direct is not None:
            return direct
        matches = self.find_contacts(ref_text)
        if not matches:
            raise KeyError(f"no contact matches {ref_text!r}")
        if len(matches) > 1:
            names = ", ".join(f"{m['name']} (id {m['id']})" for m in matches)
            raise ValueError(
                f"{ref_text!r} matches {len(matches)} contacts: {names}. "
                "Say which one — by full name or id."
            )
        return matches[0]

    # ------------------------------------------------------------------
    # deals
    # ------------------------------------------------------------------
    def add_deal(
        self,
        contact_id: str,
        title: str,
        *,
        stage: str = "lead",
        value_text: str | None = None,
    ) -> dict[str, Any]:
        """Insert a deal for an existing contact. Raises on unknown contact or bad stage."""
        clean_title = (title or "").strip()
        if not clean_title:
            raise ValueError("a deal needs a title")
        clean_stage = (stage or "").strip().lower()
        if clean_stage not in DEAL_STAGES:
            raise ValueError(
                f"unknown deal stage {stage!r}; valid stages: {', '.join(DEAL_STAGES)}"
            )
        if self.get_contact((contact_id or "").strip()) is None:
            raise KeyError(f"no contact with id {contact_id!r}")
        now = _utcnow_iso()
        row = {
            "id": uuid.uuid4().hex,
            "contact_id": (contact_id or "").strip(),
            "title": clean_title,
            "stage": clean_stage,
            "value_text": (value_text or "").strip() or None,
            "notes_json": json.dumps(
                {
                    "stage_history": [
                        {"from": None, "to": clean_stage, "at": now}
                    ]
                }
            ),
            "created_at": now,
            "updated_at": now,
            "stage_changed_at": now,
        }
        with self._lock:
            with self._resolved_engine.begin() as conn:
                conn.execute(insert(oracle.deals_table).values(**row))
        return self.get_deal(row["id"])  # type: ignore[return-value]

    def get_deal(self, deal_id: str) -> dict[str, Any] | None:
        with self._resolved_engine.connect() as conn:
            result = conn.execute(
                select(oracle.deals_table).where(
                    oracle.deals_table.c.id == deal_id
                )
            ).mappings()
            rows = result.all()
        return _deal_from_row(dict(rows[0])) if rows else None

    def list_deals(
        self,
        *,
        contact_id: str | None = None,
        stage: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        stmt = select(oracle.deals_table)
        if contact_id:
            stmt = stmt.where(oracle.deals_table.c.contact_id == contact_id)
        if stage:
            clean_stage = stage.strip().lower()
            if clean_stage not in DEAL_STAGES:
                raise ValueError(
                    f"unknown deal stage {stage!r}; valid stages: {', '.join(DEAL_STAGES)}"
                )
            stmt = stmt.where(oracle.deals_table.c.stage == clean_stage)
        stmt = stmt.order_by(oracle.deals_table.c.created_at).limit(limit)
        with self._resolved_engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_deal_from_row(dict(r)) for r in rows]

    def resolve_deal(self, ref: str) -> dict[str, Any]:
        """Resolve an id or a title fragment to exactly one deal (see resolve_contact)."""
        ref_text = (ref or "").strip()
        if not ref_text:
            raise KeyError("no deal reference given")
        direct = self.get_deal(ref_text)
        if direct is not None:
            return direct
        stmt = (
            select(oracle.deals_table)
            .where(
                oracle.deals_table.c.title.ilike(
                    f"%{_like_escape(ref_text)}%", escape="\\"
                )
            )
            .order_by(oracle.deals_table.c.created_at)
        )
        with self._resolved_engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        matches = [_deal_from_row(dict(r)) for r in rows]
        if not matches:
            raise KeyError(f"no deal matches {ref_text!r}")
        if len(matches) > 1:
            titles = ", ".join(f"{m['title']} (id {m['id']})" for m in matches)
            raise ValueError(
                f"{ref_text!r} matches {len(matches)} deals: {titles}. "
                "Say which one — by full title or id."
            )
        return matches[0]

    def set_deal_stage(self, deal_id: str, new_stage: str) -> dict[str, Any]:
        """Move a deal to a new stage, recording the old stage in history.

        Raises KeyError for an unknown deal and ValueError for an invalid
        stage. Moving to the stage the deal is already in is a no-op that
        reports the current stage instead of writing a history row.
        """
        clean_stage = (new_stage or "").strip().lower()
        if clean_stage not in DEAL_STAGES:
            raise ValueError(
                f"unknown deal stage {new_stage!r}; valid stages: {', '.join(DEAL_STAGES)}"
            )
        deal = self.get_deal((deal_id or "").strip())
        if deal is None:
            raise KeyError(f"no deal with id {deal_id!r}")
        old_stage = deal["stage"]
        if old_stage == clean_stage:
            return {**deal, "stage_unchanged": True}
        now = _utcnow_iso()
        history = list(deal["stage_history"] or [])
        history.append({"from": old_stage, "to": clean_stage, "at": now})
        history = history[-STAGE_HISTORY_CAP:]
        with self._lock:
            with self._resolved_engine.begin() as conn:
                conn.execute(
                    update(oracle.deals_table)
                    .where(oracle.deals_table.c.id == deal["id"])
                    .values(
                        stage=clean_stage,
                        notes_json=json.dumps({"stage_history": history}),
                        updated_at=now,
                        stage_changed_at=now,
                    )
                )
        moved = self.get_deal(deal["id"])
        assert moved is not None
        return {**moved, "previous_stage": old_stage}

    def delete_all(self) -> int:
        """Delete every CRM row. Test-only cleanup; never called in production."""
        if not oracle.ephemeral_backend_allowed():
            raise PersistenceConfigError("CrmStore.delete_all is test-only")
        with self._lock:
            with self._resolved_engine.begin() as conn:
                contacts = conn.execute(delete(oracle.contacts_table)).rowcount or 0
                deals = conn.execute(delete(oracle.deals_table)).rowcount or 0
        return contacts + deals


def default_store() -> CrmStore:
    """Process-wide CRM store (Oracle in production). Constructed lazily so
    importing a module that declares a tool never opens a socket."""
    global _store
    if _store is None:
        _store = CrmStore()
    return _store


__all__ = ["CrmStore", "DEAL_STAGES", "STAGE_HISTORY_CAP", "default_store"]
