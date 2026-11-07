"""
Health Check Endpoints
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.config import settings
from storage.relational.session import get_db, storage_receipt
from storage.vector.qdrant_adapter import vector_adapter

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
@router.head("")
def health_check(db: Session = Depends(get_db)):
    database = storage_receipt()
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"degraded ({type(e).__name__})"

    # Production event feeds use Oracle. Explicit testing mode reports the same
    # ephemeral SQLite database as a test-only event store; it is never durable
    # across the runner lifecycle and does not alter production backend rules.
    sqlite_test = (
        str(settings.MEMORA_ENV).lower() in {"test", "testing"}
        and database.get("backend") == "sqlite"
    )
    if database.get("backend") == "oracle":
        event_store = "oracle_database"
        event_store_ok = True
        vector_store = {"status": "available", "available": True, "backend": "oracle_23ai_native_vector"}
    else:
        event_store = "sqlite_test_database" if sqlite_test else "unavailable"
        event_store_ok = sqlite_test and db_status == "healthy"
        vector_store = vector_adapter.readiness()

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

    vector_store = vector_adapter.readiness()
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

