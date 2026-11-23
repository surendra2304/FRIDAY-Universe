import tempfile
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from intelx.core.metrics import get_metrics_payload
from intelx.core.settings import Settings, get_settings
from intelx.core.version import PROJECT_NAME, __version__
from intelx.db.session import check_database_health

router = APIRouter(tags=["Health & Telemetry"])


async def _probe_database() -> bool:
    """Live database round-trip (SELECT 1 / SELECT 1 FROM DUAL).

    Shared by /health and /readyz so both endpoints report the same
    database state. check_database_health() never raises: it returns
    False (and logs server-side) on failure, so no exception text can
    leak into a payload.
    """
    return await check_database_health()


async def _probe_storage(settings: Settings) -> bool:
    """Writable data-dir probe — the exact /readyz write test, shared by
    /health and /readyz so both endpoints report the same storage state."""
    try:
        data_dir = Path(settings.DATA_DIR)
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir, delete=True) as tf:
            tf.write(b"readyz_probe\n")
            tf.flush()
        return True
    except Exception:
        return False


def _provider_configured(settings: Settings) -> bool:
    """Model-provider configuration check, verbatim from /readyz.

    This does NOT probe upstream reachability; it only verifies that
    the selected live backend has the required endpoint/key. In
    MOCK_MODE the provider is a local mock, so the check passes
    trivially — exactly as /readyz has always treated it. The /health
    capability therefore reports model_provider as unknown /
    CONFIG_ONLY (design §2.2 rule 7), never as ok on config alone.
    """
    if settings.MOCK_MODE:
        return True
    if settings.LLM_PROVIDER in ("inference", "ai_universe", "aiuniverse"):
        return bool(settings.INFERENCE_URL and settings.INFERENCE_API_KEY)
    if settings.LLM_PROVIDER == "anthropic":
        return bool(settings.ANTHROPIC_API_KEY)
    if settings.LLM_PROVIDER in {
        "openai_compatible",
        "openai",
        "groq",
        "vllm",
        "ollama",
        "openrouter",
    }:
        return bool(settings.get_llm_api_key("openai_compatible"))
    return False


def _resolve_db_backend(settings: Settings) -> str:
    """Backend name for the readiness gate, verbatim from /readyz."""
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
    return db_backend


def _capability_report(
    settings: Settings,
    *,
    db_healthy: bool,
    storage_healthy: bool,
    provider_configured: bool,
) -> dict[str, Any]:
    """Build the REL-004 §2.2 capability report for /health (TASK-REL-067).

    Mapping (design §5, IntelX): capabilities.research (required; no
    live probe exists today, so unknown / NO_LIVE_PROBE — and degraded /
    MOCK_MODE in mock mode, because synthetic findings must never
    present as ok), capabilities.model_provider (required when not
    MOCK_MODE; config-only today, so unknown / CONFIG_ONLY per §2.2
    rule 7 — in MOCK_MODE unknown / MOCK_MODE, since there is no live
    provider to report); dependencies.database (required; the live
    check_database_health() round-trip, as /readyz does),
    dependencies.storage (required; the writable data-dir probe, as
    /readyz does). Top-level status is derived: ok iff every required
    entry is ok, else degraded (§2.2 rule 1). No detail key on ok
    entries; every non-ok entry carries a stable reason code (§2.2
    rule 5); no key, token, DSN or exception text appears anywhere
    (§2.2 rule 8).
    """
    observed_at = datetime.now(UTC).isoformat()
    if settings.MOCK_MODE:
        research = {
            "state": "degraded",
            "detail": "MOCK_MODE",
            "evidence": "mock mode: findings are synthetic; research cannot report ok",
        }
        model_provider = {
            "state": "unknown",
            "detail": "MOCK_MODE",
            "evidence": "provider is a local mock in MOCK_MODE; no live provider to report",
        }
    else:
        research = {
            "state": "unknown",
            "detail": "NO_LIVE_PROBE",
            "evidence": "no live research probe exists; research ability is not verified by this endpoint",
        }
        model_provider = {
            "state": "unknown",
            "detail": "CONFIG_ONLY",
            "evidence": (
                "provider config present; no live probe"
                if provider_configured
                else "provider key/endpoint missing; no live probe"
            ),
        }
    capabilities = {"research": research, "model_provider": model_provider}
    dependencies = {
        "database": (
            {
                "state": "ok",
                "evidence": "live check_database_health() round-trip (SELECT 1 / SELECT 1 FROM DUAL)",
            }
            if db_healthy
            else {
                "state": "unavailable",
                "detail": "DATABASE_UNREACHABLE",
                "evidence": "live check_database_health() round-trip failed",
            }
        ),
        "storage": (
            {
                "state": "ok",
                "evidence": "writable data-dir probe (tempfile write, as /readyz)",
            }
            if storage_healthy
            else {
                "state": "unavailable",
                "detail": "STORAGE_UNWRITABLE",
                "evidence": "writable data-dir probe failed (tempfile write, as /readyz)",
            }
        ),
    }
    required_ok = all(
        entry["state"] == "ok"
        for entry in list(capabilities.values()) + list(dependencies.values())
    )
    return {
        "status": "ok" if required_ok else "degraded",
        "evidence_class": "capability_report",
        "observed_at": observed_at,
        "service": PROJECT_NAME,
        "version": __version__,
        "mock_mode": settings.MOCK_MODE,
        # Legacy field, kept for consumers that read it: now the probed
        # value (as /readyz reports it), not "not_checked" — /health does
        # check the database. FRIDAY's ask_intelx reads /healthz, not
        # /health, so its display is unaffected.
        "database": "connected" if db_healthy else "unavailable",
        "capabilities": capabilities,
        "dependencies": dependencies,
        "timestamp": observed_at,
    }


