"""
FORGE Application Entry Point.
FastAPI initialization with lifespan lifecycle management, middleware, and routers.
"""

import asyncio
import hmac
import sys
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api.analytics import analytics_router
from app.api.delegate import delegate_router
from app.api.health import health_router
from app.api.improvement import improvement_router
from app.api.marketplace import marketplace_router, task_template_router
from app.api.routes import router as api_router
from app.api.automated_testing import router as automated_testing_router
from app.api.code_intelligence import router as code_intelligence_router
from app.api.synthesis_routes import pipeline_router, synthesis_router
from app.api.autonomous_code_repair import router as code_repair_router
from app.api.quantum_flow_optimizer import router as quantum_optimizer_router
from app.api.realtime_collaboration import router as collaboration_router
from app.api.distributed_dev_environment import router as dev_env_router
from app.api.code_review_router import router as code_review_router
from app.api.deployment_pipeline_manager import router as deployment_router
from app.api.tasks import tasks_router
from app.api.websocket import ws_router
from app.config.production import production_settings
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.dashboard.routes import dashboard_router
from app.memory.db import db_manager
from app.monitoring.production_monitor import production_monitor
from app.optimization.performance import performance_optimizer
from app.streaming.routes import streaming_router

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler."""
    settings = get_settings()
    setup_logging(debug=settings.debug)
    logger.info(f"Starting {settings.app_name} v{settings.app_version} ({settings.env})")

    # Ensure runtime directories exist
    settings.ensure_directories()

    # Initialize SQLite database schema and optimize PRAGMAs
    await db_manager.init_db()
    await performance_optimizer.optimize_sqlite_pragmas(db_manager)
    logger.info("Database schemas initialized and performance PRAGMAs tuned.")

    # Signal trapping for graceful shutdown in Unix/Linux container environments
    if sys.platform != "win32":
        import signal

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: logger.info(f"Received signal {s}. Triggering graceful shutdown..."),
                )
            except (NotImplementedError, RuntimeError):
                pass

    yield

    logger.info(f"Shutting down {settings.app_name}...")
    # Safe cleanup of in-flight execution sandboxes within 5 seconds
    try:
        from app.execution.engine import execution_engine

        logger.info("Halting all in-flight sandbox execution processes (5s grace period)...")
        await asyncio.wait_for(
            execution_engine.terminate_all_sandboxes(timeout=4.0),
            timeout=5.0,
        )
        logger.info("All in-flight sandboxes cleanly halted.")
    except Exception as e:
        logger.warning(f"Sandbox cleanup notice: {e}")



# Largest accepted request body (8 MB). Guards the worker against unbounded
# buffering of hostile payloads.
MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024


def _unique_operation_id(route: APIRoute) -> str:
    """Build a deterministic, path-aware OpenAPI operationId.

    Several routers are mounted at more than one prefix ("", /api, /api/v1).
    FastAPI derives operationId from the endpoint function name alone, so every
    multi-mounted endpoint emitted a duplicate operationId -- which violates the
    OpenAPI spec and breaks strict client generators. Folding the full path into
    the id makes each mount unique.
    """
    raw = f"{route.name}_{route.path_format}"
    return "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in raw)


def _dedupe_operation_ids(schema: dict[str, Any]) -> dict[str, Any]:
    """Guarantee operationId uniqueness across (path, method) pairs.

    FastAPI reuses a single `route.unique_id` for every HTTP method declared on a
    route, so any route registered with methods=["GET", "HEAD"] emits two
    operations sharing one operationId. The OpenAPI spec requires operationId to
    be unique, so disambiguate the leftovers by method.
    """
    seen: set[str] = set()
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in list(path_item.items()):
            if not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId")
            if not op_id:
                continue
            candidate = op_id
            suffix = 2
            while candidate in seen:
                candidate = f"{op_id}_{method}_{suffix}"
                suffix += 1
            operation["operationId"] = candidate
            seen.add(candidate)
    return schema


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FORGE: Autonomous Software Engineering Engine for goal-driven software synthesis and verification.",
        lifespan=lifespan,
        generate_unique_id_function=_unique_operation_id,
    )

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        with warnings.catch_warnings():
            # FastAPI warns for every id it sees twice *during* generation; the
            # schema returned below is already de-duplicated, so the warning is
            # pure noise on /openapi.json and in the logs.
            warnings.filterwarnings("ignore", message="Duplicate Operation ID")
            schema = get_openapi(
                title=settings.app_name,
                version=settings.app_version,
                description=app.description,
                routes=app.routes,
            )
        app.openapi_schema = _dedupe_operation_ids(schema)
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    @app.middleware("http")
    async def require_production_api_key(request: Request, call_next):
        """Protect data APIs while allowing the credential-free dashboard shell to load.

        Gating used to be based purely on `production_settings.env ==
        PRODUCTION`, which completely ignored the dedicated
        `api_key_required` setting (driven by the `API_KEY_REQUIRED` env
        var). That meant the operator-facing escape hatch for running a
        trusted/internal production deployment without API key enforcement
        was silently unusable: `docker-compose.yml` ships with
        `FORGE_ENV=production` + `API_KEY_REQUIRED=false` (and no
        `FORGE_API_KEY` configured, since none was meant to be required) --
        with the old logic, every request to `/api/*` after `docker compose
        up` returned 503 "service_auth_unconfigured" regardless of the
        explicit opt-out, locking operators out of their own fresh install.
        `api_key_required` is the single dedicated setting for "should this
        deployment enforce an API key" (and itself already defaults to True
        whenever FORGE_ENV=production and no explicit override is given), so
        it alone -- not a second, conflicting check against `env` -- should
        decide whether this gate runs at all.
        """
        from app.config.production import production_settings

        if not production_settings.api_key_required:
            return await call_next(request)
        # Keep the /api spellings in sync with the bare ones, otherwise the
        # duplicate mounts make the auth-exempt set prefix-dependent.
        if request.url.path in {
            "/health", "/health/ready", "/ready", "/status", "/metrics", "/docs", "/redoc", "/openapi.json",
            "/api/health", "/api/health/ready", "/api/ready", "/api/status", "/api/metrics", "/api/openapi.json",
        } or request.url.path.startswith("/static/"):
            return await call_next(request)
        if request.method in {"GET", "HEAD"} and request.url.path in {"/", "/dashboard"}:
            return await call_next(request)

        configured_key = production_settings.forge_api_key or ""
        if len(configured_key) < 32 or configured_key.lower() in {
            "forge_api", "change-me", "changeme", "password", "secret",
        }:
            return JSONResponse(
                status_code=503,
                content={"error": "service_auth_unconfigured", "detail": "A unique FORGE_API_KEY is required."},
            )

        provided_key = request.headers.get("X-API-Key", "")
        authorization = request.headers.get("Authorization", "")
        if not provided_key and authorization.lower().startswith("bearer "):
            provided_key = authorization[7:].strip()
        if not provided_key:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})

        # Accept either the calling agent's credential, which is how the rest of the
        # mesh authenticates, or Forge's own key for direct operator access. Previously
        # only Forge's own key was accepted, so no peer could ever call Forge and every
        # FRIDAY->Forge delegation was rejected with 403.
        caller_key = production_settings.friday_api_key or ""
        accepted = [configured_key]
        if len(caller_key) >= 32:
            accepted.append(caller_key)
        if not any(hmac.compare_digest(provided_key.encode(), key.encode()) for key in accepted):
            return JSONResponse(status_code=403, content={"error": "forbidden"})
        return await call_next(request)

    @app.middleware("http")
    async def enforce_rate_limit(request: Request, call_next):
        """Apply the sliding-window rate limiter to API traffic.

        `RateLimiter` (app/security/api_keys.py) was a fully implemented,
        tested-in-isolation sliding-window limiter with hourly and
        per-minute burst thresholds -- but it, and the `verify_api_key`
        FastAPI dependency built around it, were never attached to any
        route or middleware anywhere in the application. No request has
        ever actually been rate limited, regardless of
        `rate_limit_enabled`/`default_rate_limit` configuration. This wires
        the existing limiter in for real, scoped to `/api/*` traffic and
        gated by `rate_limit_enabled` (which itself defaults to "on in
        production, off elsewhere" so the dev/test experience and existing
        test suite's rapid-fire request patterns are unaffected unless an
        operator explicitly opts in via RATE_LIMIT_ENABLED).
        """
        from app.config.production import production_settings
        from app.security.api_keys import rate_limiter

        if not production_settings.rate_limit_enabled or not request.url.path.startswith("/api/"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            authorization = request.headers.get("Authorization", "")
            if authorization.lower().startswith("bearer "):
                api_key = authorization[7:].strip()
        client_identifier = api_key or (request.client.host if request.client else "anonymous")

        if not rate_limiter.is_allowed(client_identifier):
            logger.warning(f"Rate limit exceeded for client '{client_identifier[:8]}...'")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "detail": "Rate limit exceeded. Please retry later.",
                },
            )
        return await call_next(request)

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        """Reject oversized bodies early instead of buffering them into memory.

        A 10 MB goal used to be read in full before any validation ran, which
        pinned the worker's memory and surfaced as a client ReadTimeout rather
        than a clean 413.
        """
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > MAX_REQUEST_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "payload_too_large",
                            "detail": f"Request body exceeds {MAX_REQUEST_BODY_BYTES} bytes.",
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)

    @app.middleware("http")
    async def record_request_telemetry(request: Request, call_next):
        """Feed the production monitor.

        ProductionMonitor.record_request had no callers anywhere in the codebase,
        so /metrics always exported forge_requests_total 0 and the error-rate
        alert in check_alerts() could never fire.
        """
        response = await call_next(request)
        try:
            production_monitor.record_request(
                request.url.path, is_error=response.status_code >= 400
            )
        except Exception:  # telemetry must never break a request
            logger.debug("Failed to record request telemetry", exc_info=True)
        return response

    # Configure CORS with explicit whitelist
    cors_whitelist = [
        "https://friday-universe.duckdns.org",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8002",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    for origin in production_settings.cors_origins:
        if origin and origin not in cors_whitelist:
            cors_whitelist.append(origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_whitelist,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Apply GZip compression for responses > 1KB
    performance_optimizer.apply_fastapi_optimizations(app)

    # Register API routers
    app.include_router(health_router, tags=["Health & Diagnostics"])
    # Health/metrics under /api too: the dashboard and docs/API_REFERENCE.md use
    # the /api prefix, so /api/metrics and /api/health/ready 404'd while their
    # bare equivalents worked.
    app.include_router(health_router, prefix="/api", tags=["Health & Diagnostics"])
    app.include_router(api_router, tags=["Core API"])
    app.include_router(api_router, prefix="/api/v1", tags=["API v1"])
    app.include_router(tasks_router, prefix="/api/v1", tags=["Tasks v1"])
    app.include_router(code_repair_router, prefix="/api/v1/forge")
    app.include_router(quantum_optimizer_router, prefix="/api/v1/forge/quantum")
    app.include_router(collaboration_router, prefix="/api/v1/forge/collab")
    app.include_router(dev_env_router, prefix="/api/v1/forge/dev-env")
    app.include_router(code_review_router)
    app.include_router(deployment_router)

    # /api is the prefix the dashboard and docs/API_REFERENCE.md actually use.
    # Without a core-router mount here every endpoint only api_router owns
    # (timeline, pause, resume, artifacts metadata, projects) 404'd under /api,
    # leaving the dashboard's Timeline tab and lifecycle buttons dead.
    #
    # api_router and tasks_router overlap on POST /tasks, GET /tasks/{id} and
    # POST /tasks/{id}/cancel. FastAPI resolves routes in registration order, so
    # tasks_router is mounted first under /api to preserve the established /api
    # contract (it is the richer handler: artifacts, logs, inspect, archive) and
    # api_router only supplies the paths tasks_router does not implement.
    app.include_router(tasks_router, prefix="/api", tags=["Tasks"])
    app.include_router(api_router, prefix="/api", tags=["Core API"])
    app.include_router(delegate_router, prefix="/api/v1", tags=["FRIDAY Universe Forge Delegation"])
    app.include_router(analytics_router, prefix="/api", tags=["Analytics"])
    app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics v1"])
    app.include_router(improvement_router, prefix="/api", tags=["Self-Improvement"])
    app.include_router(improvement_router, prefix="/api/v1", tags=["Self-Improvement v1"])
    app.include_router(marketplace_router, tags=["Marketplace"])
    app.include_router(task_template_router, tags=["Tasks"])
    app.include_router(synthesis_router, tags=["Synthesis & Refactoring"])
    app.include_router(pipeline_router, tags=["Pipeline Events"])
    app.include_router(ws_router, tags=["WebSockets"])
    app.include_router(streaming_router, tags=["WebSocket Streaming Gateway"])
    app.include_router(dashboard_router, tags=["Web Dashboard"])
    app.include_router(automated_testing_router, prefix="/api/v1", tags=["Automated Testing v1"])
    app.include_router(automated_testing_router, prefix="/api", tags=["Automated Testing"])
    app.include_router(code_intelligence_router, prefix="/api/v1", tags=["Code Intelligence v1"])
    app.include_router(code_intelligence_router, prefix="/api", tags=["Code Intelligence"])

    # --- Test Generation Engine Integration ---
    from app.services.test_generation_engine import router as test_gen_router
    app.include_router(test_gen_router, prefix="/api/v1/forge", tags=["Test Generation"])

    # --- Code Refactoring Engine Integration ---
    from app.services.code_refactoring_engine import router as refactor_router
    app.include_router(refactor_router, prefix="/api/v1/forge", tags=["Code Refactoring"])

    # --- Dependency Analyzer Integration ---
    from app.services.dependency_analyzer import router as dep_analyzer_router
    app.include_router(dep_analyzer_router, prefix="/api/v1/forge", tags=["Dependency Analysis"])

    # --- Performance Profiler Integration ---
    from app.services.performance_profiler import router as perf_profiler_router
    app.include_router(perf_profiler_router, prefix="/api/v1/forge", tags=["Performance Profiling"])

    # --- Code Analysis Engine Integration ---
    from app.services.code_analysis_engine import router as code_analysis_router
    app.include_router(code_analysis_router, prefix="/api/v1/forge", tags=["Code Analysis"])

    # --- Build Pipeline Manager Integration ---
    from app.services.build_pipeline_manager import router as build_pipeline_router
    app.include_router(build_pipeline_router, prefix="/api/v1/forge", tags=["Build Pipeline"])

    # --- Test Coverage Analyzer Integration ---
    from app.services.test_coverage_analyzer import router as test_coverage_router
    app.include_router(test_coverage_router, prefix="/api/v1/forge", tags=["Test Coverage"])

    # --- Code Architecture Analyzer Integration ---
    from app.services.code_architecture_analyzer import router as arch_analyzer_router
    app.include_router(arch_analyzer_router, prefix="/api/v1/forge", tags=["Architecture Analysis"])

    # --- Code Merge Conflict Resolver Integration ---
    from app.services.code_merge_conflict_resolver import router as merge_resolver_router
    app.include_router(merge_resolver_router, prefix="/api/v1/forge", tags=["Merge Conflict Resolver"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


# --- Autonomous Software Synthesizer Integration ---

@app.post("/api/v1/synthesize", tags=["Autonomous Synthesis"])
async def autonomous_synthesize(
    description: str,
    language: str = "python",
    test_coverage: bool = True,
    security_check: bool = True,
):
    """Autonomously synthesize software from a description."""
    from app.agents.autonomous_synthesizer import autonomous_synthesizer, SynthesisRequest
    try:
        request = SynthesisRequest(
            description=description,
            language=language,
            test_coverage=test_coverage,
            security_check=security_check,
        )
        result = await autonomous_synthesizer.synthesize(request)
        return {
            "success": result.success,
            "files_created": result.files_created,
            "tests_created": result.tests_created,
            "verification_passed": result.verification_passed,
            "errors": result.errors,
            "warnings": result.warnings,
            "iterations": result.iterations,
        }
    except Exception as exc:
        raise HTTPException(500, f"Synthesis failed: {exc}")


@app.post("/api/v1/synthesize/multi-language", tags=["Autonomous Synthesis"])
async def autonomous_synthesize_multi_language(
    description: str,
    languages: list[str] = ["python", "javascript", "typescript"],
):
    """Synthesize software in multiple languages simultaneously."""
    from app.agents.autonomous_synthesizer import autonomous_synthesizer, SynthesisRequest
    results = {}
    for lang in languages:
        try:
            request = SynthesisRequest(description=description, language=lang)
            result = await autonomous_synthesizer.synthesize(request)
            results[lang] = {
                "success": result.success,
                "files": result.files_created,
                "iterations": result.iterations,
            }
        except Exception as exc:
            results[lang] = {"error": str(exc)}
    return {"languages": languages, "results": results}
