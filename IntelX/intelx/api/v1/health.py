import tempfile
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from intelx.core.metrics import get_metrics_payload
from intelx.core.settings import get_settings
from intelx.core.version import PROJECT_NAME, __version__
from intelx.db.session import check_database_health

router = APIRouter(tags=["Health & Telemetry"])


@router.get("/healthz", summary="System Liveness Probe")
@router.head("/healthz", summary="System Liveness Probe")
@router.get("/health", summary="System Liveness Probe Alias")
@router.head("/health", summary="System Liveness Probe Alias")
async def healthz() -> dict[str, Any]:
    """Liveness probe: verifies process is running and accepting HTTP requests.

    Process-only by design (TASK-INT-012): this handler performs NO
    database work — no pool checkout, no query — so a liveness call
    never pays an Oracle round trip or a stale-pool reconnect.
    Dependency readiness (database, storage, provider) is reported
    by /readyz, unchanged.

    The `database` field is retained because FRIDAY's fleet client
    (ask_intelx) reads it for display; it reports "not_checked" —
    this probe does not query the database, and the value must not
    be read as a database health signal. `status` reports process
    liveness only, per this endpoint's contract.
    """
    settings = get_settings()
    observed_at = datetime.now(UTC).isoformat()
    return {
        "status": "ok",
        "evidence_class": "process_liveness",
        "observed_at": observed_at,
        "service": PROJECT_NAME,
        "version": __version__,
        "mock_mode": settings.MOCK_MODE,
        "database": "not_checked",
        "timestamp": observed_at,
    }


@router.get("/readyz", summary="Service Readiness Probe")
@router.head("/readyz", summary="Service Readiness Probe")
async def readyz() -> dict[str, Any]:
    """Readiness probe: verifies database connectivity, storage writeability, and provider readiness."""
    settings = get_settings()

    # 1. Database Connectivity Check
    db_healthy = await check_database_health()

    # 2. Local Storage Writable Check
    storage_healthy = False
    try:
        data_dir = Path(settings.DATA_DIR)
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir, delete=True) as tf:
            tf.write(b"readyz_probe\n")
            tf.flush()
        storage_healthy = True
    except Exception:
        storage_healthy = False

    # 3. Model-provider configuration check. This does not probe upstream reachability;
    # it only verifies that the selected live backend has the required endpoint/key.
    provider_healthy = settings.MOCK_MODE
    if not settings.MOCK_MODE:
        if settings.LLM_PROVIDER in ("inference", "ai_universe", "aiuniverse"):
            provider_healthy = bool(settings.INFERENCE_URL and settings.INFERENCE_API_KEY)
        elif settings.LLM_PROVIDER == "anthropic":
            provider_healthy = bool(settings.ANTHROPIC_API_KEY)
        elif settings.LLM_PROVIDER in {
            "openai_compatible",
            "openai",
            "groq",
            "vllm",
            "ollama",
            "openrouter",
        }:
            provider_healthy = bool(settings.get_llm_api_key("openai_compatible"))

    # Resolve the backend before any readiness decision that depends on it.
    db_backend = "unconfigured"
    try:
        from intelx.db.engine import _engine

        if _engine is not None and hasattr(_engine, "dialect"):
            db_backend = str(getattr(_engine.dialect, "name", "unconfigured"))
    except Exception:
        pass
    if db_backend == "unconfigured":
        url = str(getattr(settings, "DB_URL", "")).lower()
        if "oracle" in url:
            db_backend = "oracle"
        else:
            db_backend = "unsupported"

    all_ready = db_healthy and storage_healthy and provider_healthy
    # INTELX runs on Oracle Autonomous Database; in production any other
    # backend is not ready.
    if db_backend != "oracle" and getattr(settings, "is_production", lambda: False)():
        all_ready = False

    payload = {
        "status": "ready" if all_ready else "not_ready",
        "evidence_class": "dependency_readiness",
        "observed_at": datetime.now(UTC).isoformat(),
        "ready": all_ready,
        "database": "connected" if db_healthy else "unavailable",
        "database_backend": db_backend,
        "storage": "ok" if storage_healthy else "error",
        "model_provider": (
            "mock"
            if settings.MOCK_MODE
            else ("configured" if provider_healthy else "misconfigured")
        ),
        "model_provider_check": "local_mock" if settings.MOCK_MODE else "configuration_only",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if not all_ready:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)

    return payload


@router.get("/metrics", summary="Prometheus Telemetry Metrics")
async def metrics() -> Response:
    """Expose Prometheus-formatted operational telemetry metrics."""
    content, content_type = get_metrics_payload()
    return Response(content=content, media_type=content_type)
