"""
Health Check Endpoints
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.resilience.circuit_breaker import circuit_registry
from storage.relational.session import get_db, storage_receipt
from storage.vector.oracle_vector_adapter import oracle_vector_adapter
from storage.vector.qdrant_adapter import vector_adapter

router = APIRouter(prefix="/health", tags=["Health"])


def _active_vector_readiness():
    """Readiness of the vector backend the write/read paths actually use.

    On the Oracle backend, embeddings live in the native 23ai vector table
    (write_service/search_service branch on ``is_oracle_backend()``), so the
    truthful signal is the Oracle adapter's readiness — which reports
    ``not_initialized`` until its schema bootstrap has actually run in this
    process. Reporting a hardcoded ``available: True`` here (the previous
    behaviour) claimed semantic search was healthy even when the vector
    table had never been initialised, and the Qdrant adapter's state —
    an unprovisioned in-memory mock — said nothing about the real path
    (TASK-REL-013).
    """
    if storage_receipt().get("backend") == "oracle":
        return oracle_vector_adapter.readiness()
    return vector_adapter.readiness()


def _capability(state, evidence, detail=None):
    """One REL-004 §2.2 capability/dependency entry.

    ``state`` is closed-vocabulary (ok / degraded / unavailable / unknown);
    ``detail`` is a stable machine-readable reason code, present exactly
    when the state is not ok. ``evidence`` names what was actually checked.
    """
    entry = {
        "state": state,
        "evidence": evidence,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if detail is not None:
        entry["detail"] = detail
    return entry


@router.get("")
@router.head("")
def health_check(db: Session = Depends(get_db)):
    observed_at = datetime.now(timezone.utc).isoformat()
    database = storage_receipt()
    db_status = "healthy"
    db_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"degraded ({type(e).__name__})"
        db_error = type(e).__name__

    # The durable event feed is the same Oracle schema as the rest of Memora.
    event_store = "oracle_database" if database.get("backend") == "oracle" else "unavailable"
    event_store_ok = event_store == "oracle_database"

    vector_store = _active_vector_readiness()
    vector_ok = bool(vector_store.get("available", False))
    vector_status = vector_store.get("status", "unknown")

    # Circuit breakers live in /ready already; the contract requires them
    # in /health too (design §5). An open breaker degrades /health: the
    # dependency is protected, not serving.
    circuits_ok = circuit_registry.healthy()
    open_circuits = sorted(
        name
        for name, snap in circuit_registry.snapshot().items()
        if isinstance(snap, dict) and snap.get("state") == "open"
    )

    db_ok = db_status == "healthy"
    vector_detail = None
    if not vector_ok:
        vector_detail = (
            "VECTOR_STORE_NOT_INITIALIZED"
            if vector_status == "not_initialized"
            else "VECTOR_STORE_UNAVAILABLE"
        )
    vector_evidence = (
        f"vector backend {vector_store.get('backend', 'unknown')}: {vector_status}"
    )

    capabilities = {
        "memory_store": _capability(
            "ok" if db_ok else "unavailable",
            "SELECT 1 succeeded" if db_ok else f"SELECT 1 failed ({db_error})",
            None if db_ok else "DATABASE_UNREACHABLE",
        ),
        "event_store": _capability(
            "ok" if event_store_ok else "unavailable",
            "oracle backend"
            if event_store_ok
            else f"backend {database.get('backend', 'uninitialized')} is not oracle",
            None if event_store_ok else "EVENT_STORE_UNAVAILABLE",
        ),
        "vector_search": _capability(
            "ok" if vector_ok else "unavailable",
            vector_evidence,
            vector_detail,
        ),
    }
    dependencies = {
        "database": _capability(
            "ok" if db_ok else "unavailable",
            "SELECT 1 succeeded" if db_ok else f"SELECT 1 failed ({db_error})",
            None if db_ok else "DATABASE_UNREACHABLE",
        ),
        "vector_store": _capability(
            "ok" if vector_ok else "unavailable",
            vector_evidence,
            vector_detail,
        ),
        "circuit_breakers": _capability(
            "ok" if circuits_ok else "degraded",
            "no circuit breaker open"
            if circuits_ok
            else f"circuit breaker(s) open: {', '.join(open_circuits) if open_circuits else 'unknown'}",
            None if circuits_ok else "CIRCUIT_BREAKER_OPEN",
        ),
    }

    # REL-004 §2.2 rule 1: status is derived — ok iff every required
    # capability and dependency is ok. All six entries above are required.
    # The top-level value moves from "healthy" to "ok": the contract's
    # closed vocabulary (§2.2). HTTP behaviour is unchanged: 200 iff ok,
    # else 503, as this handler already did.
    status_ok = db_ok and event_store_ok and vector_ok and circuits_ok
    return JSONResponse(status_code=200 if status_ok else 503, content={
        "status": "ok" if status_ok else "degraded",
        "service": "memora",
        "evidence_class": "capability_report",
        "observed_at": observed_at,
        "capabilities": capabilities,
        "dependencies": dependencies,
        "storage": database.get("backend", "uninitialized"),
        "database": db_status,
        "database_backend": database["backend"],
        "database_durable": database["durable"],
        "database_durability": database["durability"],
        "event_store": event_store,
        "event_store_durable": event_store == "oracle_database",
        "vector_store": vector_store,
        "version": "2.0.0"
    })


@router.get("/ready")
@router.head("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Dedicated readiness probe verifying the Oracle database and vector availability."""
    database = storage_receipt()
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"degraded ({type(e).__name__})"

    vector_store = _active_vector_readiness()
    from core.resilience.circuit_breaker import circuit_registry
    circuits_ok = circuit_registry.healthy()

    ready = (db_status == "healthy") and vector_store.get("available", False)
    status_code = 200 if ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if ready else "unready",
            "service": "memora",
            "version": "2.0.0",
            "database": db_status,
            "database_backend": database["backend"],
            "vector_store": vector_store.get("status", "unknown"),
            "circuits": "healthy" if circuits_ok else "degraded",
            "evidence_class": "readiness_probe",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