@router.get("/healthz", summary="System Liveness Probe")
@router.head("/healthz", summary="System Liveness Probe")
async def healthz() -> dict[str, Any]:
    """Liveness probe: verifies process is running and accepting HTTP requests.

    Process-only by design (TASK-INT-012): this handler performs NO
    database work — no pool checkout, no query — so a liveness call
    never pays an Oracle round trip or a stale-pool reconnect.
    Dependency readiness (database, storage, provider) is reported
    by /readyz, unchanged, and the capability verdict by /health
    (TASK-REL-067; /health is a separate handler since this contract
    — the old /health alias of this liveness handler is removed).

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


@router.get("/health", summary="Health Capability Report")
@router.head("/health", summary="Health Capability Report")
async def health() -> JSONResponse:
    """Capability report per REL-004 §2.2 (TASK-REL-067).

    Answers "what can this agent actually do right now?": the §2.2
    capabilities + dependencies block with a derived top-level status
    (ok iff every required entry is ok, else degraded) and HTTP 200
    iff ok, else 503. Honest consequence, stated plainly: /health is
    degraded / 503 even with the database and storage ready, because
    research is required and has no live probe (unknown /
    NO_LIVE_PROBE; degraded / MOCK_MODE in mock mode). That is the
    contract's outcome (§2.4 forbids reclassifying a required
    capability as optional to get a green status); it clears only
    when a research probe is built. /readyz is unchanged in behaviour
    (same 200/503 gates and fields) and shares these probes, so
    /health can never contradict /ready (§2.5).
    """
    settings = get_settings()
    db_healthy = await _probe_database()
    storage_healthy = await _probe_storage(settings)
    provider_configured = _provider_configured(settings)
    payload = _capability_report(
        settings,
        db_healthy=db_healthy,
        storage_healthy=storage_healthy,
        provider_configured=provider_configured,
    )
    status_code = (
        status.HTTP_200_OK
        if payload["status"] == "ok"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/readyz", summary="Service Readiness Probe")
@router.head("/readyz", summary="Service Readiness Probe")
async def readyz() -> dict[str, Any]:
    """Readiness probe: verifies database connectivity, storage writeability, and provider readiness."""
    settings = get_settings()

    # 1. Database Connectivity Check
    db_healthy = await _probe_database()

    # 2. Local Storage Writable Check
    storage_healthy = await _probe_storage(settings)

    # 3. Model-provider configuration check. This does not probe upstream reachability;
    # it only verifies that the selected live backend has the required endpoint/key.
    provider_healthy = _provider_configured(settings)

    # Resolve the backend before any readiness decision that depends on it.
    db_backend = _resolve_db_backend(settings)

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
