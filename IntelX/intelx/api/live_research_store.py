"""Durable persistence for ``research_live`` runs (TASK-REL-038).

The live research pipeline is synchronous and was ephemeral: the result
existed only in the HTTP response, so neither FRIDAY nor a user could ever
retrieve a past research result. This store writes each completed run —
SUCCESS or DEGRADED — verbatim (full result payload + receipt) into the
``live_research_runs`` table of IntelX's existing database (Oracle in
production; the table is created by the lifespan's ``create_all``), and
serves it back by run id after any restart.

Honesty contract: persistence is best-effort and NEVER rewrites history.
If the write fails, ``persist_live_research`` returns ``None`` and the
caller must keep reporting ``durable_run: False``. Retention is bounded
(newest ``MAX_STORED_RUNS`` rows); the write cost is measured and logged.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

MAX_STORED_RUNS = max(10, int(os.getenv("INTELX_LIVE_RESEARCH_MAX_RUNS", "200")))


def _new_run_id(payload: dict) -> str:
    existing = payload.get("run_id")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()[:48]
    return f"lr_{uuid.uuid4().hex[:24]}"


async def persist_live_research(
    task_id: str, query: str, envelope: dict
) -> tuple[str, float] | None:
    """Store one completed live-research envelope.

    Returns ``(run_id, elapsed_ms)`` on success, ``None`` on any failure
    (the failure is logged; the caller's response is never blocked or
    altered by a persistence error).
    """
    started = time.monotonic()
    try:
        from sqlalchemy import delete, func, select

        from intelx.db.models import LiveResearchRun
        from intelx.db.session import get_sessionmaker, get_write_lock

        payload = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
        run_id = _new_run_id(payload)
        # The stored copies describe themselves truthfully: by the time a
        # record can be read back, the run IS durable and carries this id.
        stored_payload = {**payload, "run_id": run_id, "durable_run": True}
        stored_receipt = envelope.get("receipt") if isinstance(envelope.get("receipt"), dict) else None
        if stored_receipt is not None:
            stored_receipt = {**stored_receipt}
            evidence = stored_receipt.get("verification_evidence")
            if isinstance(evidence, dict):
                stored_receipt["verification_evidence"] = {**evidence, "durable_run": True}
            receipt_result = stored_receipt.get("result")
            if isinstance(receipt_result, dict):
                stored_receipt["result"] = {**receipt_result, "run_id": run_id}
        row = LiveResearchRun(
            id=run_id,
            task_id=str(task_id)[:128],
            query=str(query)[:4000],
            status=str(envelope.get("status") or "DEGRADED")[:16],
            synthesis_status=(
                str(payload["synthesis_status"])[:32]
                if payload.get("synthesis_status") is not None
                else None
            ),
            answer_kind=(
                str(payload["answer_kind"])[:64]
                if payload.get("answer_kind") is not None
                else None
            ),
            summary=str(envelope.get("summary") or "")[:4000] or None,
            payload_json=stored_payload,
            receipt_json=stored_receipt,
        )
        sessionmaker = get_sessionmaker()
        async with get_write_lock():
            async with sessionmaker() as session:
                await session.merge(row)
                await session.flush()  # the count below must include this row
                # Bounded retention: keep only the newest MAX_STORED_RUNS.
                total = (
                    await session.execute(select(func.count()).select_from(LiveResearchRun))
                ).scalar_one()
                if total > MAX_STORED_RUNS:
                    stale_ids = (
                        await session.execute(
                            select(LiveResearchRun.id)
                            .order_by(LiveResearchRun.created_at.desc())
                            .offset(MAX_STORED_RUNS)
                        )
                    ).scalars().all()
                    if stale_ids:
                        await session.execute(
                            delete(LiveResearchRun).where(LiveResearchRun.id.in_(stale_ids))
                        )
                await session.commit()
        elapsed_ms = (time.monotonic() - started) * 1000.0
        logger.info(
            "live research persisted run_id=%s status=%s write_ms=%.1f",
            run_id, row.status, elapsed_ms,
        )
        return run_id, elapsed_ms
    except Exception as exc:  # persistence must never break the live answer
        logger.warning("live research persistence failed (%s)", type(exc).__name__)
        return None


def _row_to_record(row: Any) -> dict:
    return {
        "run_id": row.id,
        "task_id": row.task_id,
        "query": row.query,
        "status": row.status,
        "synthesis_status": row.synthesis_status,
        "answer_kind": row.answer_kind,
        "summary": row.summary,
        "result": row.payload_json or {},
        "receipt": row.receipt_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "durable_run": True,
    }


async def fetch_live_research(run_id: str) -> dict | None:
    """Return the stored record for ``run_id`` verbatim, or None."""
    from sqlalchemy import select

    from intelx.db.models import LiveResearchRun
    from intelx.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        row = (
            await session.execute(
                select(LiveResearchRun).where(LiveResearchRun.id == run_id)
            )
        ).scalar_one_or_none()
        return _row_to_record(row) if row is not None else None


async def list_live_research(limit: int = 20) -> list[dict]:
    """Return metadata for the newest stored runs (payloads excluded)."""
    from sqlalchemy import select

    from intelx.db.models import LiveResearchRun
    from intelx.db.session import get_sessionmaker

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        rows = (
            await session.execute(
                select(LiveResearchRun)
                .order_by(LiveResearchRun.created_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        ).scalars().all()
    return [
        {
            "run_id": r.id,
            "task_id": r.task_id,
            "query": r.query,
            "status": r.status,
            "synthesis_status": r.synthesis_status,
            "answer_kind": r.answer_kind,
            "summary": r.summary,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "durable_run": True,
        }
        for r in rows
    ]
