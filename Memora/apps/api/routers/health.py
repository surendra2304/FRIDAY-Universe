"""
Health Check Endpoints
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
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

@router.get("")
@router.head("")
def health_check(db: Session = Depends(get_db)):
    database = storage_receipt()
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"degraded ({type(e).__name__})"

    # The durable event feed is the same Oracle schema as the rest of Memora.
    event_store = "oracle_database" if database.get("backend") == "oracle" else "unavailable"
    event_store_ok = event_store == "oracle_database"

    vector_store = _active_vector_readiness()

    status_ok = db_status == "healthy" and event_store_ok and vector_store["available"]
    return JSONResponse(status_code=200 if status_ok else 503, content={
        "status": "healthy" if status_ok else "degraded",
        "service": "memora",
        "evidence_class": "process_liveness",
        "observed_at": datetime.now(timezone.utc).isoformat(),
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

