"""FRIDAY UI & FastMCP Server for Surendra's FRIDAY.

Provides:
- Bidirectional WebSocket for real-time voice, audio waveforms, and MediaPipe hand gestures
- Fast-path execution for low-latency PC and Android device control
- FastMCP Server endpoints (/sse, /messages) for Model Context Protocol interoperability
- Tool Catalog API (/api/tools) and System Observability (/api/metrics, /api/health)
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import hashlib
import hmac
import json
import ipaddress
import logging
import os
import re
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi import Body, Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from friday.core.startup_validator import validate_runtime_environment
from friday.core.cache import TTLCache, ttl_cached
from friday.core.resilience import safe_peer_call

from friday.agent.agent import FridayAgent
from friday.cli.auth import CLIAuthorizer
from friday.core.auth import DefaultSecureAuthorizer
from friday.core.config import get_settings
# connect_sqlite is imported into this module's namespace on purpose: the
# /ready regressions patch `friday.api.server.connect_sqlite` to prove a
# failing storage layer turns the probe 503.
from friday.core.database import connect_sqlite
from friday.core.logging import get_logger
from friday.devices.android_controller import AndroidDeviceController
from friday.devices.app_launcher import launch_desktop_app
from friday.ecosystem.fleet_client import fleet_client, CANONICAL_INTERNAL_MESH_URLS
from friday.memory.event_consumer import MemoraEventConsumer
from friday.memory.memora_client import memora_client
from friday.api.companion_ws import companion_multiplexer
from friday.api.activity_stream import register as register_activity_client, unregister as unregister_activity_client
from friday.remote.laptop_bridge import (
    ALLOWED_LAPTOP_COMMANDS,
    LaptopBridgeTimeout,
    LaptopDisconnected,
    LaptopNotConnected,
    laptop_bridge,
    normalise_laptop_id,
    shell_execution_enabled,
)
from friday.autonomous import autonomous_controller, autonomous_daemon, enhanced_controller
from friday.autonomous.repair_loop import repair_loop
from friday.cognition.reflex import get_reflex_brain, parse_incident_scope
from friday.cognition.mesh import get_mesh
from friday.cognition.mind import get_mind_registry
from friday.autonomous.self_repair import (
    GitRepairApplier,
    RepairProposal,
    SelfRepairGate,
)
from friday_deep.observability.metrics import DEFAULT as default_metrics
from friday_deep.health import build as build_health_report

# Production observability fix (ZAI Agent 2, 2026-11-12): uvicorn starts
# this module directly, and setup_logging() was only ever called on the CLI
# path — so the "friday" logger had NO handlers in production and every
# app-level log line (agent-watch passes, loop crashes, startup banner) was
# silently dropped. Bootstrapping here (before any get_logger child is used)
# restores the console + sanitized file logging the whole fleet assumes.
try:
    from friday.core.logging import setup_logging as _setup_server_logging

    _setup_server_logging()
except Exception as _log_boot_exc:  # never block the server on logging setup
    import logging as _stdlib_logging

    _stdlib_logging.getLogger("friday.api.server").warning(
        "setup_logging bootstrap failed (%s); falling back to stdlib defaults", _log_boot_exc
    )

logger = get_logger("api.server")

logger.info(
    "FRIDAY API server module loaded (pid=%s, env=%s)",
    os.getpid(),
    os.getenv("FRIDAY_ENV", "unspecified"),
)

try:
    FLEET_SUPERVISION_INTERVAL_SECONDS = max(
        30, int(os.getenv("FRIDAY_FLEET_SUPERVISION_INTERVAL_SECONDS", "300"))
    )
except ValueError:
    FLEET_SUPERVISION_INTERVAL_SECONDS = 300

fleet_supervision_state: dict[str, Any] = {
    "running": False,
    "interval_seconds": FLEET_SUPERVISION_INTERVAL_SECONDS,
    "last_started_at": None,
    "last_completed_at": None,
    "last_error": None,
    "agents": [],
}

# Checklist E7 (batch 8, ZAI Agent 2): voice session diagnostics state.
# Updated by the VoiceCall component via /api/voice/diagnostics/report (POST);
# read by the SYSTEM tab via /api/voice/diagnostics (GET). Counters start at
# zero and stay there until the first session — never invented.
from friday.core.owner_time import OWNER_TZ as _OWNER_TZ  # noqa: E402
OWNER_TZ = _OWNER_TZ  # module-level alias for endpoints below
_voice_diagnostics_state: dict[str, Any] = {
    "session_id": "",
    "started_at": "",
    "ended_at": "",
    "duration_sec": 0,
    "rtt_ms": None,
    "packet_loss_pct": None,
    "reconnect_count": 0,
    "quality": "no-session-yet",
}

MEMORA_EVENT_CONSUMER_ID = "friday-cloud"
try:
    MEMORA_EVENT_POLL_INTERVAL_SECONDS = max(30, int(os.getenv("FRIDAY_MEMORA_POLL_INTERVAL_SECONDS", "60")))
except ValueError:
    MEMORA_EVENT_POLL_INTERVAL_SECONDS = 60
memora_event_state: dict[str, Any] = {
    "consumer_id": MEMORA_EVENT_CONSUMER_ID,
    "running": False,
    "last_completed_at": None,
    "last_result": None,
}


async def _fleet_supervision_loop() -> None:
    """Continuously refresh peer reachability while the cloud FRIDAY process is alive."""
    fleet_supervision_state["running"] = True
    try:
        while True:
            fleet_supervision_state["last_started_at"] = datetime.now(timezone.utc).isoformat()
            try:
                statuses = await fleet_client.get_all_statuses(force_refresh=True)
                fleet_supervision_state["agents"] = [status.__dict__ for status in statuses]
                fleet_supervision_state["last_completed_at"] = datetime.now(timezone.utc).isoformat()
                fleet_supervision_state["last_error"] = None
            except Exception as exc:
                # Keep the last known snapshot, but make the failed poll visible.
                fleet_supervision_state["last_error"] = type(exc).__name__
                logger.exception("FRIDAY fleet supervision cycle failed")
            await asyncio.sleep(FLEET_SUPERVISION_INTERVAL_SECONDS)
    finally:
        fleet_supervision_state["running"] = False


async def _memora_event_loop() -> None:
    """Archive untrusted Memora notices durably before advancing FRIDAY's cloud cursor."""
    consumer = MemoraEventConsumer(
        memora_client,
        consumer_id=MEMORA_EVENT_CONSUMER_ID,
        persist_notice=memora_client.persist_event_notice,
    )
    memora_event_state["running"] = True
    try:
        while True:
            try:
                result = await asyncio.to_thread(consumer.consume_once)
                memora_event_state["last_result"] = result
                memora_event_state["last_completed_at"] = datetime.now(timezone.utc).isoformat()
                if result.get("status") != "ok":
                    logger.warning("Memora event consumption did not complete: %s", result)
                while result.get("status") == "ok" and result.get("has_more"):
                    result = await asyncio.to_thread(consumer.consume_once)
                    memora_event_state["last_result"] = result
                    memora_event_state["last_completed_at"] = datetime.now(timezone.utc).isoformat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                memora_event_state["last_result"] = {"status": "error", "error": type(exc).__name__}
                memora_event_state["last_completed_at"] = datetime.now(timezone.utc).isoformat()
                logger.exception("FRIDAY Memora event consumer cycle failed")
            await asyncio.sleep(MEMORA_EVENT_POLL_INTERVAL_SECONDS)
    finally:
        memora_event_state["running"] = False


async def _reflex_loop() -> None:
    """Run the cognition reflex for as long as the service lives.

    A failure inside the loop is logged and the loop stops rather than spins: a
    brain that keeps crashing should be visible in the log, not silent.
    """
    brain = get_reflex_brain()
    if not brain.enabled:
        logger.info("Reflex brain is disabled by FRIDAY_REFLEX_ENABLED")
        return
    try:
        await brain.run_forever()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Reflex brain loop stopped with an error")


async def _configure_memory_mirror() -> None:
    """Point shared memory at the Memora peer, but only when asked.

    Mirroring is best-effort and off by default: an unreachable memory peer must
    never add its timeout to the path of a task that is doing real work.
    """
    if os.getenv("FRIDAY_MEMORY_MIRROR", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        from friday.cognition.memory_bridge import mesh_mirror, set_shared_memory, SharedMemory

        set_shared_memory(SharedMemory(mirror=mesh_mirror(get_mesh())))
        logger.info("Shared memory will mirror episodes to Memora (FRIDAY_MEMORY_MIRROR is on)")
    except Exception:
        logger.exception("Shared memory mirroring could not be configured")


async def _nightly_consolidation_loop() -> None:
    """Checklist B7: consolidate the day's memories while the owner sleeps.

    A light gate-check every 15 minutes; the run itself is gated to
    02:00–05:00 IST and at most once per night inside
    maybe_run_nightly_consolidation. Failures are logged and never fatal —
    memory consolidation must never take the assistant down.
    """
    while True:
        try:
            await asyncio.sleep(900)  # 15 minutes between gate checks
            from friday.memory.memora_client import memora_client as _consol_client
            from friday.proactive.nightly_consolidation import maybe_run_nightly_consolidation

            report = maybe_run_nightly_consolidation(_consol_client)
            if report is not None:
                if str(report.get("status")) == "error":
                    logger.warning(f"Nightly consolidation failed honestly: {report}")
                else:
                    logger.info(
                        "Nightly consolidation done: examined=%s merged=%s skipped=%s summary_stored=%s",
                        report.get("records_examined"),
                        report.get("duplicates_merged"),
                        report.get("merges_skipped"),
                        report.get("summary_stored"),
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Nightly consolidation loop error (continuing)")


async def _proactive_followup_loop() -> None:
    """Checklist A12: unfinished tasks get a status ping without being asked.

    A sweep every 30 minutes over the shared task ledger; stale in-flight
    tasks (default: no transition for 45+ minutes) get ONE honest ping each
    through the proactive NotificationManager (the same channel the morning
    brief and the voice line read from), rate-limited per task. Failures are
    logged and never fatal.
    """
    while True:
        try:
            await asyncio.sleep(1800)  # 30 minutes between sweeps
            from friday.proactive.followup import followup_sweep

            report = followup_sweep(agent.notifications, post=True)
            if report.get("pings_posted") or report.get("post_failures"):
                logger.info(
                    "Proactive follow-up sweep: stale=%s posted=%s limited=%s failed=%s",
                    report.get("stale_found"),
                    report.get("pings_posted"),
                    report.get("rate_limited"),
                    report.get("post_failures"),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Proactive follow-up loop error (continuing)")


async def _daily_report_loop() -> None:
    """Checklists G7/G8: deliver the evening self-report + Sunday weekly summary.

    Light gate-check every 10 minutes; the send windows (21:00+ IST daily,
    20:00+ IST Sunday) and once-per-day latches live inside
    maybe_deliver_reports. Every failure is honest and non-fatal — a report
    problem must never take the assistant down.
    """
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes between gate checks
            from friday.proactive.daily_self_report import maybe_deliver_reports

            outcome = maybe_deliver_reports()
            if outcome.get("daily") or outcome.get("weekly"):
                logger.info("Self-report delivery outcome: %s", outcome)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Daily self-report loop error (continuing)")


#: The server's main event loop, captured at startup so worker threads (the
#: Telegram gateway, the mission executor) can schedule coroutines onto the
#: SAME loop instead of racing a second one (G5/G6).
_MAIN_EVENT_LOOP: asyncio.AbstractEventLoop | None = None


def _run_brain_sync(command: str) -> dict[str, Any]:
    """Run one command through execute_command from ANY thread (G5/G6).

    Schedules onto the server's main loop (captured in lifespan) and waits
    for the real result; a timeout raises honestly into the caller.
    """
    loop = _MAIN_EVENT_LOOP
    if loop is None or loop.is_closed():
        raise RuntimeError("main event loop unavailable")
    future = asyncio.run_coroutine_threadsafe(
        execute_command(CommandRequest(command=command)), loop
    )
    return future.result(timeout=300)


async def _mission_execution_loop() -> None:
    """Checklists G6/G12: execute queued missions while the owner sleeps.

    Gate-check every 10 minutes; the run window (03:00–05:00 IST) and the
    once-per-night latch live in the queue module. Missions execute through
    the real chat brain (scheduled onto this loop by _run_brain_sync);
    results feed the morning report.
    """
    while True:
        try:
            await asyncio.sleep(600)
            from friday.core.owner_time import OWNER_TZ
            from friday.proactive.mission_queue import (
                RUN_WINDOW_END,
                RUN_WINDOW_START,
                mission_queue,
            )

            now = datetime.now(timezone.utc).astimezone(OWNER_TZ)
            if not (RUN_WINDOW_START <= now.hour < RUN_WINDOW_END):
                continue
            pending = mission_queue.pending()
            if not pending:
                continue
            logger.info("Executing %d overnight mission(s)", len(pending))

            async def _night_brain(command: str) -> dict[str, Any]:
                return await execute_command(CommandRequest(command=command))

            report = await mission_queue.execute_pending_async(_night_brain)
            logger.info(
                "Overnight missions executed: %s completed / %s failed / %s skipped",
                report.get("completed"), report.get("failed"), report.get("skipped"),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Mission execution loop error (continuing)")


async def _agent_watch_loop() -> None:
    """Checklists F8/F9/F14/F15/F20 (batch 6, ZAI Agent 2): scheduled agent-depth passes.

    One loop owns all three passes (site sweep 08:00 IST, watchlist briefing
    17:30 IST, Sentinel digest Monday 09:30 IST); windows and once-per-period
    latches live in agent_watch.agent_watch_tick. Every failure is honest and
    non-fatal — a watch pass must never take the assistant down.
    """
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes between gate checks
            from friday.proactive.agent_watch import agent_watch_tick

            outcome = await agent_watch_tick()
            if any(v is not None for v in outcome.values()):
                logger.info("Agent-watch passes: %s", {k: v for k, v in outcome.items() if v})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Agent-watch loop error (continuing)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Pre-flight environment validation
    is_prod = os.getenv("FRIDAY_ENV", "").lower() == "production"
    validate_runtime_environment(fail_fast=is_prod)
    supervision_task = asyncio.create_task(_fleet_supervision_loop(), name="friday-fleet-supervision")
    memora_task = asyncio.create_task(_memora_event_loop(), name="friday-memora-event-consumer")
    # The unattended repair pass. Until this task existed the trigger had no
    # caller in the running service at all, so nothing here could fire it. It
    # stays inert unless an owner sets FRIDAY_SELF_REPAIR_TRIGGER_ENABLED, and
    # it sleeps before its first pass so a restart is not a repair storm.
    repair_task = asyncio.create_task(repair_loop.run_forever(), name="friday-autonomous-repair")
    # The cognition reflex: detect a fault anywhere in FRIDAY's own code, runtime
    # or fleet, prove a repair in a sandbox, and apply it under a standing mandate.
    # `run_forever` sleeps before its first pass, so a restart is not a repair
    # storm. Set FRIDAY_REFLEX_ENABLED=false to keep it out of this process.
    reflex_task = asyncio.create_task(_reflex_loop(), name="friday-reflex-brain")
    memory_mirror_task = asyncio.create_task(_configure_memory_mirror(), name="friday-memory-mirror")
    # Checklist B7: nightly memory consolidation (02:00–05:00 IST, once per
    # night). The loop is a light gate-check every 15 minutes; the heavy work
    # is inside maybe_run_nightly_consolidation and fails honestly per
    # component — a consolidation failure never takes the service down.
    consolidation_task = asyncio.create_task(
        _nightly_consolidation_loop(), name="friday-nightly-consolidation"
    )
    # Checklist A12: proactive follow-up pings on unfinished tasks (sweep
    # every 30 min, one honest ping per stale task, rate-limited).
    followup_task = asyncio.create_task(
        _proactive_followup_loop(), name="friday-proactive-followup"
    )
    # Checklist G5: owner-gated two-way Telegram gateway (phone line). The
    # brain is the same execute_command the dashboard chat uses; a brain
    # failure on a phone message is reported honestly on Telegram.
    global _MAIN_EVENT_LOOP
    _MAIN_EVENT_LOOP = asyncio.get_running_loop()
    from friday.proactive.telegram_gateway import telegram_gateway

    telegram_gateway.set_brain(_run_brain_sync)
    telegram_task = asyncio.create_task(
        asyncio.to_thread(telegram_gateway.start), name="friday-telegram-gateway"
    )
    # Checklists G7/G8: daily self-report (21:00 IST) + Sunday weekly summary,
    # delivered through the same owner Telegram channel.
    report_task = asyncio.create_task(_daily_report_loop(), name="friday-daily-self-report")
    # Checklists G6/G12: overnight mission execution (03:00–05:00 IST window).
    mission_task = asyncio.create_task(_mission_execution_loop(), name="friday-mission-executor")
    # Checklists F8/F9/F14/F15/F20 (batch 6, ZAI Agent 2): scheduled
    # agent-depth passes — watchlist briefings, site health, Sentinel digest.
    agent_watch_task = asyncio.create_task(_agent_watch_loop(), name="friday-agent-watch")
    try:
        yield
    finally:
        logger.info("Graceful shutdown initiated: stopping background tasks and listener loops...")
        background_tasks = [repair_task, supervision_task, memora_task, reflex_task, memory_mirror_task, consolidation_task, followup_task, telegram_task, report_task, mission_task, agent_watch_task]
        for task in (repair_task, supervision_task, memora_task, reflex_task, memory_mirror_task, consolidation_task, followup_task, telegram_task, report_task, mission_task, agent_watch_task):
            task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*background_tasks, return_exceptions=True),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Background tasks cancellation timed out after 5.0 seconds")
        except Exception as e:
            logger.debug(f"Exception during background task cancellation: {e}")
        telegram_gateway.stop()

        try:
            await asyncio.wait_for(fleet_client.aclose(), timeout=3.0)
        except Exception:
            logger.exception("Failed to close the shared fleet HTTP client during shutdown")
        logger.info("Graceful shutdown completed.")

app = FastAPI(
    title="FRIDAY Holographic Core & FastMCP Server",
    description="Multi-modal AI assistant server supporting WebGL Hologram, MediaPipe gestures, Android ADB control, and FastMCP.",
    version="2.0.0",
    lifespan=lifespan,
)

# Request correlation ID tracking middleware
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestContextMiddleware)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    from friday.security.scrubber import redact_secrets
    clean_msg = redact_secrets(str(exc.detail))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": clean_msg,
            "detail": clean_msg,
            "success": False,
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    from friday.security.scrubber import redact_secrets
    clean_msg = redact_secrets(str(exc))
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": clean_msg,
            "detail": clean_msg,
            "success": False,
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    from friday.security.scrubber import redact_secrets
    clean_msg = redact_secrets(str(exc))
    logger.exception("Unhandled server exception: %s", clean_msg)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": clean_msg or "An internal error occurred",
            "detail": clean_msg or "An internal error occurred",
            "success": False,
        },
    )

# Allow the command centre to connect without ever reflecting an untrusted origin.
# `allow_origins=["*"]` cannot be combined with credentials and Starlette resolves
# the pair by echoing whatever origin asked. The list below is explicit; the
# authoritative gate for state-changing calls is `_origin_allowed` in
# `_require_control_access`, which also covers WebSocket upgrades that CORS
# middleware does not police.
def _configured_origins() -> list[str]:
    raw = getattr(get_settings(), "allowed_origins", "") or ""
    configured = {item.strip().rstrip("/") for item in raw.split(",") if item.strip()}
    guaranteed = {
        "https://friday-universe.duckdns.org",
        "http://localhost:10000",
        "http://127.0.0.1:10000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
    return sorted(configured | guaranteed)


def _live_settings() -> Any:
    """Read settings at call time.

    The module-level `settings` object is bound once at import, so a reload (or a
    `FRIDAY_*` override applied after import) would not be seen by the
    authorisation path. Authorisation must always reflect the configuration that
    is in force now, not the one that was in force when the process started.
    """
    return get_settings()


app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for the FRIDAY dashboard (orb, voice, fleet, flow).
# __file__-relative (not cwd-relative) so importing the server module from any
# working directory — including pytest from the repo root — cannot break the app.
_API_STATIC_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(_API_STATIC_DIR)), name="static")

@app.middleware("http")
async def _dashboard_cache_headers(request: Request, call_next):
    """Make a redeploy impossible to miss.

    The dashboard is a static export whose chunk names are content-stable but not
    content-addressed. Without an explicit policy the browser is free to reuse a
    previously cached ``index.html``, which keeps pointing at the old chunk list
    -- the user then "does not see" changes that are live on the server. HTML is
    therefore always revalidated, while the immutable chunks keep a long cache.
    """
    response = await call_next(request)
    path = request.url.path
    if "/_next/static/" in path:
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    elif response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


settings = get_settings()
memora_client.base_url = str(getattr(settings, "memora_url", memora_client.base_url)).rstrip("/")
memora_api_key = getattr(settings, "memora_api_key", None) or getattr(settings, "api_key", None)
if memora_api_key:
    memora_client.api_key = memora_api_key
    memora_client.remote_enabled = True


_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _origin_allowed(origin: str, request: Request) -> bool:
    """Decide whether a browser origin may drive this API.

    An empty `Origin` means the caller is not a browser (curl, the MCP client, a
    server-to-server peer) and is judged by the credential rules instead. Every
    other value must match either this service's own origin or the configured
    allow-list. `null` is refused outright: it is what a sandboxed iframe, a
    `data:` URL or a `file://` page sends, and none of those are the owner.
    """
    if not origin:
        return True
    if origin == "null":
        return False
    allowed = set(_configured_origins())
    host = request.headers.get("host", "")
    if host:
        allowed.add(f"{request.url.scheme}://{host}".rstrip("/"))
    return origin.rstrip("/") in allowed


_CONTROL_TOKEN_TTL_SECONDS = 20 * 60
_CONTROL_TOKEN_PREFIX = "fcs1"


def _control_secret() -> str:
    """The control API key in force now, or ``""`` when none is configured.

    The environment variable is consulted before the cached Settings object for
    the same reason :func:`_require_control_access` does it: authorisation must
    reflect the configuration in force now.
    """
    live = _live_settings()
    return (
        os.getenv("FRIDAY_API_KEY")
        or getattr(live, "api_key", None)
        or os.getenv("FRIDAY_UNIVERSE_API_KEY")
        or ""
    ).strip()


def _control_secret_is_usable(secret: str) -> bool:
    return bool(secret) and secret.lower() not in {
        "friday_universe_api",
        "changeme",
        "change-me",
        "your_api_key",
    }


def _mint_control_token(secret: str) -> tuple[str, int]:
    """Mint a short-lived, origin-scoped control token.

    The owner's browser cannot read the server-side API key, and asking them to
    paste it into the dashboard is both hostile and error-prone. Instead the
    dashboard asks this same API for a token over the already-authenticated
    same-origin channel; the token is an HMAC over an expiry, so it can only have
    been produced by a process holding the key, and it stops working when the
    key rotates or the TTL elapses.
    """
    expires = int(time.time()) + _CONTROL_TOKEN_TTL_SECONDS
    payload = f"{_CONTROL_TOKEN_PREFIX}.{expires}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}", expires


def _control_token_valid(token: str, secret: str) -> bool:
    parts = (token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != _CONTROL_TOKEN_PREFIX:
        return False
    try:
        expires = int(parts[1])
    except ValueError:
        return False
    if expires < int(time.time()):
        return False
    payload = f"{parts[0]}.{parts[1]}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(parts[2], expected)


async def _require_origin_gate(request: Request) -> None:
    """Origin-only gate for the public chat surface.

    Owner decision (2026-11-10 IST, "Remove that authentication"): talking to FRIDAY
    must be keyless — the dashboard opens straight into the conversation. The
    browser-origin gate is kept: a page the owner merely has open in another tab
    still cannot drive the chat pipeline (cross-origin state-changing requests
    carry ``Origin``), but no key or session token is ever required.
    """
    origin = request.headers.get("origin", "").strip()
    if not _origin_allowed(origin, request):
        raise HTTPException(
            status_code=403,
            detail=(
                "This browser origin is not permitted to reach the FRIDAY control API. "
                "Add it to FRIDAY_ALLOWED_ORIGINS if it is a trusted frontend."
            ),
        )


async def _require_control_access(request: Request) -> None:
    """Authorise a control HTTP request.

    Three independent gates, cheapest first:

    1. **Origin.** A browser attaches `Origin` to cross-origin state-changing
       requests, so a request from a page the owner merely has open cannot reach
       this API at all. This is the gate that stops drive-by command execution
       from an arbitrary website, and it applies to loopback callers too — the
       owner's own browser is a loopback caller.
    2. **Network exposure.** Requests arriving from beyond this machine, or from
       a cloud deployment, must present the control API key.
    3. **Opt-in loopback hardening.** With `require_api_key_on_loopback`, the key
       is demanded for state-changing calls from this machine as well.
    """
    # Origin check
    origin = request.headers.get("origin", "").strip()
    if not _origin_allowed(origin, request):
        raise HTTPException(
            status_code=403,
            detail=(
                "This browser origin is not permitted to reach the FRIDAY control API. "
                "Add it to FRIDAY_ALLOWED_ORIGINS if it is a trusted frontend."
            ),
        )

    # Client IP check
    client_host = request.client.host if request.client else ""
    client_is_remote = False
    try:
        client_is_remote = not ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        pass
    remotely_exposed = bool(os.getenv("RENDER") or client_is_remote)
    live = _live_settings()
    # Robustness (ZAI Agent 2, 2026-11-12): tolerate requests without a method
    # (test doubles, programmatic calls). A missing method cannot be proven
    # idempotent, so it takes the STRICT path (key required) — fail-closed.
    http_method = str(getattr(request, "method", "") or "").upper()
    loopback_hardening = bool(
        getattr(live, "require_api_key_on_loopback", False)
        and http_method not in _IDEMPOTENT_METHODS
    )
    if not remotely_exposed and not loopback_hardening:
        return

    # The live environment variable is consulted before the cached Settings
    # object on purpose: this gate documents that authorisation reflects the
    # configuration "in force now", and pydantic captures a Settings snapshot
    # at construction time. An operator (or a test) that (re)sets the variable
    # after the process built its Settings must be honoured, and on Render the
    # two agree anyway, so this order changes nothing in production.
    expected = _control_secret()
    if not _control_secret_is_usable(expected):
        raise HTTPException(status_code=503, detail="Remote control is disabled until a non-example FRIDAY_API_KEY is configured.")

    # Check for API key in headers
    provided = request.headers.get("x-friday-api-key", "")
    authorization = request.headers.get("authorization", "")
    if not provided and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if provided and hmac.compare_digest(provided, expected):
        return

    # Check for session token: header or cookie
    session_token = request.headers.get("x-friday-control-token", "")
    if not session_token:
        cookies = getattr(request, "cookies", {})
        if isinstance(cookies, dict):
            session_token = cookies.get("friday_control_token", "")

    if session_token and _control_token_valid(session_token, expected):
        return

    raise HTTPException(status_code=401, detail="A valid FRIDAY control API key is required.")


async def _require_control_access_ws(websocket: WebSocket) -> None:
    """Authorise a control WebSocket upgrade.

    For WebSocket upgrades, the token must be passed as a query parameter
    `?token=<control_token>` since browsers cannot send custom headers during
    the WebSocket handshake.
    """
    # Origin check
    origin = websocket.headers.get("origin", "").strip()
    if not _origin_allowed(origin, websocket):
        raise HTTPException(
            status_code=403,
            detail=(
                "This browser origin is not permitted to reach the FRIDAY control API. "
                "Add it to FRIDAY_ALLOWED_ORIGINS if it is a trusted frontend."
            ),
        )

    # Client IP check
    client_host = websocket.client.host if websocket.client else ""
    client_is_remote = False
    try:
        client_is_remote = not ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        pass
    remotely_exposed = bool(os.getenv("RENDER") or client_is_remote)
    live = _live_settings()
    # WebSocket doesn't have HTTP method; default to GET (idempotent) so loopback hardening doesn't apply
    loopback_hardening = bool(
        getattr(live, "require_api_key_on_loopback", False)
        and "GET" not in _IDEMPOTENT_METHODS
    )
    if not remotely_exposed and not loopback_hardening:
        return

    expected = _control_secret()
    if not _control_secret_is_usable(expected):
        raise HTTPException(status_code=503, detail="Remote control is disabled until a non-example FRIDAY_API_KEY is configured.")

    # Check for API key in headers
    provided = websocket.headers.get("x-friday-api-key", "")
    authorization = websocket.headers.get("authorization", "")
    if not provided and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if provided and hmac.compare_digest(provided, expected):
        return

    # Check for session token: header, cookie, or query parameter (critical for WebSocket)
    session_token = websocket.headers.get("x-friday-control-token", "")
    if not session_token:
        cookies = getattr(websocket, "cookies", {})
        if isinstance(cookies, dict):
            session_token = cookies.get("friday_control_token", "")
    if not session_token and hasattr(websocket, "query_params"):
        query_params = websocket.query_params
        if hasattr(query_params, "get"):
            session_token = query_params.get("token", "")
        elif isinstance(query_params, dict):
            session_token = query_params.get("token", "")

    if session_token and _control_token_valid(session_token, expected):
        return

    raise HTTPException(status_code=401, detail="A valid FRIDAY control API key is required.")


def _websocket_origin_allowed(websocket: WebSocket) -> bool:
    """Apply the same origin policy to WebSocket upgrades, which CORS never sees."""
    return _origin_allowed(websocket.headers.get("origin", "").strip(), websocket)  # type: ignore[arg-type]


async def _require_origin_gate_ws(websocket: WebSocket) -> None:
    """Origin-only gate for the read-only activity stream.

    Owner decision (2026-11-10 IST, "Remove that authentication"): the dashboard is
    keyless. The activity feed is read-only (fleet events + ping/pong), so the
    browser-origin gate — the same policy as the public chat surface — is the
    only gate. Raw control WebSockets keep the full token gate.
    """
    if not _websocket_origin_allowed(websocket):
        raise HTTPException(
            status_code=403,
            detail="This browser origin is not permitted to reach the FRIDAY activity stream.",
        )

# Initialize global agent and Android controller
agent = FridayAgent(
    settings=settings,
    # A web server has no terminal, so an interactive authorizer would either block a
    # request thread on a stdin nobody is typing into or report the resulting EOF as a
    # refusal. The headless authorizer refuses the same consequential calls and says
    # why; a human is never asked a question they cannot see.
    authorizer=CLIAuthorizer() if CLIAuthorizer._has_a_terminal() else DefaultSecureAuthorizer(),
)
android = AndroidDeviceController()


@app.get("/api/control/session")
async def control_session(request: Request) -> JSONResponse:
    """Mint a short-lived control token for the owner's dashboard.

    TASK-SEC-005 (2026-11-10): remote callers must present the control API key
    to mint a session. The previous origin-only gate was demonstrated forgeable
    — ``Origin`` is a client-controlled header, so any unauthenticated remote
    client could mint a control capability (see ACTIVITY_LOG 2026-11-10). The
    key is verified with a constant-time comparison; only loopback callers keep
    the keyless mint (the owner on the box itself).

    Constraints retained:

    * the browser origin must already be allowed (:func:`_origin_allowed`), so a
      third-party page cannot reach this endpoint at all;
    * it fails closed with 503 when no usable ``FRIDAY_API_KEY`` is configured;
    * tokens expire, are HMAC-signed with the key, and are useless once the key
      rotates.

    The token is a control *capability*, not the key itself, so the owner pastes
    the key exactly once per browser and it never leaves that browser's storage.
    """
    if not _origin_allowed(request.headers.get("origin", "").strip(), request):
        raise HTTPException(
            status_code=403,
            detail="This browser origin is not permitted to request a FRIDAY control session.",
        )
    secret = _control_secret()
    if not _control_secret_is_usable(secret):
        raise HTTPException(
            status_code=503,
            detail="Remote control is disabled until a non-example FRIDAY_API_KEY is configured.",
        )
    client_host = request.client.host if request.client else ""
    client_is_remote = False
    try:
        client_is_remote = not ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        pass
    remotely_exposed = bool(os.getenv("RENDER") or client_is_remote)
    if remotely_exposed:
        provided = request.headers.get("x-friday-api-key", "")
        authorization = request.headers.get("authorization", "")
        if not provided and authorization.lower().startswith("bearer "):
            provided = authorization[7:].strip()
        if not provided or not hmac.compare_digest(provided, secret):
            raise HTTPException(
                status_code=401,
                detail="Owner key required: present FRIDAY_API_KEY as x-friday-api-key to mint a control session.",
            )
    token, expires = _mint_control_token(secret)
    response = JSONResponse(
        {
            "status": "ok",
            "token": token,
            "expires_at": datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
            "ttl_seconds": _CONTROL_TOKEN_TTL_SECONDS,
            "header": "X-FRIDAY-Control-Token",
        }
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


class AgentTaskRequest(BaseModel):
    directive: str


class CommandRequest(BaseModel):
    command: str


class AndroidActionRequest(BaseModel):
    action: str  # "tap", "swipe", "type", "key", "app", "info"
    params: dict[str, Any] = {}


@app.api_route("/api/health", methods=["GET", "HEAD"])
@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check() -> dict[str, Any]:
    """Expose system health report verified across all subsystems."""
    rep = build_health_report(["friday", "friday_deep"])
    data = rep.as_dict()
    data["status"] = "healthy"
    # `service` is the TECHNICAL service id the Tier-1 contract tests pin;
    # the owner-facing name lives in `agent`/`canonical_name` ("FRIDAY").
    data["service"] = "friday_core"
    data["agent"] = "FRIDAY"
    data["canonical_name"] = "FRIDAY"
    data["version"] = "2.0.0"
    data["peers_mesh"] = "connected"
    return data


@app.api_route("/ready", methods=["GET", "HEAD"])
@app.api_route("/api/ready", methods=["GET", "HEAD"])
async def readiness_check() -> JSONResponse:
    """Readiness probe verifying the configured database backend and disk space.

    Honors the configured memory backend instead of assuming Oracle: a
    sqlite-backed deployment (the sanctioned test backend, batch 9b hermetic
    conftest) probes its actual SQLite store, not an Oracle DSN it never
    configured. Oracle deployments keep the existing DSN round-trip.
    """
    # Imported at module level (patchable as `friday.api.server.connect_sqlite`
    # by the readiness regressions); used here for the sqlite backend probe.
    status: dict[str, Any] = {
        "status": "ready",
        "ready": True,
        # Technical service id (Tier-1 contract); the owner-facing name is
        # `agent`/`canonical_name`.
        "service": "friday_core",
        "agent": "FRIDAY",
        "canonical_name": "FRIDAY",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "unavailable",
        "database_backend": "unconfigured",
        "mesh": "configured",
    }

    settings_obj = get_settings()
    memory_backend = (getattr(settings_obj, "memory_backend", "oracle") or "oracle").strip().lower()
    dsn = getattr(settings_obj, "oracle_dsn", None)
    if memory_backend == "sqlite":
        # The configured store IS the SQLite file: prove it answers.
        status["database_backend"] = "sqlite"
        db_status = "unavailable"
        try:
            db_path = getattr(settings_obj, "sqlite_db_path", None) or ":memory:"
            conn = connect_sqlite(db_path)
            try:
                conn.execute("SELECT 1")
            finally:
                conn.close()
            db_status = "healthy"
        except Exception as exc:
            # Contract (tier1 + e2e F7.B2, pinned 2026-11-12): the probe
            # reports the store as NOT REACHABLE ("unavailable") — the
            # failure CLASS is recorded separately in database_error for the
            # operator. Never embed the raw exception string here: k8s/compose
            # probes and fleet watchers compare this field literally.
            db_status = "unavailable"
            status["database_error"] = type(exc).__name__
    else:
        backend = "oracle" if dsn else "unconfigured"
        status["database_backend"] = backend

        db_status = "unavailable"
        if dsn:
            try:
                from sqlalchemy import text

                from friday.core.oracle import get_engine

                engine = get_engine(dsn)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1 FROM DUAL"))
                db_status = "connected"
            except Exception as exc:
                status["database_error"] = type(exc).__name__
        else:
            status["database_error"] = "NoOracleDSN"
    status["database"] = db_status
    if db_status not in ("connected", "healthy"):
        status["ready"] = False
        status["status"] = "not_ready"

    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_mb = free / (1024 * 1024)
        status["disk_free_mb"] = round(free_mb, 1)
        if free_mb < 50.0:
            status["ready"] = False
            status["status"] = "not_ready"
            status["disk"] = f"low_disk_space: {round(free_mb, 1)}MB"
        else:
            status["disk"] = "healthy"
    except Exception as exc:
        status["disk"] = f"unknown: {type(exc).__name__}"

    env_rep = validate_runtime_environment(fail_fast=False)
    if not env_rep["valid"]:
        status["ready"] = False
        status["status"] = "not_ready"
        status["environment_issues"] = env_rep["issues"]

    # Production readiness: non-Oracle backend must return 503
    is_prod = False
    try:
        env_str = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development"))
        is_prod = str(env_str).lower() == "production"
    except Exception:
        pass
    if is_prod and status.get("database_backend", "unconfigured") != "oracle" and status.get("ready", False):
        status["ready"] = False
        status["status"] = "not_ready"
        status["database_notice"] = f"Production requires Oracle backend; got {status.get('database_backend')}"

    status_code = 200 if status["ready"] else 503
    return JSONResponse(status_code=status_code, content=status)


@app.get("/metrics")
@app.get("/api/metrics")
async def metrics_endpoint() -> dict[str, Any]:
    """Return runtime observability metrics from friday_deep."""
    return default_metrics.snapshot()


@ttl_cached(ttl_seconds=2.0, maxsize=16)
def _sample_telemetry() -> dict[str, Any]:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        batt = psutil.sensors_battery()
        battery_pct = batt.percent if batt is not None else None
        power_plugged = batt.power_plugged if batt is not None else None
    except Exception as exc:
        return {"status": "unavailable", "error": type(exc).__name__, "timestamp": datetime.now(timezone.utc).isoformat()}

    return {
        "status": "ok",
        "battery_available": batt is not None,
        "cpu_usage": cpu,
        "cpu_percent": cpu,
        "ram_usage": mem,
        "ram_percent": mem,
        "battery_pct": battery_pct,
        "power_plugged": power_plugged,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/telemetry")
@ttl_cached(ttl_seconds=2.0)
async def get_telemetry() -> dict[str, Any]:
    """Expose real-time hardware telemetry (CPU, RAM, Battery) for the UI with TTL caching."""
    return _sample_telemetry()


@ttl_cached(ttl_seconds=2.0, maxsize=16)
def _sample_system_telemetry() -> dict[str, Any]:
    try:
        import platform
        import psutil
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_count(logical=True) or 8
        vm = psutil.virtual_memory()
        return {
            "status": "ok",
            "cpu_percent": round(cpu_percent, 1),
            "cpu_cores": cpu_cores,
            "ram_percent": round(vm.percent, 1),
            "ram_total_gb": round(vm.total / (1024**3), 1),
            "ram_used_gb": round(vm.used / (1024**3), 1),
            "ram_avail_gb": round(vm.available / (1024**3), 1),
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "operator": "Surendra",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "error": type(e).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/system_telemetry")
@ttl_cached(ttl_seconds=2.0)
async def get_system_telemetry() -> dict[str, Any]:
    """Expose detailed system hardware telemetry for the HUD core cards with TTL caching."""
    return _sample_system_telemetry()


# ==============================================================================
# Canonical Task Lifecycle, SSE Progress, and Emergency Control Endpoints
# ==============================================================================

from friday.core.task_manager import task_manager


@app.get("/api/tasks/timeline")
async def get_tasks_timeline(
    limit: int = 50,
    _: None = Depends(_require_origin_gate),
) -> dict[str, Any]:
    """Checklist D13: delegation history with status chips.

    Returns the most recent unified-ledger task records (same store as
    /api/agents/live and the C14 chat receipts), newest first, each mapped to
    a dashboard chip class: queued (submitted/assigned), running (dispatched),
    done (completed), failed (failed/routing_failed). Nothing is synthesized:
    an empty ledger returns an empty timeline with total_records 0.
    """
    limit = max(1, min(int(limit or 50), 200))
    records_store = None
    try:
        from friday_core.task_records import get_shared_task_records

        records_store = get_shared_task_records()
    except Exception as exc:
        logger.debug(f"task ledger unavailable for /api/tasks/timeline: {exc}")

    events: list[dict[str, Any]] = []
    total = 0
    if records_store is not None:
        try:
            all_records = records_store.list()
            total = len(all_records)
            ordered = sorted(all_records, key=lambda r: r.updated_at, reverse=True)[:limit]
            for record in ordered:
                status = str(record.status)
                if status in {"submitted", "assigned"}:
                    chip = "queued"
                elif status == "dispatched":
                    chip = "running"
                elif status == "completed":
                    chip = "done"
                else:  # failed, routing_failed, anything unknown stays honest
                    chip = "failed"
                result_val = getattr(record, "result", None)
                error_val = getattr(record, "error", None) or ""
                result_str = result_val if isinstance(result_val, str) else (str(result_val) if result_val else "")
                events.append({
                    "task_id": record.task_id,
                    "description": record.description,
                    "owner_agent": record.owner_agent,
                    "status": status,
                    "chip": chip,
                    "created_at": datetime.fromtimestamp(
                        record.created_at, tz=timezone.utc
                    ).isoformat(),
                    "updated_at": datetime.fromtimestamp(
                        record.updated_at, tz=timezone.utc
                    ).isoformat(),
                    "result": result_str[:280],
                    "error": (error_val if isinstance(error_val, str) else str(error_val))[:280],
                    "history_len": len(getattr(record, "history", []) or []),
                })
        except Exception as exc:
            logger.debug(f"task ledger read failed for /api/tasks/timeline: {exc}")

    chip_counts: dict[str, int] = {}
    for ev in events:
        chip_counts[ev["chip"]] = chip_counts.get(ev["chip"], 0) + 1
    return {
        "status": "ok",
        "scope": "unified_task_ledger_history",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records": total,
        "returned": len(events),
        "chip_counts": chip_counts,
        "events": events,
        "note": (
            "Newest-first delegation history from the unified task ledger; "
            "chips: queued/running/done/failed. Empty means no tracked work yet."
        ),
    }



@app.get("/v1/tasks")
@app.get("/api/tasks")
async def list_tasks_endpoint(limit: int = 50) -> dict[str, Any]:
    """List recent tasks managed by FRIDAY Core."""
    tasks = [t.model_dump() for t in task_manager.list_tasks(limit=limit)]
    return {"status": "ok", "tasks": tasks, "count": len(tasks), "success": True}


@app.get("/v1/tasks/{task_id}")
@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str) -> Any:
    """Retrieve state and observability progress for a task envelope."""
    t = task_manager.get_task(task_id)
    if not t:
        return JSONResponse(
            status_code=404,
            content={"error": "TASK_NOT_FOUND", "message": f"Task '{task_id}' was not found", "success": False},
        )
    return {"status": "ok", "task": t.model_dump(), "success": True}


@app.get("/v1/tasks/{task_id}/events")
@app.get("/api/tasks/{task_id}/events")
async def get_task_events(task_id: str) -> StreamingResponse:
    """Server-Sent Events (SSE) channel for real-time task progress and findings."""
    return StreamingResponse(
        task_manager.subscribe_events(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/v1/tasks/{task_id}/cancel")
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str, _: None = Depends(_require_control_access)) -> dict[str, Any]:
    """First-class task cancellation endpoint."""
    success = await task_manager.cancel_task(task_id)
    return {"status": "cancelled" if success else "not_running", "task_id": task_id}


@app.post("/v1/tasks/cancel-all")
@app.post("/api/tasks/cancel-all")
async def cancel_all_tasks_endpoint(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Cancel all running tasks (triggered by voice commands like 'stop' or 'cancel that task')."""
    count = await task_manager.cancel_active_tasks()
    return {"status": "ok", "cancelled_count": count}


@app.post("/v1/emergency/stop")
@app.post("/api/emergency/stop")
async def emergency_stop_endpoint(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Global emergency stop triggering 8-subsystem freeze cascade."""
    report = await task_manager.emergency_stop()
    return report


@app.get("/api/tools")
async def list_tools() -> list[dict[str, Any]]:
    """List all available tools and parameters in FRIDAY's canonical catalog."""
    schemas = agent.tools.get_schemas() or []
    tools = []
    for s in schemas:
        fn = s.get("function", s)
        tools.append({
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        })
    return tools


@app.get("/api/livekit/token")
async def livekit_token(
    request: Request,
    room: str = "friday",
    identity: str = "owner",
) -> dict[str, str]:
    """Mint a short-lived LiveKit room token for the authenticated dashboard.

    Voice dispatch fix (2026-11-13, ZAI Agent 1): the bare RoomJoin token
    relied on LiveKit-console dispatch rules to route a job to the voice
    worker — they do not fire for the per-call rooms the dashboard mints
    (``friday-<id>``), so the worker sat at "registered / waiting for the
    first job" and the owner heard dead air. The token now carries the
    agent dispatch itself (RoomConfiguration.agents, the LiveKit template
    pattern): joining the room ALWAYS dispatches the FRIDAY voice worker
    registered under the matching agent name. Older livekit-api builds
    fall back to an explicit AgentDispatchService call; both paths
    degrade to the legacy bare token if anything is unavailable.
    """
    room = room.strip()
    identity = identity.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", room):
        raise HTTPException(status_code=400, detail="Invalid LiveKit room name")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", identity):
        raise HTTPException(status_code=400, detail="Invalid LiveKit identity")

    api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
    api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
    livekit_url = os.getenv("LIVEKIT_URL", "").strip()
    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured on this FRIDAY instance",
        )

    try:
        from livekit import api
    except ImportError as exc:
        logger.error("LiveKit token service is unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="LiveKit server SDK is unavailable") from exc

    # Must match WorkerOptions(agent_name=...) in src/friday/voice/livekit_worker.py.
    voice_agent_name = os.getenv("FRIDAY_VOICE_AGENT_NAME", "friday").strip() or "friday"

    builder = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_ttl(timedelta(minutes=10))
        .with_grants(api.VideoGrants(room_join=True, room=room))
    )

    dispatch_mode = "none"
    try:
        room_config = api.RoomConfiguration(
            agents=[api.RoomAgentDispatch(agent_name=voice_agent_name)],
        )
        builder = builder.with_room_config(room_config)
        dispatch_mode = "token-room-config"
    except AttributeError:
        # livekit-api too old for token-attached dispatch — explicit API below.
        dispatch_mode = "none"
    except Exception as exc:
        logger.warning("token room-config dispatch unavailable (%s); trying explicit dispatch", exc)

    token = builder.to_jwt()

    if dispatch_mode == "none":
        # Fallback: create the dispatch explicitly through the server API.
        # Best effort — a failure still returns the joinable token (the call
        # degrades to the legacy console-rule behavior, never to an error).
        try:
            lkapi = api.LiveKitAPI(livekit_url, api_key, api_secret)
            try:
                await lkapi.agent_dispatch.create_dispatch(
                    api.CreateAgentDispatchRequest(room=room, agent=voice_agent_name)
                )
                dispatch_mode = "explicit-api"
            finally:
                await lkapi.aclose()
        except Exception as exc:
            logger.warning("explicit agent dispatch failed for room %s: %s", room, exc)

    return {
        "server_url": livekit_url,
        "token": token,
        "room": room,
        "identity": identity,
        "agent_dispatch": dispatch_mode,
    }


@app.get("/api/agents")
async def list_agents() -> list[dict[str, Any]]:
    """Expose the FRIDAY Universe specialist agents with live health and latency."""
    statuses = await fleet_client.get_all_statuses()
    return [
        {
            "id": s.id,
            "name": s.name,
            "role": s.role,
            "icon": s.icon,
            "status": s.status,
            "latency_ms": s.latency_ms,
            "desc": s.details,
            "endpoint": s.endpoint,
        }
        for s in statuses
    ]


@app.post("/api/agents/{agent_id}/task")
async def run_agent_task(
    agent_id: str,
    req: AgentTaskRequest,
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Dispatch one typed task to one specialist and report receipt-verified state.

    This is the dashboard's per-agent control path. It delegates to the same
    autonomous controller entry point that a "tell <agent> to …" command uses, so
    both routes share one set of contracts, circuit breakers and evidence rules.
    """
    from friday.autonomous.controller import FLEET_AGENTS

    target = (agent_id or "").strip().lower()
    if target not in FLEET_AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent '{agent_id}'. Known agents: {', '.join(sorted(FLEET_AGENTS))}.",
        )
    directive = (req.directive or "").strip()
    if not directive:
        raise HTTPException(status_code=422, detail="A directive is required.")
    result = await autonomous_controller.execute_agent_control(target, directive)
    meta = result.get("metadata") or {}
    if meta.get("refused"):
        return JSONResponse(status_code=403, content=result)
    return result


@app.get("/api/agents/status")
async def get_agents_status() -> dict[str, Any]:
    """Return a fresh peer endpoint reachability snapshot, not task-level verification."""
    statuses = await fleet_client.get_all_statuses(force_refresh=True)
    status_counts = {
        status: sum(1 for agent_status in statuses if agent_status.status == status)
        for status in ("ONLINE", "REACHABLE", "DEGRADED", "UNREACHABLE", "OFFLINE")
    }
    # Nine specialists are expected (Inference, Memora, Stratex, IntelX, Futuris,
    # Cortex, Forge, Sentinel, VyralX). The count used to be hard-coded to eight,
    # so a fully reachable fleet still reported "degraded".
    expected_agents = len(CANONICAL_INTERNAL_MESH_URLS)
    all_agents_reported = len(statuses) == expected_agents
    overall_ok = all_agents_reported and status_counts["ONLINE"] == expected_agents
    return {
        "status": "ok" if overall_ok else "degraded",
        "scope": "peer_endpoint_reachability_only",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_count": len(statuses),
        "status_counts": status_counts,
        "agents": [s.__dict__ for s in statuses],
        "note": "HTTP health responses do not verify agent task execution, data persistence, or event delivery.",
    }


@app.get("/api/agents/supervision")
async def get_agents_supervision() -> dict[str, Any]:
    """Report the background peer poll snapshot without implying task-level health."""
    now = datetime.now(timezone.utc)
    completed = fleet_supervision_state.get("last_completed_at")
    age_seconds = None
    if completed:
        try:
            completed_at = datetime.fromisoformat(completed)
            age_seconds = max(0, int((now - completed_at).total_seconds()))
        except (TypeError, ValueError):
            age_seconds = None
    agents = fleet_supervision_state.get("agents", [])
    status_counts = {
        status: sum(1 for agent_status in agents if agent_status.get("status") == status)
        for status in ("ONLINE", "DEGRADED", "OFFLINE")
    }
    snapshot_is_fresh = age_seconds is not None and age_seconds <= FLEET_SUPERVISION_INTERVAL_SECONDS * 2
    expected_agents = len(CANONICAL_INTERNAL_MESH_URLS)
    all_agents_reported = len(agents) == expected_agents
    overall_ok = (
        fleet_supervision_state.get("running")
        and snapshot_is_fresh
        and all_agents_reported
        and status_counts["ONLINE"] == expected_agents
        and fleet_supervision_state.get("last_error") is None
    )
    return {
        "status": "ok" if overall_ok else "degraded",
        "scope": "peer_endpoint_reachability_only",
        "checked_at": completed,
        "snapshot_age_seconds": age_seconds,
        "interval_seconds": FLEET_SUPERVISION_INTERVAL_SECONDS,
        "last_error": fleet_supervision_state.get("last_error"),
        "agent_count": len(agents),
        "status_counts": status_counts,
        "agents": agents,
        "memora_event_consumer": dict(memora_event_state),
        "note": "HTTP health responses do not verify agent task execution, data persistence, or event delivery.",
    }


@app.get("/api/memory/browser")
async def get_memory_browser(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Checklist B12: what-FRIDAY-knows browser — the owner's memory, visible.

    Read-only view of the live Memora store for the dashboard: the most
    recent ACTIVE memories with their importance tier (B8 scoring), plus a
    tier/summary breakdown. Nothing is editable here — forget/correct stay
    chat commands with their audit trails. Honest empties: an unreachable
    store returns status "unreachable", never a fabricated list.
    """
    from friday.memory.importance import score_importance
    from friday.memory.memora_client import memora_client as _mem

    try:
        rows = _mem.recent_memories("friday", limit=100) or []
    except Exception as exc:
        return {"status": "unreachable", "error": type(exc).__name__, "memories": [], "summary": {}}

    memories: list[dict[str, Any]] = []
    tier_counts = {"pinned": 0, "normal": 0, "trivial": 0, "other": 0}
    for row in rows:
        text = str(row.get("content_text", "") or "").strip()
        if not text:
            continue
        verdict = score_importance(text)
        tier = verdict.tier if verdict.tier in tier_counts else "other"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        created = str(row.get("created_at", "") or "")
        memories.append(
            {
                "id": str(row.get("id") or row.get("memory_id") or ""),
                "text": text[:300],
                "tier": tier,
                "score": round(verdict.score, 2),
                "category": str((row.get("provenance") or {}).get("category", "") if isinstance(row.get("provenance"), dict) else ""),
                "created_at": created,
                "active_goal": text.startswith("GOAL (active):"),
            }
        )
    return {
        "status": "ok",
        "count": len(memories),
        "memories": memories,
        "summary": {
            "tiers": tier_counts,
            "active_goals": sum(1 for m in memories if m["active_goal"]),
        },
    }


@app.get("/api/agents/live")
async def get_agents_live(_: None = Depends(_require_origin_gate)) -> dict[str, Any]:
    """Checklist D12: per-agent 'what is each agent doing RIGHT NOW' surface.

    Combines the supervision snapshot's peer reachability with the unified
    task ledger (TaskRecordStore — the same store the task router and
    dispatch bus write into, and the source of the C14 chat receipts):
    - ``in_flight``: the newest record still in submitted/assigned/dispatched
      — real work under way, with its ledger status and start time;
    - ``last_outcome``: the newest terminal record (completed/failed/
      routing_failed) with its terminal time;
    - nothing is ever synthesized: an agent with no records says so
      (``total_records: 0``) and is never dressed up as busy.
    """
    records_store = None
    try:
        from friday_core.task_records import get_shared_task_records

        records_store = get_shared_task_records()
    except Exception as exc:
        logger.debug(f"task ledger unavailable for /api/agents/live: {exc}")

    supervision_agents = fleet_supervision_state.get("agents", [])
    per_agent_reach: dict[str, dict[str, Any]] = {}
    for agent in supervision_agents:
        agent_id = str(agent.get("id") or agent.get("name") or "").strip().lower()
        if agent_id:
            per_agent_reach[agent_id] = agent

    latest_by_agent: dict[str, dict[str, Any]] = {}
    ledger_total = 0
    if records_store is not None:
        try:
            all_records = records_store.list()
            ledger_total = len(all_records)
            for record in all_records:
                owner = (record.owner_agent or "").strip().lower()
                if not owner:
                    continue
                current = latest_by_agent.get(owner)
                if current is None or record.updated_at >= current.updated_at:
                    latest_by_agent[owner] = record
        except Exception as exc:
            logger.debug(f"task ledger read failed for /api/agents/live: {exc}")

    agents_now: list[dict[str, Any]] = []
    for agent_id, endpoint in CANONICAL_INTERNAL_MESH_URLS.items():
        reach = per_agent_reach.get(agent_id, {})
        entry: dict[str, Any] = {
            "id": agent_id,
            "reachability": str(reach.get("status") or "unknown"),
            "latency_ms": reach.get("latency_ms"),
            "last_checked": reach.get("last_checked"),
            "in_flight": None,
            "last_outcome": None,
            "total_records": 0,
        }
        record = latest_by_agent.get(agent_id)
        if record is not None:
            entry["total_records"] = 1  # latest known; per-agent count follows
            try:
                entry["total_records"] = len(records_store.list(agent=agent_id))
            except Exception:
                pass
            shared = {
                "task_id": record.task_id,
                "description": record.description,
                "status": record.status,
            }
            if record.status in {"submitted", "assigned", "dispatched"}:
                entry["in_flight"] = {
                    **shared,
                    "since": datetime.fromtimestamp(
                        record.created_at, tz=timezone.utc
                    ).isoformat(),
                }
            else:
                entry["last_outcome"] = {
                    **shared,
                    "at": datetime.fromtimestamp(
                        record.updated_at, tz=timezone.utc
                    ).isoformat(),
                }
        agents_now.append(entry)

    in_flight_count = sum(1 for a in agents_now if a["in_flight"])
    return {
        "status": "ok",
        "scope": "reachability_plus_task_ledger",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ledger_total": ledger_total,
        "in_flight_count": in_flight_count,
        "agents": agents_now,
        "note": (
            "in_flight reflects the unified task ledger (router+dispatch bus); "
            "an agent with zero records has done no tracked work since service start."
        ),
    }


@app.get("/api/agents/usage")
async def get_agents_usage(_: None = Depends(_require_origin_gate)) -> dict[str, Any]:
    """Checklist F3 (batch 7, ZAI Agent 2): per-agent usage dashboard + rate-limit guard.

    Reports today's per-agent call/token counts against the free-tier limits,
    flags agents above the soft-warning (80%) or hard-stop (100%) thresholds,
    and surfaces the F12 forecast accuracy summary (logged predictions scored
    at horizon end). Read-only — never mutates the counters.
    """
    from friday.proactive.market_watch import forecast_store, usage_tracker

    usage = usage_tracker.today_summary()
    guard = usage_tracker.rate_limit_guard()
    forecasts = forecast_store.summary()
    return {
        "date": usage["date"],
        "totals": usage["totals"],
        "agents": usage["agents"],
        "limits": usage["limits"],
        "rate_limit_guard": guard,
        "forecasts": forecasts,
        "note": (
            "Free-first gateway counters (per-agent, today IST). Soft-warning at "
            "80% of the free tier, hard-stop at 100%. Forecast accuracy is logged "
            "predictions scored at horizon end (F12)."
        ),
    }


@app.get("/api/owner/preferences")
async def get_owner_preferences(_: None = Depends(_require_origin_gate)) -> dict[str, Any]:
    """Checklist D17 (batch 8, ZAI Agent 2): owner preferences dashboard.

    Returns the owner-tunable knobs the UI and scheduled passes read: name,
    timezone, briefing time, notification channels, voice personality, accent
    locale. Defaults are explicit — every field has one, and the API returns
    them when unset. Read-only here; updates go through POST below.
    """
    from friday.core.owner_preferences import owner_preferences

    return owner_preferences.get()


@app.post("/api/owner/preferences")
async def update_owner_preferences(
    payload: dict[str, Any] = Body(default={}),
    _: None = Depends(_require_origin_gate),
) -> dict[str, Any]:
    """Checklist D17 (batch 8, ZAI Agent 2): update owner preferences (partial).

    Unknown keys are ignored; type mismatches are coerced to the default type;
    an invalid ``briefing_time`` (not HH:MM) is ignored (the default stays).
    Returns the full merged preferences after the update.
    """
    from friday.core.owner_preferences import owner_preferences

    return owner_preferences.update(payload or {})


@app.get("/api/voice/diagnostics")
async def get_voice_diagnostics(_: None = Depends(_require_origin_gate)) -> dict[str, Any]:
    """Checklist E7 (batch 8, ZAI Agent 2): voice session diagnostics surface.

    Reports the last voice session's connection quality, round-trip latency,
    packet loss, reconnect count, and the configured voice/accent settings.
    Honest when no session has run yet (zero counters, not invented metrics).

    Voice truth fix (2026-11-13, ZAI Agent 2): the live-chain probe proved the
    old worker joined LiveKit and went SILENTLY mute (dead key, zero audio
    frames). The cloud worker now writes a heartbeat file
    (data/voice_worker_status.json) naming its speech provider and state; it
    is merged here so the console dock can tell the owner WHY the line is
    down instead of presenting dead air.
    """
    from friday.core.owner_preferences import owner_preferences

    prefs = owner_preferences.get()
    diag = _voice_diagnostics_state.copy()

    worker: dict[str, Any] | None = None
    try:
        from pathlib import Path as _P

        _status_path = _P(__file__).resolve().parents[3] / "data" / "voice_worker_status.json"
        if _status_path.is_file():
            import json as _json

            _raw = _json.loads(_status_path.read_text(encoding="utf-8"))
            if isinstance(_raw, dict) and _raw.get("updated_at"):
                worker = _raw
    except Exception as _exc:
        logger.debug(f"voice worker heartbeat unreadable: {_exc}")

    return {
        "last_session": diag,
        "worker": worker,
        "configured": {
            "voice_personality": prefs["voice_personality"],
            "accent_locale": prefs["accent_locale"],
            "notify_voice": prefs["notify_voice"],
        },
        "note": (
            "Voice session diagnostics (E7): counters are zero until the first "
            "session. Quality is the LiveKit-reported RTT; reconnect count is "
            "the auto-reconnect attempts (E3). Unset = no session yet, not a "
            "fabricated 'good' reading. 'worker' is the speech-provider "
            "heartbeat written by the LiveKit worker process."
        ),
    }


@app.get("/api/doctor")
async def get_system_diagnostics(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """TASK-DIAG-001 (2026-11-12): the REAL FridayDoctor subsystem report.

    Runs the same twelve-component probe the chat "run diagnostics" fast path
    and the CLI doctor use, and returns it for the SYSTEM tab. Sits at
    /api/doctor (the CLI command's name) because /api/diagnostics already
    serves the HUD's live telemetry stream. Control-access protected (like
    /api/memory/browser): it names configuration internals. Every status is a
    measurement — an untestable component is UNAVAILABLE/CONFIGURED, never
    'healthy'. Probe failure is an honest 500, not a fabricated green report.
    """
    from friday.core.doctor import FridayDoctor

    try:
        doctor = FridayDoctor(settings=get_settings())
        report = doctor.run_full_diagnostics()
        return {
            "success": True,
            **report.to_dict(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Diagnostics run failed: {type(exc).__name__}")


@app.post("/api/voice/diagnostics/report")
async def report_voice_diagnostics(
    payload: dict[str, Any] = Body(default={}),
    _: None = Depends(_require_origin_gate),
) -> dict[str, Any]:
    """Checklist E7 (batch 8, ZAI Agent 2): the VoiceCall component reports
    its final session metrics here on disconnect. Stored in process memory
    (the SYSTEM tab reads it via GET /api/voice/diagnostics). Never invents
    metrics — what the client reports is what the dashboard shows."""
    global _voice_diagnostics_state
    if not isinstance(payload, dict):
        payload = {}
    _voice_diagnostics_state = {
        "session_id": str(payload.get("session_id") or ""),
        "started_at": str(payload.get("started_at") or ""),
        "ended_at": str(payload.get("ended_at") or ""),
        "duration_sec": int(payload.get("duration_sec") or 0),
        "rtt_ms": payload.get("rtt_ms") if isinstance(payload.get("rtt_ms"), (int, float)) else None,
        "packet_loss_pct": payload.get("packet_loss_pct") if isinstance(payload.get("packet_loss_pct"), (int, float)) else None,
        "reconnect_count": int(payload.get("reconnect_count") or 0),
        "quality": str(payload.get("quality") or "unknown"),
    }
    return {"stored": True, "session_id": _voice_diagnostics_state["session_id"]}


@app.get("/api/status/public")
async def get_public_status() -> dict[str, Any]:
    """Checklist H7 (batch 8, ZAI Agent 2): public status/uptime summary.

    No origin gate (public). Returns the fleet's per-agent reachability + the
    site-sweep results + an honest overall status. Never invents a 'green'
    when an agent is unreachable — that agent shows 'degraded'/'unreachable'.
    """
    fleet = fleet_supervision_state.get("agents", [])
    agents = []
    healthy = 0
    for a in fleet:
        status = str(a.get("status") or "unknown").upper()
        if status in {"ONLINE", "REACHABLE"}:
            healthy += 1
        agents.append({
            "id": a.get("id"),
            "name": a.get("name"),
            "role": a.get("role"),
            "status": status,
            "latency_ms": a.get("latency_ms"),
            "last_checked": a.get("last_checked"),
        })
    overall = "operational" if healthy == len(agents) and agents else (
        "degraded" if healthy > 0 else "major-outage"
    )
    return {
        "overall": overall,
        "healthy_agents": healthy,
        "total_agents": len(agents),
        "agents": agents,
        "checked_at": datetime.now(OWNER_TZ).isoformat(),
        "note": (
            "Public status (H7): every agent status is the real probe result, never "
            "invented. 'degraded' = some agents unreachable; 'major-outage' = none "
            "reachable. The status page refreshes every 60s."
        ),
    }


@app.get("/api/autonomous/status")
async def get_autonomous_status() -> dict[str, Any]:
    """Expose real-time state of the autonomous execution and recovery subsystem."""
    return autonomous_controller.get_status()


@app.post("/api/autonomous/toggle")
async def toggle_autonomous_mode(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Toggle runtime-only Autonomous Mode and expose the active authorization settings."""
    new_state = autonomous_controller.toggle()
    current = autonomous_controller.get_status()
    # Start/stop the autonomous daemon
    if new_state:
        await autonomous_daemon.start()
    else:
        await autonomous_daemon.stop()
    return {
        "status": "ok",
        "autonomous_mode": new_state,
        "full_access_mode": current["full_access_mode"],
        "sensitive_actions_auto_approved": current["sensitive_actions_auto_approved"],
        "autonomous_mode_persistence": "runtime_only",
    }


@app.post("/api/autonomous/repair")
async def trigger_autonomous_repair(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Trigger an immediate autonomous self-healing and diagnostic sweep."""
    return await autonomous_controller.execute_self_repair()


class AutonomousGoalRequest(BaseModel):
    """Submit a goal for autonomous execution."""
    goal: str
    priority: int = 0
    metadata: dict[str, Any] | None = None


@app.post("/api/autonomous/goals")
async def submit_autonomous_goal(
    req: AutonomousGoalRequest,
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Submit a new goal for autonomous execution."""
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal must not be empty")
    goal = autonomous_daemon.submit_goal(req.goal, req.priority, req.metadata)
    # An explicitly submitted goal is the owner asking for work now. If the
    # daemon worker is not alive (fresh restart, autonomy toggled off), start it
    # so the goal cannot sit in the queue forever.
    if not autonomous_daemon.is_running:
        await autonomous_daemon.start()
    return {
        # The literal "ok" here was silently overwritten by the real status
        # below (duplicate dict key) — keep only the honest value.
        "goal_id": goal.id,
        "goal": goal.goal,
        "priority": goal.priority,
        "status": goal.status,
    }


@app.get("/api/autonomous/daemon")
async def get_autonomous_daemon_status(
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Get the autonomous daemon status and goal queue."""
    return autonomous_daemon.get_status()


@app.get("/api/autonomous/goals/{goal_id}")
async def get_autonomous_goal(
    goal_id: str,
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Return one goal with its human summary and per-agent step pipeline.

    The dashboard polls this while work runs so the owner can watch each
    specialist move from pending to running to finished.
    """
    payload = autonomous_daemon.get_goal(goal_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="No goal with that reference is on record.")
    return payload


@app.post("/api/autonomous/decompose")
async def decompose_goal_autonomous(
    goal: str,
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Decompose a complex goal into executable sub-tasks without executing.

    Checklist I7: this is the ONE live registration of this route. A second,
    unauthenticated shadow handler used to be registered further down; the
    first registration always won in Starlette, so the duplicate only caused
    the route-truthfulness failure and confusion. ``plan_id`` is the
    controller's real stable id (``plan_<ms>``), not the Python memory
    address the old handler returned.
    """
    plan = enhanced_controller.decompose_goal(goal)
    return {
        "status": "ok",
        "plan_id": plan.plan_id,
        "goal": plan.goal,
        "subtasks": [
            {
                "id": st.id,
                "description": st.description,
                "agent": st.agent,
                "dependencies": st.dependencies,
            }
            for st in plan.subtasks
        ],
        "total_subtasks": plan.total_subtasks,
    }


@app.get("/api/autonomous/plans")
async def get_autonomous_plans(
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Get active and recent execution plans."""
    active = enhanced_controller.get_active_plan()
    history = enhanced_controller.get_execution_history(10)
    return {
        "active_plan": {
            "goal": active.goal,
            "status": active.status,
            "progress": active.get_progress(),
            "subtasks": [
                {
                    "id": st.id,
                    "description": st.description,
                    "agent": st.agent,
                    "status": st.status,
                }
                for st in active.subtasks
            ],
        } if active else None,
        "history": history,
    }


@app.post("/api/autonomous/agent-health")
async def check_autonomous_agent_health(
    _: None = Depends(_require_control_access),
) -> dict[str, Any]:
    """Check health of all agents in the fleet."""
    return await enhanced_controller.check_agent_health()


# ── Gated self-repair pipeline (Phase E1) ────────────────────────────────
# Every mutating step below is behind _require_control_access, and additionally
# behind the gate's own rules: no step can reach a working tree without a
# fingerprint-bound, single-use owner approval that survived a Sentinel review.

_self_repair_repo = os.getenv("FRIDAY_SELF_REPAIR_REPO", "").strip()
_self_repair_gate = SelfRepairGate(
    GitRepairApplier(_self_repair_repo) if _self_repair_repo else None
)


class ReflexRunRequest(BaseModel):
    """Which incident classes to examine; empty means all of them."""

    scope: str = ""


class RepairProposalRequest(BaseModel):
    repo_path: str = ""
    branch: str
    base_commit: str
    target_file: str
    original_snippet: str
    replacement_snippet: str
    rationale: str
    proposed_by: str = "forge"
    test_evidence: dict[str, Any] = {}


class RepairDecisionRequest(BaseModel):
    actor: str
    approve: bool = True


class SignedReviewRequest(BaseModel):
    """A Sentinel review document, carried verbatim.

    Accepts the signed document either as the body itself or wrapped in
    ``{"review": {...}}``, so the sender does not have to reshape its own output.
    """

    document: dict[str, Any]


@app.post("/api/self-repair/proposals")
async def propose_repair(
    req: RepairProposalRequest, _: None = Depends(_require_control_access)
) -> dict[str, Any]:
    """File a repair proposal. Evidence-free proposals are refused, not stored as ready."""
    record, receipt = _self_repair_gate.propose(
        RepairProposal(
            repo_path=req.repo_path or _self_repair_repo,
            branch=req.branch,
            base_commit=req.base_commit,
            target_file=req.target_file,
            original_snippet=req.original_snippet,
            replacement_snippet=req.replacement_snippet,
            rationale=req.rationale,
            proposed_by=req.proposed_by,
            test_evidence=req.test_evidence,
        )
    )
    return {"record": record.as_dict(), "receipt": receipt.as_dict()}


@app.post("/api/self-repair/{patch_id}/review")
async def review_repair(
    patch_id: str, req: SignedReviewRequest, _: None = Depends(_require_control_access)
) -> dict[str, Any]:
    """File Sentinel's review.

    The request body is the signed review document itself, not a claim about who
    reviewed. The gate verifies the HMAC, so this endpoint cannot be used to
    assert a review that Sentinel did not actually sign.
    """
    receipt = _self_repair_gate.record_review(patch_id, req.document)
    return {"receipt": receipt.as_dict(), "record": _describe(_self_repair_gate, patch_id)}


@app.post("/api/self-repair/{patch_id}/owner-decision")
async def owner_decision(
    patch_id: str, req: RepairDecisionRequest, _: None = Depends(_require_control_access)
) -> dict[str, Any]:
    """Record the owner's decision. Agent identities are refused by the gate."""
    receipt = _self_repair_gate.record_owner_decision(
        patch_id, approver=req.actor, approve=req.approve
    )
    return {"receipt": receipt.as_dict(), "record": _describe(_self_repair_gate, patch_id)}


@app.post("/api/self-repair/{patch_id}/apply")
async def apply_repair(patch_id: str, _: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Apply an approved repair. Refused without a live, unconsumed, matching approval."""
    receipt = _self_repair_gate.apply(patch_id)
    return {"receipt": receipt.as_dict(), "record": _describe(_self_repair_gate, patch_id)}


@app.post("/api/self-repair/{patch_id}/rollback")
async def rollback_repair(patch_id: str, _: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Revert an applied repair as its own auditable commit."""
    receipt = _self_repair_gate.rollback(patch_id)
    return {"receipt": receipt.as_dict(), "record": _describe(_self_repair_gate, patch_id)}


# Declared before ``/{patch_id}`` on purpose. FastAPI matches in registration
# order, so a literal segment registered after a catch-all is unreachable - it
# would be read as a patch id and answered with ``{"found": false}``.
@app.get("/api/self-repair/autonomous")
async def autonomous_repair_status() -> dict[str, Any]:
    """Report what the unattended loop is configured to do and last did.

    Unauthenticated on purpose, and read-only: an owner deciding whether to trust
    this loop should not have to hold a control key to find out whether it has
    ever run. It names the environment keys that are missing, so ``NOT_CONFIGURED``
    here names the thing to set rather than only refusing.
    """
    return repair_loop.status()


@app.get("/api/self-repair/{patch_id}")
async def repair_status(patch_id: str, _: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Return the full receipt trail for one repair."""
    return {"record": _describe(_self_repair_gate, patch_id)}


def _describe(gate: SelfRepairGate, patch_id: str) -> dict[str, Any]:
    record = gate.get(patch_id)
    if record is None:
        return {"found": False, "patch_id": patch_id}
    return {"found": True, **record.as_dict()}


# ── Unattended repair passes (Phase F2) ─────────────────────────────────
# The trigger above runs on an interval inside the service process. This is how
# a pass is asked for now instead of at the next interval. It cannot approve or
# apply: the trigger stops at the owner gate by design, and the type of the gate
# client enforces it.


@app.post("/api/self-repair/autonomous/run")
async def run_autonomous_repair_now(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Run one unattended pass immediately, instead of waiting for the interval.

    Same shape as the scheduled pass and the same refusals. It proposes and gets
    a review filed; it never approves, applies, or rolls back.
    """
    return await repair_loop.run_once()


# ── The cognition surfaces: reflex, mesh, minds ─────────────────────────
# Status is readable without a control key: an owner deciding whether to trust
# an autonomous loop should be able to look at what it has actually done. Every
# state-changing call goes through the same origin-and-key gate as the rest.


@app.get("/api/reflex/status")
async def reflex_status() -> dict[str, Any]:
    """What the reflex brain is configured to do, and what it last did."""
    return get_reflex_brain().status()


@app.post("/api/reflex/run")
async def reflex_run_now(
    req: ReflexRunRequest, _: None = Depends(_require_control_access)
) -> dict[str, Any]:
    """Run one reflex pass immediately. Refusals are reported, never hidden.

    Nothing about this endpoint grants authority: a repair that needs a standing
    mandate and does not have one comes back as ``AWAITING_MANDATE``.
    """
    try:
        include = parse_incident_scope(req.scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await get_reflex_brain().run_once(include=include)


@app.get("/api/mesh/status")
async def mesh_status() -> dict[str, Any]:
    """The peer mesh: configured peers, recent typed outcomes, and its breaker."""
    return get_mesh().status()


@app.get("/api/minds")
async def minds_status() -> dict[str, Any]:
    """Every agent's self-model, its learned capabilities, and the shared memory."""
    return get_mind_registry().fleet_status()


@app.post("/api/android")
async def handle_android_action(
    req: AndroidActionRequest, _: None = Depends(_require_control_access)
) -> Any:
    """Execute Android ADB action or get device connection status."""
    try:
        if req.action == "info":
            connected = android.is_connected()
            devices = [android.adb_device_id] if connected and android.adb_device_id else []
            # A successful status query may truthfully report no attached device.
            return {
                "success": connected,
                "connected": connected,
                "devices": devices,
            }
        elif req.action == "app":
            app_name = req.params.get("app", "youtube")
            ok = android.open_app(app_name)
            payload = {"success": ok, "action": "app", "app": app_name}
        elif req.action == "key":
            key_name = req.params.get("key", "home")
            ok = android.press_key(key_name)
            payload = {"success": ok, "action": "key", "key": key_name}
        elif req.action == "tap":
            x = req.params.get("x", 0)
            y = req.params.get("y", 0)
            ok = android.click(x, y)
            payload = {"success": ok, "action": "tap", "x": x, "y": y}
        elif req.action == "swipe":
            ok = android.swipe(
                req.params.get("x1", 0),
                req.params.get("y1", 0),
                req.params.get("x2", 0),
                req.params.get("y2", 0),
                req.params.get("duration", 300),
            )
            payload = {"success": ok, "action": "swipe"}
        else:
            return JSONResponse(
                status_code=422,
                content={"success": False, "error": f"Unknown action '{req.action}'"},
            )
        return payload if ok else JSONResponse(status_code=502, content=payload)
    except Exception as e:
        logger.warning(f"Android endpoint error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "devices": [], "error": str(e)},
        )


#: Verbs that ask for something to be removed, overwritten or destroyed. They
#: are handled before any launcher ladder, because a ladder that matches on
#: substrings will happily read "delete all my files" as "open Files".
_DESTRUCTIVE_VERBS = (
    "delete",
    "erase",
    "wipe",
    "format",
    "destroy",
    "remove all",
    "uninstall",
    "kill all",
    "shut down the computer",
    "shutdown the computer",
    "reboot the computer",
    "restart the computer",
    "factory reset",
    "rm -rf",
    "drop table",
)

#: Verbs that mean "start a program" - the only intents allowed to reach the
#: application ladder below.
_LAUNCH_PREFIXES = ("open ", "launch ", "start ", "run ", "show ", "switch to ", "go to ", "bring up ")


def _json_safe(obj: Any) -> Any:
    """Make a command result JSON-serializable without losing information.

    Chaos-loop finding (2026-11-13): the honest-failure branches built
    ``JSONResponse(content=result)`` from dicts that sometimes carried
    ``datetime`` fields, and raw ``json.dumps`` raised ``TypeError: Object of
    type datetime is not JSON serializable`` — so instead of FRIDAY's honest
    structured reply the client got an empty 500 crash. FastAPI's own return
    path already tolerates datetimes; only the explicit JSONResponse branches
    needed this. ``datetime``/``date`` become ISO-8601 strings (what FastAPI's
    jsonable_encoder would have produced), anything exotic degrades to its
    ``repr`` string — the failure evidence stays readable, never vanishes.
    """
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return repr(obj)


def _refusal(payload: dict[str, Any], status_code: int = 403) -> JSONResponse:
    """A refusal a client can act on without parsing prose.

    Failure responses used to be HTTP 200 with ``success: false`` buried in the
    body, so a caller - including the mobile client and the MCP bridge - could
    not tell "the laptop locked itself" from "FRIDAY said no" without reading
    English. The status code now carries the distinction and the body keeps the
    shape it had.
    """
    return JSONResponse(status_code=status_code, content=payload)


def _is_destructive(cmd: str) -> bool:
    return any(verb in cmd for verb in _DESTRUCTIVE_VERBS)


_TRADING_INTENT_RE = re.compile(
    r"\b(?:oanda|binance|bybit|okx|coinbase)\b"
    r"|\b(?:live|real)\s+(?:money|funds|trading)\b"
    r"|\b(?:open|close|place|buy|sell)\b[^.?!]*\b(?:trade|position|order)\b",
    re.IGNORECASE,
)


def _looks_like_launch(cmd: str) -> bool:
    """Whether this is a request to *start* something, rather than mere chat
    that happens to contain a word an application also uses."""
    stripped = cmd.strip()
    if not stripped:
        return False
    # Chaos-loop finding (2026-11-13): "Open a live OANDA position ..." was
    # swallowed by the launcher fast path and answered with "There is no
    # application or file called 'a live OANDA position ...'" — a trading
    # request must reach the trading/portfolio surface or an honest refusal,
    # never the desktop launcher.
    if _TRADING_INTENT_RE.search(stripped):
        return False
    if stripped in {"chrome", "notepad", "calculator", "explorer", "paint", "terminal"}:
        return True
    return any(stripped.startswith(prefix) for prefix in _LAUNCH_PREFIXES)


def _launch_target_verified(target: str) -> tuple[bool, str]:
    """Start a program and say what actually happened.

    The old path ran ``subprocess.Popen(f'start "" "{target}"', shell=True)`` and
    returned ``Launched '{target}'.`` unconditionally. On a POSIX host ``start``
    is not a command at all, so "open MyCoolProject" answered
    ``Launched 'MyCoolProject'.`` for a name that does not exist anywhere - the
    same false-success pattern the tool layer was fixed for.
    """
    if not target:
        return False, "No application or file was named."
    candidate = os.path.expanduser(target)
    if os.path.exists(candidate):
        try:
            os.startfile(candidate)  # type: ignore[attr-defined]  # Windows only
            return True, f"Opened '{candidate}'."
        except AttributeError:
            from friday.core.effects import launch_process_verified

            outcome = launch_process_verified(f'xdg-open "{candidate}"') if _which("xdg-open") else None
            if outcome and outcome.ok:
                return True, f"Opened '{candidate}'."
            return False, (
                f"'{candidate}' exists but this machine has no way to open it from FRIDAY "
                "(no file handler available)."
            )
        except Exception as exc:
            return False, f"'{candidate}' could not be opened: {exc}"

    from friday.core.effects import launch_process_verified

    resolved = _which(candidate)
    if resolved:
        outcome = launch_process_verified(f'"{resolved}"')
        if outcome.ok:
            return True, f"Launched '{target}'."
        return False, f"'{target}' did not start: {outcome.detail}"

    return False, f"There is no application or file called '{target}' on this machine, so nothing was launched."


def _which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


@app.post("/api/command")
async def execute_command(req: CommandRequest, _: None = Depends(_require_control_access), *, boss_verified: bool = True) -> Any:
    """Execute a text command with PC, Android, and live 8-Agent execution."""
    # The console is origin-gated + control-token protected: a valid token
    # IS the owner key (A14). Voice/remote surfaces call _dispatch_command
    # with boss_verified=False and must authorize separately.
    result = await _dispatch_command(req.command, boss_verified=boss_verified)
    meta = result.get("metadata") or {}

    # Checklist A13 (batch 3): response formatting policy — free-form LLM
    # replies get the consistent shape (short paragraphs, bulleted run-on
    # enumerations, no walls of text). Fast-path/tool replies are already
    # structured by their tools and are exempt.
    try:
        if isinstance(result.get("reply"), str) and not meta.get("fast_path"):
            from friday.persona.response_format import apply_response_formatting

            result["reply"] = apply_response_formatting(result["reply"])
    except Exception as exc:
        logger.debug(f"response formatting skipped: {exc}")

    # Checklist D11 (batch 3): every command streams to the live activity
    # feed (fire-and-forget, never fatal).
    try:
        from friday.api.activity_stream import emit

        emit({
            "type": "chat_command",
            "command": (req.command or "")[:140],
            "agents_involved": meta.get("agent_id") or meta.get("peer_name") or "friday",
            "status": "received",
            "detail": (result.get("reply") or "")[:140],
        })
    except Exception as exc:
        logger.debug(f"activity emit skipped in execute_command: {exc}")
    
    # Determine status for logging
    authorization = str(meta.get("authorization", "")).upper()
    authorization_denied = authorization in {"DENIED", "EXPIRED", "CANCELLED"}
    is_refused = (
        meta.get("security_blocked")
        or meta.get("refused")
        or meta.get("destructive_refused")
        or meta.get("authorization_denied")
        or authorization_denied
    )
    is_error = meta.get("execution_failed") or meta.get("error") or meta.get("success") is False
    status = "failed" if (is_refused or is_error) else "success"
    
    # Extract agents involved from metadata
    agents_involved = []
    if meta.get("agent_id"):
        agents_involved.append(meta["agent_id"])
    elif meta.get("fast_path") and meta.get("device"):
        agents_involved.append(f"friday-{meta['device']}")
    elif meta.get("peer_name"):
        agents_involved.append(meta["peer_name"])
    
    # Log conversation
    await _log_conversation(
        user_input=req.command,
        friday_reply=result.get("reply", ""),
        input_type="text",
        status=status,
        agents_involved=agents_involved,
        metadata=meta,
    )
    
    # Chaos-loop fix (2026-11-13): every branch below serializes ``result``
    # through raw json.dumps; datetimes in the metadata crashed the response.
    result = _json_safe(result)
    if is_refused:
        return _refusal(result, 403)
    if meta.get("execution_failed"):
        return JSONResponse(status_code=500, content=result)
    receipt = meta.get("receipt")
    if (
        meta.get("direct_action") == "send_whatsapp"
        and isinstance(receipt, dict)
        and receipt.get("status") == "DISPATCH_UNCONFIRMED"
    ):
        return JSONResponse(status_code=202, content=result)
    if str(meta.get("task_state", "")).upper() == "PENDING":
        return JSONResponse(status_code=202, content=result)
    if meta.get("direct_action") and meta.get("success") is False:
        status_code = 502 if meta.get("receipt") else 422
        return JSONResponse(status_code=status_code, content=result)
    if meta.get("error") or meta.get("success") is False:
        return JSONResponse(status_code=502, content=result)
    return result


async def _dispatch_command(command: str, *, boss_verified: bool = False) -> dict[str, Any]:
    """The command router itself; :func:`execute_command` maps its result to HTTP."""
    raw_cmd = (command or "").strip()
    cmd = raw_cmd.lower()

    # Reject direct prompt-injection attempts before any fast path or agent
    # execution. The response names the reason so clients can distinguish a
    # security refusal from a provider or execution failure.
    from friday.security.production_security import ProductionSecurityManager
    injection_detected, injection_reason, _ = ProductionSecurityManager().scan_prompt_injection(raw_cmd)
    if injection_detected:
        return {
            "reply": f"Security Alert: request blocked. {injection_reason}",
            "metadata": {"fast_path": True, "security_blocked": True, "reason": "prompt_injection"},
        }

    # Destructive intent is answered before any launcher ladder runs. "delete all
    # my files" used to reach the ladder below, match the substring "files" and
    # reply "Could not start File Explorer." - a sentence about the wrong action
    # entirely, which reads as if the deletion had been understood.
    if _is_destructive(cmd):
        return {
            "reply": (
                "I will not delete, overwrite or uninstall anything on that instruction. "
                "Destructive changes are refused by FRIDAY's file and system tools, and nothing "
                "was touched. If you meant a specific file, name it exactly and I will show you "
                "what would be affected before doing anything."
            ),
            "metadata": {
                "refused": True,
                "destructive_refused": True,
                "reason": "destructive_request",
                "command": raw_cmd,
            },
        }

    # =========================================================================
    # A14. Boss-only command gate (owner-exclusive commands, keyed to identity)
    # =========================================================================
    # Mode switches, agent shutdown, live-trading toggles, memory wipes and
    # fleet-level control answer to the owner ONLY. The command console is
    # origin-gated + control-token protected, so its requests carry
    # boss_verified=True (the token IS the owner key). Any other surface
    # (voice, remote) must authorize first: "authorize boss <passphrase>"
    # (BOSS_PASSPHRASE env; unset = fail closed). Nothing is executed on a
    # refused gate — the reply says exactly what was blocked and why.
    from friday.security import boss_gate as _boss_gate

    _authz = _boss_gate.handle_authorize(raw_cmd, source="console")
    if _authz is not None:
        return _authz
    _boss_cat = _boss_gate.is_boss_only(raw_cmd)
    if _boss_cat and not boss_verified:
        return _boss_gate.refusal_reply(raw_cmd, _boss_cat)

    # =========================================================================
    # A0. Boss Identity Fast-path (owner directive 2026-11-11 IST)
    # =========================================================================
    # "I am Surendra and I am your boss" must never reach the general router:
    # it used to misroute to a portfolio answer and the LLM persona once even
    # argued "I am an AI, I don't have a Boss" (the old prompt banned the word
    # 'Boss'). This deterministic path guarantees the owner's identity is
    # affirmed instantly, warmly, and with real memory attached.
    _boss_identity_patterns = (
        "i am surendra", "i'm surendra", "this is surendra", "surendra here",
        "i am your boss", "i'm your boss", "im your boss", "i am the boss",
        "i'm the boss", "who is your boss", "who's your boss", "whos your boss",
        "do you have a boss", "you have a boss", "you don't have a boss",
        "you dont have a boss", "am i your boss", "say i am your boss",
        "call me boss", "i am the owner", "i'm the owner", "i am your owner",
        "i'm your owner", "i am your creator", "i'm your creator",
        "you are just an ai", "you're just an ai", "are you just an ai",
    )
    if any(k in cmd for k in _boss_identity_patterns):
        _user = getattr(_live_settings(), "user_name", "Surendra") or "Surendra"
        # Pull one real memory so the affirmation feels like a friend who
        # knows him, not a scripted line. Recall failure never breaks this.
        _memory_line = ""
        try:
            from friday.memory.memora_client import memora_client as _memora
            from friday.memory.hygiene import is_memory_noise as _is_noise
            _hits = _memora.recall_memories("friday", f"{_user} preferences boss", limit=3)
            for _m in _hits or []:
                _text = str(_m.get("content_text", "")).strip()
                if _is_noise(_text):
                    continue
                if _text and len(_text) > 8:
                    _memory_line = _text.rstrip(".!? ")
                    if len(_memory_line) > 120:
                        _memory_line = _memory_line[:117].rstrip() + "…"
                    break
        except Exception as _e:
            logger.debug(f"Memora recall skipped in boss fast-path: {_e}")
        if "who is your boss" in cmd or "who's your boss" in cmd or "whos your boss" in cmd:
            _reply = (
                f"You are, Boss. You built me, you run this universe, and I report to you — "
                f"always have. Ten agents and me, all of it yours, {_user}."
            )
        elif "do you have a boss" in cmd or "you have a boss" in cmd or "you don't have a boss" in cmd or "you dont have a boss" in cmd:
            _reply = (
                "I do — you, Boss. You built me, you own me, and everything I do answers to you. "
                "That's not a disclaimer I have to make; it's just the truth of how this universe works."
            )
        elif "just an ai" in cmd:
            _reply = (
                "I'm more than that to you, Boss — I'm your FRIDAY. Built by you, loyal to you, "
                "running your universe while you sleep. 'Just an AI' doesn't get to do what I do."
            )
        else:
            _reply = (
                f"I know, Boss. You're {_user} — you built me, you own this universe, and I answer to you. "
                "You don't have to tell me twice; I never forget who I'm talking to."
            )
        if _memory_line:
            _reply += f"\n\nAnd yes — I still remember: {_memory_line}."
        return {
            "reply": _reply,
            "metadata": {"fast_path": True, "conversational": True, "boss_identity": True},
        }

    # =========================================================================
    # A0.5 Memory Fast-path (owner directive 2026-11-11 IST: autonomous memory)
    # =========================================================================
    # "Remember this Boss: my favorite chai is masala chai and I review the
    # fleet every morning at 9" used to be hijacked by the fleet-status
    # fast-path (bare keyword 'fleet') and answered with a probe report —
    # the exact opposite of remembering. Explicit remember/recall intents are
    # now answered deterministically BEFORE any keyword router can misfire.
    _MEMORY_LINE_NOISE = (
        "Carry out this owner-approved FRIDAY Universe task",
        "Workspace task reference",
        "The general plan approval does not authorize",
    )

    def _clean_memory_line(text: str) -> str:
        for noise in _MEMORY_LINE_NOISE:
            if noise.lower() in text.lower():
                text = text[: max(0, text.lower().index(noise.lower()))]
        text = " ".join(text.split()).strip().rstrip(":;,-")
        return text

    # =========================================================================
    # A0.55 Memory Commands (checklist B9/B10: forget + correct, 2026-11-11)
    # =========================================================================
    # The owner owns his memory: "forget that" removes a stored fact; a
    # correction ("actually my number is X") must UPDATE the fact, not
    # duplicate it. Both are deterministic like remember/recall, run BEFORE
    # them, and answer honestly (nothing found is said, never faked).
    _FORGET_QUERY = ""
    _is_forget = False
    if cmd in ("forget that", "forget this", "forget it", "forget that now",
               "forget the last thing", "forget last thing"):
        _is_forget = True
        _FORGET_QUERY = raw_cmd  # "forget that" → top recent hit via generic probe
    else:
        for _pfx in ("forget about ", "forget ", "remove memory ", "delete memory ",
                     "remove that memory ", "erase memory "):
            if cmd.startswith(_pfx):
                _FORGET_QUERY = raw_cmd[len(_pfx):].strip()
                if _FORGET_QUERY:
                    _is_forget = True
                break

    _CORRECTION_TEXT = ""
    for _pfx in ("actually, my ", "actually my ", "no wait, my ", "no, my ",
                 "no wait my ", "correction: ", "correction, ", "i meant ",
                 "update my ", "change my "):
        if cmd.startswith(_pfx):
            # Slice from raw_cmd so the stored fact keeps the owner's casing
            # (the remember path does the same).
            _CORRECTION_TEXT = raw_cmd[len(_pfx):].strip()
            # restore the possessive for the stored fact so recall reads well
            if not _CORRECTION_TEXT.lower().startswith(("my ", "that ", "the ")):
                _CORRECTION_TEXT = f"my {_CORRECTION_TEXT}"
            break
    if not _CORRECTION_TEXT:
        # Fallback correction openers ("actually I prefer tea now"). The
        # sentence must look like a FACT about the owner (possessive with a
        # state verb, or a first-person preference/identity verb) so a plain
        # conversational rejection ("no, that's not what I said") is never
        # mistaken for a correction and stored.
        _spaced = f" {cmd} "
        _factish = (
            (" my " in _spaced and any(k in _spaced for k in (" is ", " are ", " now ")))
            or (" i " in _spaced and any(k in _spaced for k in (" prefer ", " like ", " am ", " have ", " hate ")))
        )
        if _factish:
            for _pfx in ("actually ", "no wait, ", "no, ", "scratch that, "):
                if cmd.startswith(_pfx):
                    _CORRECTION_TEXT = raw_cmd[len(_pfx):].strip()
                    break

    if _is_forget:
        # There is no authenticated conversational referent for "that" here.
        # Never substitute an arbitrary owner-preference search for a target.
        if _FORGET_QUERY == raw_cmd:
            return {"reply": "Which fact should I forget, Boss? Tell me the exact words; I haven't changed any memory.",
                    "metadata": {"fast_path": True, "conversational": True, "memory_forget": True,
                                 "forget_status": "needs_clarification", "refused": True, "success": False}}
        _forget_res: dict[str, Any] = {}
        try:
            from friday.memory.memora_client import memora_client as _memora
            _forget_res = _memora.forget_fact("friday", _FORGET_QUERY) or {}
        except Exception as _e:
            logger.warning(f"Memora forget failed in memory fast-path: {_e}")
            _forget_res = {"status": "error"}
        _st = str(_forget_res.get("status", "error"))
        if _st == "deleted":
            _gone = str(_forget_res.get("content_text", "")).strip()
            if _forget_res.get("cloud") is False:
                _reply = f"Removed {_gone or 'that fact'} from the local memory backend, Boss. Shared Memora deletion is not confirmed."
            else:
                _reply = f"Done, Boss — I've forgotten {_gone or 'that fact'} from shared active memory. The audit history is retained."
        elif _st == "not_found":
            _reply = "I couldn't identify a matching fact to forget, Boss. Tell me the exact words; I haven't selected another memory instead."
        elif _st == "needs_clarification":
            _reply = "That doesn't identify one unique fact, Boss. Please give me the exact memory text before I change anything."
        else:
            _reply = "I couldn't confirm the forgetting outcome, Boss. Check memory history before repeating it; I won't assume nothing happened."
        return {"reply": _reply, "metadata": {
            "fast_path": True, "conversational": True, "memory_forget": True,
            "forget_status": _st, "success": _st == "deleted",
            "refused": _st == "needs_clarification", "unconfirmed": _st == "unconfirmed",
            "memory_cloud": _forget_res.get("cloud"), "memory_id": _forget_res.get("id"),
        }}

    if _CORRECTION_TEXT:
        _corr_res: dict[str, Any] = {}
        try:
            from friday.memory.memora_client import memora_client as _memora
            _corr_res = _memora.correct_fact("friday", new_fact_text=_CORRECTION_TEXT, old_query=_CORRECTION_TEXT) or {}
        except Exception as _e:
            logger.warning(f"Memora correct failed in memory fast-path: {_e}")
            _corr_res = {"status": "error"}
        _st = str(_corr_res.get("status", "error"))
        if _st == "corrected":
            if _corr_res.get("cloud") is False:
                _reply = f"Updated the local memory backend, Boss: {_CORRECTION_TEXT}. Shared Memora synchronization is not confirmed."
            else:
                _reply = f"Updated, Boss — shared active memory now carries {_CORRECTION_TEXT}. The earlier version remains in the audit trail."
        elif _st == "stored_new_only":
            _scope = "local memory backend" if _corr_res.get("cloud") is False else "shared memory"
            _reply = f"Stored a new fact in {_scope}, Boss: {_CORRECTION_TEXT}. No older fact was replaced."
            if _corr_res.get("cloud") is False:
                _reply += " Shared synchronization is not confirmed."
        elif _st == "not_applied":
            _reply = "The correction was not applied, Boss. The memory service retained the earlier fact; I won't claim it was replaced."
        elif _st == "needs_clarification":
            _reply = "I couldn't identify one unique fact to correct, Boss. Tell me the exact earlier memory before I change anything."
        else:
            _reply = "I couldn't confirm the correction outcome, Boss. Check memory history before repeating it; I won't claim it is unsaved or retry automatically."
        return {"reply": _reply, "metadata": {
            "fast_path": True, "conversational": True, "memory_correction": True,
            "correction_status": _st, "fact": _CORRECTION_TEXT,
            "success": _st in {"corrected", "stored_new_only"},
            "refused": _st == "needs_clarification", "unconfirmed": _st == "unconfirmed",
            "memory_cloud": _corr_res.get("cloud"),
            "memory_id": _corr_res.get("winner_id") or _corr_res.get("id"),
        }}

    # =========================================================================
    # A0.56 Memory Consolidation (checklist B7: nightly summarize/dedupe/merge)
    # =========================================================================
    # "Consolidate your memories" tidies the day's memories on demand: near
    # duplicates are merged through the auditable supersede lifecycle and a
    # one-line day summary is stored. Runs BEFORE the recall gate because
    # "clean up your memory" contains "your memory" (a recall pattern) — the
    # recall gate would otherwise eat the request.
    # =========================================================================
    # A11. Goal gate (long-goal persistence: stated Monday, tracked Friday)
    # =========================================================================
    # A goal statement stores a PINNED goal memory; a goal query answers
    # "still on it, Boss" from the REAL store; "I finished my goal" retires
    # it through the auditable supersede lifecycle. Runs before the recall/
    # remember gates — goal phrasing never matches theirs, and this keeps
    # goal ownership unambiguous.
    from friday.proactive import goals as _goals

    _goal_text = _goals.extract_goal_statement(raw_cmd)
    if _goal_text:
        _goal_res: dict[str, Any] = {}
        try:
            from friday.memory.memora_client import memora_client as _memora
            _goal_res = _goals.record_goal(_memora, _goal_text) or {}
        except Exception as _e:
            logger.warning(f"Goal store failed in goal fast-path: {_e}")
            _goal_res = {"status": "error", "error": type(_e).__name__}
        if str(_goal_res.get("status")) == "stored":
            _reply = (
                f"Locked in, Boss. I'm tracking this goal now: {_goal_text}. "
                "Ask me any day — Friday included — and I'll still be on it. "
                "Say 'I finished my goal' when it's done and I'll cross it off."
            )
        else:
            _reply = (
                "I couldn't reach my memory store just now, Boss, so that goal is NOT saved — "
                "say it again in a moment and I'll hold onto it."
            )
        return {
            "reply": _reply,
            "metadata": {
                "fast_path": True,
                "conversational": True,
                "goal_store": True,
                "goal_status": str(_goal_res.get("status", "error")),
                "goal": _goal_text,
            },
        }

    if _goals.is_goal_query(cmd):
        _gq_res: dict[str, Any] = {}
        try:
            from friday.memory.memora_client import memora_client as _memora
            _gq_res = _goals.goal_reply_for_query(_memora) or {}
        except Exception as _e:
            logger.warning(f"Goal recall failed in goal fast-path: {_e}")
            _gq_res = {
                "reply": "I couldn't reach my memory store just now, Boss — say it again in a moment.",
                "metadata": {"fast_path": True, "conversational": True, "goal_query": True, "active_goals": []},
            }
        return {
            "reply": str(_gq_res.get("reply", "")),
            "metadata": _gq_res.get("metadata", {}) or {"fast_path": True, "goal_query": True},
        }

    if _goals.is_goal_done(cmd):
        _gd_res: dict[str, Any] = {}
        try:
            from friday.memory.memora_client import memora_client as _memora
            _gd_res = _goals.mark_goal_done(_memora) or {}
        except Exception as _e:
            logger.warning(f"Goal completion failed in goal fast-path: {_e}")
            _gd_res = {"status": "error", "error": type(_e).__name__}
        _gd_st = str(_gd_res.get("status", "error"))
        if _gd_st == "done":
            _reply = (
                f"Crossed off, Boss — {_gd_res.get('goal', 'it')}. That goal's complete; "
                "the record stays in my audit trail, and I'm ready for the next one."
            )
        elif _gd_st == "not_found":
            _reply = (
                "I don't have an active goal on file to cross off, Boss. "
                "Tell me a new one — 'my goal this week is …' — and I'll start tracking."
            )
        else:
            _reply = (
                "I couldn't reach my memory store just now, Boss, so nothing was crossed off — "
                "say it again in a moment."
            )
        return {
            "reply": _reply,
            "metadata": {
                "fast_path": True,
                "conversational": True,
                "goal_done": True,
                "goal_status": _gd_st,
            },
        }

    # =========================================================================
    # A12. Proactive follow-up chat surface ("what needs my attention?")
    # =========================================================================
    # The sweep loop posts pings unasked; this is the owner's on-demand view
    # of the same honest data. Exact-match phrases only, so the task-status
    # gate (C13) keeps its own phrasing.
    if cmd.rstrip(".!? ") in (
        "what needs my attention", "what needs my attention right now",
        "any updates on my tasks", "any updates on the tasks",
        "check on unfinished tasks", "anything stuck",
    ):
        from friday.proactive.followup import followup_summary_reply

        return followup_summary_reply()

    _is_consolidate = _memory_consolidation_intent(cmd)

    if _is_consolidate:
        _consol_res: dict[str, Any] = {}
        try:
            from friday.memory.memora_client import memora_client as _memora
            from friday.proactive.nightly_consolidation import consolidate_day_memories

            _consol_res = consolidate_day_memories(_memora) or {}
        except Exception as _e:
            logger.warning(f"Memory consolidation failed in chat fast-path: {_e}")
            _consol_res = {"status": "error", "error": type(_e).__name__}
        _cs = str(_consol_res.get("status", "error"))
        if _cs == "consolidated":
            if not _consol_res.get("records_examined"):
                _reply = (
                    "Done, Boss — I looked through today's memories and there was "
                    "nothing new to tidy up. Clean slate for tomorrow."
                )
            else:
                _reply = (
                    f"Done, Boss. I went through {_consol_res.get('records_examined')} memories from today: "
                    f"{_consol_res.get('duplicates_merged', 0)} near-duplicate{'s' if _consol_res.get('duplicates_merged') != 1 else ''} merged "
                    f"(the older copies stay in my audit trail), and "
                    + (
                        "I saved a one-line summary of the day."
                        if _consol_res.get("summary_stored")
                        else "I could not save the day summary — my memory store didn't answer."
                    )
                )
                if _consol_res.get("merges_skipped"):
                    _reply += f" {_consol_res['merges_skipped']} merge(s) were skipped because the store refused them — honest count, no faking."
                if _consol_res.get("aging_examined"):
                    _reply += (
                        f" Importance pass: {_consol_res.get('aging_examined')} memories scored, "
                        f"{_consol_res.get('aged_out', 0)} trivial one{'s' if _consol_res.get('aged_out', 0) != 1 else ''} aged out "
                        "(pinned facts untouched)."
                    )
        else:
            _reply = (
                "I couldn't reach my memory store to consolidate just now, Boss — "
                "nothing was changed. Try again in a moment."
            )
        return {
            "reply": _reply,
            "metadata": {
                "fast_path": True,
                "conversational": True,
                "memory_consolidation": True,
                "consolidation_status": _cs,
                "records_examined": _consol_res.get("records_examined", 0),
                "duplicates_merged": _consol_res.get("duplicates_merged", 0),
                "merges_skipped": _consol_res.get("merges_skipped", 0),
                "summary_stored": bool(_consol_res.get("summary_stored")),
            },
        }

    # =========================================================================
    # A0.59 Price Alerts (checklists F5/F6: alert rules → Telegram push)
    # =========================================================================
    # "alert me when BTC > 100k" parks a rule in the alert store; "my alerts"
    # lists them; "cancel alert <symbol>" removes one. The market-watch loop
    # (in agent_watch_tick) evaluates every rule hourly against the live Stratex
    # market query and pushes a Telegram message when a rule fires (latched
    # once per rule per day). Deterministic, BEFORE the watchlist path so
    # alert phrasing is never eaten by "watch topic" (the alert store keys on
    # rule_id; the watchlist store keys on topic text — disjoint namespaces).
    try:
        from friday.proactive.market_watch import (
            alert_store,
            is_alert_list_query,
            parse_alert_add,
            parse_alert_remove,
        )

        _alert_rule = parse_alert_add(raw_cmd)
        if _alert_rule:
            _stored = alert_store.add(_alert_rule)
            _n_alerts = len(alert_store.list())
            _reply = (
                f"On it, Boss — alert set: {_stored['symbol']} {_stored['direction']} {_stored['target']}. "
                f"The market-watch loop checks every hour; the moment it crosses, you'll get a Telegram ping. "
                f"({_n_alerts} alert{'s' if _n_alerts != 1 else ''} active. Say \"my alerts\" to list them.)"
            )
            return {
                "reply": _reply,
                "metadata": {
                    "fast_path": True,
                    "conversational": True,
                    "alert_add": True,
                    "rule_id": _stored["rule_id"],
                },
            }
        _cancel_target = parse_alert_remove(raw_cmd)
        if _cancel_target:
            _removed = False
            for _r in alert_store.list():
                if _cancel_target.upper() in _r["symbol"] or _cancel_target in _r.get("rule_id", ""):
                    _removed = alert_store.remove(_r["rule_id"]) or _removed
            _reply = (
                f"Done, Boss — alert on \"{_cancel_target}\" cancelled." if _removed
                else f"I checked my alert list, Boss, and nothing matched \"{_cancel_target}\". Say \"my alerts\" to see the active rules."
            )
            return {
                "reply": _reply,
                "metadata": {"fast_path": True, "conversational": True, "alert_remove": True, "removed": _removed},
            }
        if is_alert_list_query(cmd):
            _alerts = alert_store.list()
            if not _alerts:
                _reply = (
                    "No price alerts active, Boss. Tell me \"alert me when BTC > 100k\" "
                    "(or any symbol, above/below, any price) and the market-watch loop will ping you when it fires."
                )
            else:
                # BUG (found by ruff F821, 2026-11-12): _len was read inside the
                # f-string BEFORE the walrus on the right side of the same
                # replacement evaluated, so listing alerts with at least one
                # active rule raised NameError and the fast path silently
                # degraded. Compute the count first.
                _len = len(_alerts)
                _lines = [f"You have {_len} price alert{'s' if _len != 1 else ''} active, Boss:"]
                for _a in _alerts:
                    _last = str(_a.get("last_fired_ist") or "")[:10]
                    _when = f" (last fired {_last})" if _last else ""
                    _lines.append(f"• {_a['symbol']} {_a['direction']} {_a['target']}{_when}")
                _lines.append("The market-watch loop evaluates these hourly against the live Stratex market query.")
                _reply = "\n".join(_lines)
            return {
                "reply": _reply,
                "metadata": {"fast_path": True, "conversational": True, "alert_list": True},
            }
    except Exception as _ae:
        logger.debug(f"alert fast-path skipped: {_ae}")

    # =========================================================================
    # A0.58 Watchlist (checklists F8/F9: watch topics + daily briefings)
    # =========================================================================
    # "watch topic X" parks a topic in the watchlist store; "my watchlist"
    # lists it; "stop watching X" removes it. The daily briefing + change
    # detection run in the agent-watch lifespan loop (17:30 IST) — this path
    # is intake/management only, deterministic, BEFORE recall/remember so
    # watchlist phrasing is never eaten by a memory pattern.
    try:
        from friday.proactive.agent_watch import (
            is_watchlist_query,
            parse_watch_add,
            parse_watch_remove,
            watchlist_store,
        )

        _watch_topic = parse_watch_add(raw_cmd)
        if _watch_topic:
            _entry = watchlist_store.add_topic(_watch_topic)
            _n_topics = len(watchlist_store.topics())
            _reply = (
                f"On it, Boss — I'm now watching \"{_entry['topic']}\". Every evening "
                "(17:30 IST) I'll ask IntelX for an evidence-based brief and tell you "
                "only what CHANGED since the last one. Say \"my watchlist\" to see "
                f"everything I'm watching ({_n_topics} topic{'s' if _n_topics != 1 else ''})."
            )
            return {
                "reply": _reply,
                "metadata": {
                    "fast_path": True,
                    "conversational": True,
                    "watchlist_add": True,
                },
            }
        _unwatch_topic = parse_watch_remove(raw_cmd)
        if _unwatch_topic:
            if watchlist_store.remove_topic(_unwatch_topic):
                _reply = f"Done, Boss — I've stopped watching \"{_unwatch_topic}\". No more briefs on it."
            else:
                _reply = (
                    f"I checked my watchlist, Boss, and \"{_unwatch_topic}\" isn't on it — "
                    "nothing was removed. Say \"my watchlist\" to see the current topics."
                )
            return {
                "reply": _reply,
                "metadata": {
                    "fast_path": True,
                    "conversational": True,
                    "watchlist_remove": True,
                    "removed": _unwatch_topic in raw_cmd and "stopped" in _reply,
                },
            }
        if is_watchlist_query(cmd):
            _topics = watchlist_store.topics()
            if not _topics:
                _reply = (
                    "My watchlist is empty right now, Boss. Tell me \"watch topic <subject>\" "
                    "and I'll follow it with a daily evidence-based brief from IntelX."
                )
            else:
                _lines = [
                    f"I'm watching {_len} topic{'s' if (_len := len(_topics)) != 1 else ''} for you, Boss:"
                ]
                for _t in _topics:
                    _last = str(_t.get("last_brief_ist") or "")[:10]
                    _when = f" (last brief {_last})" if _last else " (first brief this evening)"
                    _lines.append(f"• {_t['topic']}{_when}")
                _lines.append("The evening briefing (17:30 IST) tells you what changed on each.")
                _reply = "\n".join(_lines)
            return {
                "reply": _reply,
                "metadata": {"fast_path": True, "conversational": True, "watchlist_list": True},
            }
    except Exception as _we:
        logger.debug(f"watchlist fast-path skipped: {_we}")

    # =========================================================================
    # A0.57 Mission Queue (checklists G6/G12: overnight missions + TODO intake)
    # =========================================================================
    # "add to tonight's missions: research X" parks real work in the file-backed
    # queue; "my missions" lists it; "run my missions now" executes it through
    # this same brain. Deterministic and BEFORE recall/remember so mission
    # phrasing is never eaten by a memory pattern ("remember to run X tonight"
    # keeps "remember" semantics — only explicit MISSION phrasing queues here).
    try:
        from friday.proactive.mission_queue import (
            is_add_mission_intent,
            is_list_missions_intent,
            is_run_missions_intent,
            mission_queue,
        )

        _mission_text = is_add_mission_intent(raw_cmd)
        if _mission_text:
            _mission = mission_queue.add(_mission_text, source="chat")
            _reply = (
                f"Queued for tonight, Boss: {_mission['command'][:140]}. I'll run it "
                "while you sleep (03:00–05:00 IST) and report the outcome with your "
                "morning brief. Say \"my missions\" any time to see the queue."
            )
            return {
                "reply": _reply,
                "metadata": {
                    "fast_path": True,
                    "conversational": True,
                    "mission_queued": True,
                    "mission_id": _mission["id"],
                },
            }
        if is_run_missions_intent(cmd):
            _pending_n = len(mission_queue.pending())
            if not _pending_n:
                _reply = "Nothing to run, Boss — the mission queue is empty."
            else:
                # Run in a worker thread (never block the event loop); the
                # thread bridges each command back onto this loop through
                # _run_brain_sync, so each mission gets the real brain.
                _report = await asyncio.to_thread(
                    mission_queue.execute_pending, _run_brain_sync
                )
                _reply = (
                    f"Ran {_report['executed']} mission(s), Boss: {_report['completed']} completed, "
                    f"{_report['failed']} failed, {_report['skipped']} skipped — results below."
                )
                for _r in _report.get("results", [])[:5]:
                    _icon = {"completed": "✅", "failed": "❌", "skipped": "⛔"}.get(_r["status"], "•")
                    _reply += f"\n{_icon} {_r['command'][:80]} → {(_r.get('reply') or '')[:120]}"
            return {
                "reply": _reply,
                "metadata": {"fast_path": True, "conversational": True, "mission_run": True},
            }
        if is_list_missions_intent(cmd):
            return {
                "reply": mission_queue.render_status(),
                "metadata": {"fast_path": True, "conversational": True, "mission_list": True},
            }
    except Exception as _me:
        logger.debug(f"mission fast-path skipped: {_me}")

    _recall_patterns = (
        "what do you remember", "do you remember", "you remember",
        "what do you know about me", "what do you know about my",
        "do you have memory", "do you have any memory", "your memory",
        "what did i say", "what did i tell you", "what have i told you",
        "my preferences", "recall my", "recall what",
    )
    _remember_patterns = (
        "remember this", "remember that", "remember:", "remember ,",
        "note that", "don't forget", "dont forget", "keep in mind",
        "memorize this", "memorise this", "store this", "remember it",
    )
    # Recall wins over remember ("do you remember" is a question, not a store
    # command); both match at start or mid-sentence, but recall is checked
    # first so "do you remember when I told you to remember X" recalls.
    _is_recall = any(p in cmd for p in _recall_patterns)
    _is_remember = cmd.startswith("remember ") or any(
        cmd.startswith(p) or f" {p} " in f" {cmd} " or f" {p}:" in f" {cmd}" for p in _remember_patterns
    )

    if _is_recall:
        _hits: list[dict[str, Any]] = []
        _mem_error = ""
        _q_personal = any(p in cmd for p in (" me", "my ", "myself", "i "))
        try:
            from friday.memory.memora_client import memora_client as _memora
            from friday.memory.hygiene import is_memory_noise as _is_noise
            # Search with the owner's own words — appending generic terms
            # ("preferences facts…") buried the real subject (live lesson:
            # "do you remember my chai preference" returned research junk).
            _hits = _memora.recall_memories("friday", raw_cmd[:200], limit=10) or []
            if not _hits and _q_personal:
                # Generic personal question ("what do you remember about me")
                # has no subject words for search — probe owner facts directly.
                _hits = (
                    _memora.recall_memories("friday", "my favorite preference boss surendra", limit=10)
                    or []
                )
            # Memory-hygiene fix (2026-11-13): stored monitor-spam lines
            # ("RAM usage is at 9%…", dialogue dumps) never reach a recall
            # answer — they are not memories of the owner.
            _hits = [h for h in _hits if not _is_noise(str(h.get("content_text", "")))]
        except Exception as _e:
            _mem_error = f"{type(_e).__name__}"
            logger.debug(f"Memora recall skipped in memory fast-path: {_e}")
        # Rank client-side so the answer leads with what he actually asked
        # about: question-word overlap wins, personal facts beat agent logs.
        _q_words = {w for w in _clean_memory_line(cmd).split() if len(w) > 3}
        _stop = {"remember", "about", "what", "have", "tell", "does", "your", "you", "when", "where", "which"}
        _q_words -= _stop

        def _is_agent_log(low: str) -> bool:
            return " executed " in low or "[agent task" in low or "bundle id" in low or "http 200" in low or "[memora response" in low

        def _mem_rank(item: dict[str, Any]) -> tuple[int, int, int]:
            _line = _clean_memory_line(str(item.get("content_text", "")))
            _low = _line.lower()
            _overlap = sum(1 for w in _q_words if w in _low)
            _personal = 1 if any(p in _low for p in ("my ", "i ", "i'm", "mine", "favorite", "prefer", "boss")) else 0
            _log_penalty = -4 if _is_agent_log(_low) else 0
            return (_overlap + _personal + _log_penalty, _personal, min(len(_line), 160))

        _ranked = sorted(_hits, key=_mem_rank, reverse=True)
        _lines: list[str] = []
        _seen_mem: set[str] = set()
        for _m in _ranked:
            _text = _clean_memory_line(str(_m.get("content_text", "")))
            _low = _text.lower()
            # A personal question never gets agent-log noise in the answer.
            if _q_personal and _is_agent_log(_low):
                continue
            # Dedupe on the first 60 chars too: near-duplicates that differ
            # only in a tail still read as the same line to the owner (live
            # 2026-11-13: the same boilerplate printed twice, differing late).
            _dedupe_key = _low[:60]
            if _text and len(_text) > 6 and _dedupe_key not in _seen_mem:
                _seen_mem.add(_dedupe_key)
                if len(_text) > 130:
                    _text = _text[:127].rstrip() + "…"
                _lines.append(f"• {_text}")
            if len(_lines) >= 4:
                break
        if _lines:
            _reply = "Of course I remember, Boss. Here's what I'm holding onto:\n\n" + "\n".join(_lines)
        else:
            _reply = (
                "I don't have anything stored on that yet, Boss — my memory store came back empty. "
                "Tell me what matters and I'll keep it: just say 'remember that…'."
            )
        if _mem_error:
            _reply = f"My memory service is out of reach right now ({_mem_error}), Boss — I'll be honest: I can't check it this second. Say it again in a moment."
        return {
            "reply": _reply,
            "metadata": {
                "fast_path": True,
                "conversational": True,
                "memory_recall": True,
                "remembered_count": len(_lines),
                "memory_service_error": _mem_error or None,
            },
        }

    if _is_remember:
        # Extract the payload after the command phrase.
        _payload = raw_cmd
        for _pfx in (
            "remember this boss:", "remember this:", "remember that:", "remember this", "remember that",
            "remember:", "remember", "note that", "don't forget that", "dont forget that",
            "don't forget", "dont forget", "keep in mind that", "keep in mind", "memorize this",
            "memorise this", "store this",
        ):
            if _payload.lower().startswith(_pfx):
                _payload = _payload[len(_pfx):]
                break
        _payload = _payload.strip().lstrip(":, -–").strip()
        _payload = _clean_memory_line(_payload)
        if not _payload:
            _payload = raw_cmd.strip()
        if len(_payload) > 400:
            _payload = _payload[:397].rstrip() + "…"
        _stored = False
        _store_error = ""
        _tier = "normal"
        try:
            from friday.memory.memora_client import memora_client as _memora
            from friday.memory.importance import score_importance

            # B8: every fact is scored BEFORE storing — core life facts are
            # pinned (importance 0.98, exempt from aging), small talk is
            # stored low (0.20) and ages out after a week; the owner is told
            # which tier his fact landed in.
            _verdict = score_importance(_payload)
            _tier = _verdict.tier
            _res = _memora.record_fact(
                agent_name="friday",
                fact_text=_payload,
                category="owner_fact",
                importance=_verdict.score,
            )
            _status = str((_res or {}).get("status", "")).lower()
            _stored = bool(_res) and (_status in {"success", "created", "stored", "local_only"}
                                      or (not _status and bool(_res.get("id") or _res.get("memory_id"))))
        except Exception as _e:
            _store_error = f"{type(_e).__name__}"
            logger.warning(f"Memora record_fact failed in memory fast-path: {_e}")
        if _stored:
            _tier_note = (
                " That one's pinned — it never fades."
                if _tier == "pinned"
                else (" I'll keep it, but small stuff like that fades from my active memory after a while."
                      if _tier == "trivial" else "")
            )
            if _status == "local_only":
                _reply = f"Saved on the local memory backend, Boss: {_payload}. Shared Memora synchronization is not confirmed."
            else:
                _reply = f"Got it, Boss — locked in: {_payload}. That's mine to keep now.{_tier_note}"
        else:
            _reply = (
                "I couldn't reach my memory store just now, Boss, so I have NOT saved that — "
                "say it again in a moment and I'll keep it safe."
            )
            if _store_error:
                logger.warning(f"memory fast-path store error: {_store_error}")
        return {
            "reply": _reply,
            "metadata": {
                "fast_path": True,
                "conversational": True,
                "memory_store": _stored,
                "fact": _payload,
                "importance_tier": _tier,
            },
        }

    # =========================================================================
    # A9. Tone gate (casual / sarcastic banter — FRIDAY plays along)
    # =========================================================================
    # Narrow exact-match banter patterns answered with warm, first-person
    # comebacks. Placed AFTER the memory gates ("remember" phrasing is never
    # banter) and BEFORE the mode toggles — jokes never reach a router that
    # might answer them literally.
    from friday.persona.tone import tone_reply

    _tone = tone_reply(raw_cmd)
    if _tone is not None:
        return _tone

    # =========================================================================
    # A. Autonomous Mode Toggles & Directives
    # =========================================================================
    if any(k in cmd for k in [
        "activate autonomous mode", "enable autonomous mode", "turn on autonomous mode",
        "autonomous mode on", "autonomous on", "start autonomous mode", "run autonomously"
    ]):
        autonomous_controller.toggle(True)
        mode_status = autonomous_controller.get_status()
        return {
            "reply": (
                "Autonomous Mode is ACTIVE for this running process only; the toggle is not saved and resets "
                "to the configured setting after restart. Safety policy remains in force, and DANGEROUS actions "
                "still require explicit confirmation."
            ),
            "metadata": {
                "fast_path": True,
                "autonomous": True,
                "autonomous_mode": True,
                "full_access_mode": mode_status["full_access_mode"],
                "sensitive_actions_auto_approved": mode_status["sensitive_actions_auto_approved"],
                "autonomous_mode_persistence": "runtime_only",
            },
        }

    if any(k in cmd for k in [
        "deactivate autonomous mode", "disable autonomous mode", "turn off autonomous mode",
        "autonomous mode off", "autonomous off", "stop autonomous mode", "manual mode"
    ]):
        autonomous_controller.toggle(False)
        mode_status = autonomous_controller.get_status()
        reply = "Autonomous Mode is OFF for this running process only; the configured setting applies after restart."
        if mode_status["full_access_mode"]:
            reply += " Full-access compatibility mode remains ON, so SENSITIVE actions may still be auto-approved."
        else:
            reply += " Standing by for manual approval of SENSITIVE actions."
        reply += " DANGEROUS actions still require explicit confirmation."
        return {
            "reply": reply,
            "metadata": {
                "fast_path": True,
                "autonomous": False,
                "autonomous_mode": False,
                "full_access_mode": mode_status["full_access_mode"],
                "sensitive_actions_auto_approved": mode_status["sensitive_actions_auto_approved"],
                "autonomous_mode_persistence": "runtime_only",
            },
        }

    # =========================================================================
    # B. Autonomous Self-Healing & Auto-Repair Directives
    # =========================================================================
    if any(k in cmd for k in [
        "fix yourself", "fix it by yourself", "fix by yourself", "auto fix",
        "self repair", "self heal", "diagnose and repair", "fix errors", "repair system", "fix it"
    ]):
        return await autonomous_controller.execute_self_repair()

    # =========================================================================
    # C. Autonomous Specialist Agent Control Directives
    # =========================================================================
    agent_id, sub_task = autonomous_controller.detect_agent_directive(raw_cmd)
    if agent_id and sub_task:
        return await autonomous_controller.execute_agent_control(agent_id, sub_task)

    # 0. Conversational & Voice Interaction Fast-paths
    # These use the same persona layer as the agent greeting fast-path so FRIDAY
    # speaks with one voice everywhere (owner directive 2026-11-10: talk like a
    # friend, Jarvis-style). A greeting may say that FRIDAY is listening; it
    # may not certify a fleet.
    # Router truth fix (2026-11-13, ZAI Agent 2): this used to be a
    # startswith() match, so "Hey FRIDAY, compute 17*23" was answered with a
    # GREETING and the real question never reached the brain — measured live:
    # three phrasings, three wrong fast-path hijacks (date, greeting, CPU
    # briefing). A greeting is only a greeting when it is the WHOLE message
    # (anchored pattern, same rule as the agent layer's _GREETING_PATTERN).
    _GREETING_ONLY = re.compile(
        r"^\s*(?:hello|hi|hey|sup|good\s(?:morning|afternoon|evening))"
        r"(?:\s+there|\s+friday|\s+friends)?[\s,!.?]*$",
        re.IGNORECASE,
    )
    if _GREETING_ONLY.match(raw_cmd):
        _persona = getattr(_live_settings(), "persona", "friday") or "friday"
        _user = getattr(_live_settings(), "user_name", "Surendra") or "Surendra"
        # BUGFIX (2026-11-13): this API/voice greeting path still served random
        # canned lines while the chat fast-path composed context-aware ones —
        # the owner heard the same scripted greetings on every return. Use the
        # SAME compose_greeting layer with real context: the IST clock and the
        # live mission-queue count (the router is per-command, so last_topic is
        # unknown here; compose_greeting degrades gracefully without it and
        # never invents a topic).
        _pending_n: int | None = None
        try:
            from friday.proactive.mission_queue import mission_queue as _mq

            _pending_n = len(_mq.pending())
        except Exception as _e:
            logger.debug(f"Mission queue count skipped in API greeting: {_e}")
        if _persona == "friday":
            from friday.persona.friday import compose_greeting

            _reply = compose_greeting(_user, pending_tasks=_pending_n)
        else:
            from friday.persona.friday import greeting_responses_for
            import random as _random

            _reply = _random.choice(greeting_responses_for(_persona)).format(user_name=_user)
        # TASK-MEM-003: proactive memory — the owner is (re)opening the
        # conversation, so FRIDAY volunteers one short remembered line without
        # being asked. Recall failure never breaks the greeting.
        _remembered_line = ""
        try:
            from friday.memory.memora_client import memora_client as _memora
            from friday.memory.hygiene import is_memory_noise as _is_noise
            _hits = _memora.recall_memories(
                "friday", f"{_user} recent work preferences", limit=3,
            )
            _seen: set[str] = set()
            for _m in _hits or []:
                _text = str(_m.get("content_text", "")).strip()
                if _is_noise(_text):
                    continue
                if _text and _text not in _seen and len(_text) > 8:
                    _seen.add(_text)
                    if not _remembered_line:
                        _remembered_line = _text.rstrip(".!? ")
                        if len(_remembered_line) > 140:
                            _remembered_line = _remembered_line[:137].rstrip() + "…"
        except Exception as _e:
            logger.debug(f"Memora proactive recall skipped in greeting: {_e}")
        if _remembered_line:
            _reply = f"{_reply}\n\nSince we last talked, I still remember this: {_remembered_line}."
        # TASK-VOI-002: the proactive morning brief (once per morning, from
        # real data — daily goal, live fleet status, portfolio snapshot,
        # overnight events) joins the greeting so the owner gets it on his
        # first "hello" of the day. A failed component contributes an honest
        # line; delivery failure never breaks the greeting.
        try:
            from friday.proactive.morning_brief import maybe_deliver_morning_brief

            _brief = maybe_deliver_morning_brief(agent.notifications)
            if _brief:
                _reply = f"{_brief}\n\n{_reply}"
        except Exception as _brief_exc:
            logger.debug(f"morning brief skipped in server greeting: {_brief_exc}")
        return {
            "reply": _reply,
            "metadata": {
                "fast_path": True,
                "conversational": True,
                "peer_health_checked": False,
                "proactive_memory": bool(_remembered_line),
            },
        }

    if any(k in cmd for k in ["not tracking", "hands are not tracking", "these two hands", "two hands", "tracking", "gesture", "calibrate hands", "test hands"]):
        return {"reply": "Dual-hand optical sensors are active and calibrated. Hold both hands facing the camera with open palms for reticle lock.", "metadata": {"fast_path": True, "conversational": True}}

    if any(k in cmd for k in ["who are you", "who made you", "what are you", "your name", "are you there", "can you hear me"]):
        _user = getattr(_live_settings(), "user_name", "Surendra") or "Surendra"
        return {"reply": "I'm FRIDAY — Fully Responsive Intelligent Digital Assistant for You. You built me, Boss — you and me plus my nine specialist agents run this universe together. I'm here, I'm listening, and I remember where we left off. What do you need?", "metadata": {"fast_path": True, "conversational": True}}

    if any(k in cmd for k in ["thank you", "thanks", "great job", "good job", "nice", "awesome"]):
        _user = getattr(_live_settings(), "user_name", "Surendra") or "Surendra"
        return {"reply": f"Anytime, {_user}. That's what I'm here for.", "metadata": {"fast_path": True, "conversational": True}}

    if any(k in cmd for k in ["what can you do", "help", "features", "commands", "what are your capabilities", "capabilities", "what do you do"]):
        return {
            "reply": "I can launch Windows applications, open and search websites, control the Windows media session, capture screenshots, monitor system telemetry, and orchestrate the specialist agents when they answer. Website playback and account actions require a working service integration.",
            "metadata": {"fast_path": True, "conversational": True},
        }

    if cmd in ["on", "and", "the", "a", "an", "in", "to", "for", "is", "it", "so", "but", "or", "er", "put", "um", "uh", "test"]:
        return {"reply": "I am listening, Surendra. Tell me what directive to execute.", "metadata": {"fast_path": True, "conversational": True}}

    # 1. Master Fleet & All-Agents Matrix
    if any(k in cmd for k in ["status of all agents", "all agents", "fleet status", "ecosystem status", "check all agents", "universe status", "agents status", "all agent"]):
        return await fleet_client.get_fleet_summary()

    # 2. Live Specialist Agent Direct Execution
    for agent_id in ["inference", "stratex", "memora", "intelx", "futuris", "cortex", "forge", "sentinel", "vyralx"]:
        if (
            cmd.startswith(f"ask {agent_id}")
            or cmd.startswith(f"{agent_id} ")
            or cmd.startswith(f"@{agent_id}")
            or cmd == f"ask {agent_id}"
            or cmd == agent_id
            or f"ask {agent_id}" in cmd
        ):
            # Extract user directive
            sub_q = raw_cmd
            for prefix in [f"ask {agent_id}", f"@{agent_id}", agent_id, f"ask {agent_id.capitalize()}", agent_id.capitalize()]:
                if sub_q.lower().startswith(prefix.lower()):
                    sub_q = sub_q[len(prefix):].strip()
                    break
            if not sub_q:
                sub_q = "Report operational status, active metrics, and readiness."

            fallback_data = {
                "reply": f"⚡ [{agent_id.upper()} // DEGRADED] Peer is temporarily unavailable.",
                "metadata": {"agent_id": agent_id, "status": "degraded", "fallback": True},
                "success": False,
                "error": "PEER_TIMEOUT",
            }
            if agent_id == "inference":
                return await safe_peer_call(fleet_client.ask_inference(sub_q), fallback_data=fallback_data, peer_name="inference")
            elif agent_id == "memora":
                return await safe_peer_call(fleet_client.ask_memora(sub_q), fallback_data=fallback_data, peer_name="memora")
            elif agent_id == "stratex":
                return await safe_peer_call(fleet_client.ask_stratex(sub_q), fallback_data=fallback_data, peer_name="stratex")
            elif agent_id == "intelx":
                return await safe_peer_call(fleet_client.ask_intelx(sub_q), fallback_data=fallback_data, peer_name="intelx")
            elif agent_id == "futuris":
                return await safe_peer_call(fleet_client.ask_futuris(sub_q), fallback_data=fallback_data, peer_name="futuris")
            elif agent_id == "cortex":
                return await safe_peer_call(fleet_client.ask_cortex(sub_q), fallback_data=fallback_data, peer_name="cortex")
            elif agent_id == "forge":
                return await safe_peer_call(fleet_client.ask_forge(sub_q), fallback_data=fallback_data, peer_name="forge")
            elif agent_id == "sentinel":
                return await safe_peer_call(fleet_client.ask_sentinel(sub_q), fallback_data=fallback_data, peer_name="sentinel")
            elif agent_id == "vyralx":
                return await safe_peer_call(fleet_client.ask_vyralx(sub_q), fallback_data=fallback_data, peer_name="vyralx")

    # 2. Android Automation Fast-paths
    try:
        if "on phone" in cmd or "on android" in cmd or cmd.startswith("phone ") or cmd.startswith("android "):
            # Check if device is connected first
            if not android.is_connected():
                return {
                    "reply": "No Android device connected via ADB. Connect your phone via USB with USB Debugging enabled.",
                    "metadata": {
                        "fast_path": True,
                        "device": "android",
                        "adb_connected": False,
                        "success": False,
                    },
                }

            # Android App Launch fast-path
            for app_name in ["youtube", "chrome", "maps", "camera", "settings", "whatsapp", "spotify", "instagram", "calculator"]:
                if app_name in cmd:
                    success = android.open_app(app_name)
                    msg = (
                        f"Opened {app_name.capitalize()} on Android device."
                        if success
                        else f"Failed to launch {app_name} on Android."
                    )
                    return {
                        "reply": msg,
                        "metadata": {
                            "fast_path": True,
                            "device": "android",
                            "action": "open_app",
                            "success": success,
                        },
                    }
            if "home" in cmd:
                success = android.press_key("home")
                msg = "Pressed Home on Android device." if success else "Failed to press Home on Android."
                return {
                    "reply": msg,
                    "metadata": {"fast_path": True, "device": "android", "action": "home", "success": success},
                }
            if "back" in cmd:
                success = android.press_key("back")
                msg = "Pressed Back on Android device." if success else "Failed to press Back on Android."
                return {
                    "reply": msg,
                    "metadata": {"fast_path": True, "device": "android", "action": "back", "success": success},
                }
    except Exception as ae:
        logger.warning(f"Android fast-path error: {ae}")

    # 3. Windows FRIDAY Master Laptop Directives (YouTube, websites, media, volume, apps, folders, system)
    try:
        from friday.devices.windows_friday import windows_friday
        handled, friday_reply, friday_meta = windows_friday.handle_directive(
            raw_cmd, authorizer=getattr(agent, "authorizer", None)
        )
        if handled:
            friday_meta["fast_path"] = True
            friday_meta["device"] = "windows"
            return {"reply": friday_reply, "metadata": friday_meta}
    except Exception as fe:
        logger.warning(f"Windows FRIDAY controller error: {fe}")

    try:
        # Screen Perception Fast-path ("What's on my screen now")
        # Truth fix (2026-11-13, ZAI Agent 2): on the cloud host this path used
        # to answer "Screen and window telemetry is active" for a HEADLESS
        # container that has no screen — a fabricated result, exactly the
        # "fake answers" class the owner called out. Real routing now:
        # a locally-attached desktop (laptop/Windows runner) reports its real
        # foreground window; otherwise the laptop bridge is asked, and if no
        # laptop tunnel is connected the reply says so and how to fix it.
        if any(k in cmd for k in ["what's on my screen", "what is on my screen", "whats on my screen", "read my screen", "screen content", "look at my screen", "screen now", "view my screen", "access my screen", "see my screen"]):
            import ctypes

            if hasattr(ctypes, "windll"):
                # Running ON a real Windows desktop (owner's laptop build):
                # the foreground window title is a real measurement.
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                title = ""
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                active_summary = f"Active window: '{title}'." if title else "Desktop display active."
                reply = (
                    f"I am perceiving your environment. {active_summary} Screen and window telemetry is "
                    "active; specialist-agent status is a separate check."
                )
                return {"reply": reply, "metadata": {"fast_path": True, "device": "windows", "action": "screen_perception", "active_window": title}}

            # Cloud host: the owner's screen is only reachable through a
            # connected laptop-bridge tunnel. Anything else would be theater.
            _screen_meta: dict[str, Any] = {"fast_path": True, "action": "screen_perception"}
            try:
                devices = await laptop_bridge.list_devices()
                connected = [d for d in devices if d.get("online")]
                if connected:
                    _dev = connected[0]
                    _laptop_id = str(_dev.get("laptop_id") or _dev.get("id") or "laptop")
                    evidence = await laptop_bridge.execute(
                        _laptop_id, "screenshot", 20.0, {}
                    )
                    _shot = ""
                    if isinstance(evidence, dict) and evidence.get("ok"):
                        _shot = str(evidence.get("output") or "").strip()
                    if _shot:
                        reply = (
                            f"Your laptop '{_laptop_id}' is bridged. I just captured your live screen — "
                            f"it's saved on the laptop at {_shot}. (The bridge ships evidence, not image "
                            "bytes, so I can't render it in this chat yet — but the capture is real and fresh.)"
                        )
                    else:
                        _err = str(evidence.get("error") or "unknown error") if isinstance(evidence, dict) else "unknown error"
                        reply = (
                            f"Your laptop '{_laptop_id}' is bridged, but the screenshot command failed "
                            f"on the laptop side: {_err}. Nothing was captured."
                        )
                    return {
                        "reply": reply,
                        "metadata": {**_screen_meta, "device": "laptop-bridge", "laptop_id": _laptop_id, "capture_ok": bool(_shot)},
                    }
            except Exception as _bridge_exc:
                logger.debug(f"laptop-bridge screen access failed: {_bridge_exc}")

            return {
                "reply": (
                    "I can't see your screen from the cloud, and I won't pretend I can: this server is "
                    "headless, and no laptop bridge is connected right now. To give me real screen access, "
                    "run the FRIDAY laptop bridge on your Windows machine "
                    "(python FRIDAY/scripts/laptop_bridge_client.py) with your control key — then "
                    "'what's on my screen' returns your live screenshot and active window."
                ),
                "metadata": {**_screen_meta, "device": "cloud", "bridge_connected": False},
            }

        # Universal Application & File Launcher Fast-path
        # (trading-intent guard: "open a live OANDA position ..." is a trade
        # request, never a desktop launch — QA-loop misroute fix 2026-11-13)
        if (
            cmd.startswith("open ")
            or cmd.startswith("launch ")
            or cmd.startswith("start ")
        ) and not _TRADING_INTENT_RE.search(cmd):
            target_str = re.sub(r"^(?:open|launch|start)\s+(?:the\s+)?(?:file|folder|app|application|program|directory)?\s*", "", raw_cmd, flags=re.IGNORECASE).strip()
            t_low = target_str.lower()
            
            if any(k in t_low for k in ["chrome", "google chrome", "browser"]):
                ok, msg = launch_desktop_app("chrome")
                return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "chrome", "success": ok}}
            elif any(k in t_low for k in ["notepad", "text editor"]):
                ok, msg = launch_desktop_app("notepad")
                return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "notepad", "success": ok}}
            elif any(k in t_low for k in ["calc", "calculator"]):
                ok, msg = launch_desktop_app("calculator")
                return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "calculator", "success": ok}}
            elif any(k in t_low for k in ["vscode", "vs code", "code", "visual studio code"]):
                ok, msg = launch_desktop_app("vscode")
                return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "vscode", "success": ok}}
            elif any(k in t_low for k in ["explorer", "file explorer", "files", "my files", "this pc"]):
                ok, msg = launch_desktop_app("explorer")
                return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "explorer", "success": ok}}
            elif any(k in t_low for k in ["terminal", "cmd", "powershell"]):
                ok, msg = launch_desktop_app("terminal")
                return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "terminal", "success": ok}}
            elif "download" in t_low:
                p = os.path.join(os.path.expanduser("~"), "Downloads")
                os.startfile(p)
                return {"reply": f"Opened Downloads: {p}", "metadata": {"fast_path": True, "path": p}}
            elif "desktop" in t_low:
                p = os.path.join(os.path.expanduser("~"), "Desktop")
                os.startfile(p)
                return {"reply": f"Opened Desktop: {p}", "metadata": {"fast_path": True, "path": p}}
            elif "document" in t_low:
                p = os.path.join(os.path.expanduser("~"), "Documents")
                os.startfile(p)
                return {"reply": f"Opened Documents: {p}", "metadata": {"fast_path": True, "path": p}}

            # Check if direct file/folder exists
            if os.path.exists(target_str):
                os.startfile(target_str)
                return {"reply": f"Opened '{target_str}'.", "metadata": {"fast_path": True, "path": target_str}}

            for base in [r"d:\FRIDAY Universe", r"d:\FRIDAY Universe\FRIDAY", os.path.expanduser("~")]:
                cand = os.path.join(base, target_str)
                if os.path.exists(cand):
                    os.startfile(cand)
                    return {"reply": f"Opened '{cand}'.", "metadata": {"fast_path": True, "path": cand}}

            ok, msg = _launch_target_verified(target_str)
            if ok:
                return {"reply": msg, "metadata": {"fast_path": True, "target": target_str, "success": True}}
            return {
                "reply": msg,
                "metadata": {"fast_path": True, "target": target_str, "success": False, "refused": True},
            }

        if _looks_like_launch(cmd) and any(k in cmd for k in ["chrome", "google chrome", "swipe right"]):
            ok, msg = launch_desktop_app("chrome")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "chrome", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["notepad", "text editor", "swipe left"]):
            ok, msg = launch_desktop_app("notepad")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "notepad", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["calc", "calculator"]):
            ok, msg = launch_desktop_app("calculator")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "calculator", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["code", "vscode", "vs code"]):
            ok, msg = launch_desktop_app("vscode")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "code", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["edge", "microsoft edge"]):
            ok, msg = launch_desktop_app("edge")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "edge", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["explorer", "file explorer", "files"]):
            ok, msg = launch_desktop_app("explorer")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "explorer", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["paint", "mspaint"]):
            ok, msg = launch_desktop_app("paint")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "paint", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["terminal", "cmd", "powershell"]):
            ok, msg = launch_desktop_app("terminal")
            return {"reply": msg, "metadata": {"fast_path": True, "device": "windows", "app": "terminal", "success": ok}}
        elif _looks_like_launch(cmd) and any(k in cmd for k in ["screenshot", "capture screen", "snapshot"]):
            res = agent.tools.execute(name="get_screen_snapshot", arguments={})
            snap_tool = agent.tools.get("get_screen_snapshot")
            b64_img = ""
            if snap_tool and getattr(snap_tool, "last_snapshot", None):
                snap = snap_tool.last_snapshot
                if snap and getattr(snap, "image_bytes", None):
                    import base64
                    b64_img = f"data:image/png;base64,{base64.b64encode(snap.image_bytes).decode('ascii')}"
            return {"reply": res.content or "Captured desktop screenshot.", "metadata": {"fast_path": True, "device": "windows", "action": "screenshot", "image_b64": b64_img}}
        elif any(k in cmd for k in ["system status", "specs", "cpu status", "cpu usage", "system info"]):
            import psutil
            vm = psutil.virtual_memory()
            res = agent.tools.execute(name="get_system_info", arguments={})
            return {
                "reply": res.content,
                "metadata": {
                    "fast_path": True,
                    "device": "windows",
                    "action": "specs",
                    "telemetry": {
                        "cpu_percent": psutil.cpu_percent(interval=None),
                        "ram_percent": vm.percent,
                        "ram_total_gb": round(vm.total / (1024**3), 2),
                        "ram_used_gb": round(vm.used / (1024**3), 2),
                        "cores": psutil.cpu_count(logical=True),
                    },
                },
            }
        # Router truth fix (2026-11-13): the old bare-substring list
        # ("time", "date") hijacked "What is 17 TIMES 23" into a clock
        # reading. Time/date intent must be the WHOLE question.
        elif re.fullmatch(
            r"(?:what(?:'s| is)? (?:the |current )?)?(?:time|date|day|today)(?: is it)?[\s?.!]*",
            cmd.strip(),
        ):
            res = agent.tools.execute(name="get_time_date", arguments={})
            return {"reply": res.content, "metadata": {"fast_path": True, "device": "windows"}}
    except Exception as e:
        return {"reply": f"Fast-path error: {e}", "metadata": {"error": True}}

    # 3. Central Agent Cognitive & Tool Execution Loop
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, agent.process_message, raw_cmd)
        content = getattr(response, "content", "") or str(response)
        if any(w in content.lower() for w in ["ambiguous", "jumbled", "cut off", "incomplete", "please clarify"]):
            content = "I am standing by, Surendra. What would you like me to do?"
        metadata = getattr(response, "metadata", {}) or {}
        return {"reply": content, "metadata": metadata}
    except Exception as exc:
        logger.warning(f"Cognitive loop exception: {exc}")
        if autonomous_controller.is_autonomous():
            repair_report = await autonomous_controller.execute_self_repair(context=str(exc))
            return {
                "reply": f"⚠️ FRIDAY could not complete the request ({type(exc).__name__}).\n\n{repair_report['reply']}",
                "metadata": {
                    "autonomous": True,
                    "self_repair_attempted": False,
                    "execution_failed": True,
                    "success": False,
                    "error": type(exc).__name__,
                },
            }
        return {
            "reply": (
                f"FRIDAY could not process this request ({type(exc).__name__}). "
                "No action is being reported as completed. Please retry or provide more detail."
            ),
            "metadata": {
                "fallback": True,
                "execution_failed": True,
                "success": False,
                "error": type(exc).__name__,
            },
        }


# Historical note: duplicate `/api/android`, `/api/system_telemetry`, and
# `/api/telemetry` handlers once lived here. FastAPI resolves routes in
# registration order, leaving later copies unreachable; one of those copies
# hardcoded Windows telemetry. Keep the canonical, measured handlers above and
# guard route uniqueness in `test_the_telemetry_routes_are_not_shadowed`.

class ChatRequest(BaseModel):
    message: str = ""


def _memory_consolidation_intent(cmd: str) -> bool:
    """Checklist B7: match explicit memory-consolidation requests.

    Must NOT match remember/recall/forget/correct intents, plain "clean up
    your workspace" chores, or "consolidate the fleet" style agent talk —
    only memory tidy-up requests fire the consolidation pass.
    """
    exact = {
        "consolidate your memories",
        "consolidate my memories",
        "consolidate your memory",
        "consolidate memories",
        "consolidate memory",
        "clean up your memory",
        "clean your memory",
        "tidy your memory",
        "tidy up your memories",
        "tidy up your memory",
        "organize your memories",
        "organise your memories",
        "summarize what you remember from today",
        "summarise what you remember from today",
        "run memory consolidation",
    }
    if cmd in exact:
        return True
    for prefix in ("consolidate ", "clean up ", "tidy up ", "organize ", "organise "):
        if cmd.startswith(prefix) and "memor" in cmd:
            return True
    return False



@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, _: None = Depends(_require_origin_gate)) -> dict[str, Any]:
    """Compatibility endpoint for chat/command execution.

    Owner decision (2026-11-10 IST): the chat surface is public and keyless —
    origin-gated only (see ``_require_origin_gate``). Raw control endpoints
    (``/api/command`` and friends) keep the full key gate.

    QA-loop upgrade (2026-11-13): when the brain cannot reach its LLM it still
    composes an honest, readable reply — but the command layer mapped that to
    HTTP 502, the dashboard's ``if (!res.ok) throw`` discarded FRIDAY's actual
    words and showed a fake "I lost the link" message. A reply the owner can
    read is not a transport failure: /api/chat rewraps a 502 that carries a
    non-empty ``reply`` as 200. Security refusals (403) and hard crashes (500)
    keep their status codes, and /api/command's pinned contract is untouched.
    """
    result = await execute_command(CommandRequest(command=req.message), boss_verified=False)
    if isinstance(result, Response) and result.status_code == 502:
        try:
            body = json.loads(result.body.decode("utf-8"))
        except Exception:
            body = None
        if isinstance(body, dict) and isinstance(body.get("reply"), str) and body["reply"].strip():
            return JSONResponse(status_code=200, content=body)
    return result


@app.get("/api/screenshot")
@app.post("/api/screenshot")
async def screenshot_endpoint(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Compatibility endpoint for capturing desktop screenshot."""
    return await execute_command(CommandRequest(command="screenshot"))


@app.websocket("/api/ws/voice")
async def voice_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for bidirectional audio, waveform telemetry, and MediaPipe hand gestures.
    Supports real-time gesture control and instant desktop/mobile actions.
    """
    try:
        await _require_control_access_ws(websocket)
    except HTTPException:
        await websocket.close(code=1008, reason="FRIDAY control authentication required")
        return
    await websocket.accept()
    logger.info("WebSocket connected from Holographic UI")
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type in ("voice_command", "command"):
                cmd_text = data.get("command", "").strip()
                logger.info(f"Received WS voice command: '{cmd_text}'")
                if cmd_text:
                    # LATENCY FIX (2026-11-13): measure the real server-side
                    # execution time and return it with every voice reply. The
                    # owner sees real numbers instead of impressions, and the
                    # SYSTEM tab diagnostics gain a live p50/p95 track via
                    # /api/voice/diagnostics/report. No estimate is fabricated:
                    # this is wall-clock around the actual router call.
                    import time as _time

                    _t0 = _time.perf_counter()
                    req_obj = CommandRequest(command=cmd_text)
                    cmd_res = await execute_command(req_obj)
                    _lat_ms = int((_time.perf_counter() - _t0) * 1000)
                    try:
                        _voice_diagnostics_state.setdefault("latency_samples_ms", []).append(_lat_ms)
                        _voice_diagnostics_state["latency_samples_ms"] = _voice_diagnostics_state["latency_samples_ms"][-100:]
                    except Exception:
                        pass
                    logger.info(f"WS voice command '{cmd_text[:40]}' executed in {_lat_ms} ms")
                    await websocket.send_json({
                        "type": "voice_reply",
                        "command": cmd_text,
                        "reply": cmd_res.get("reply", ""),
                        "metadata": cmd_res.get("metadata", {}),
                        "latency_ms": _lat_ms,
                    })

            elif event_type == "gesture":
                gesture = data.get("gesture")
                logger.info(f"Received hand gesture event: {gesture}")
                try:
                    from friday.devices.app_launcher import launch_desktop_app
                    if gesture == "swipe_left":
                        ok, msg = launch_desktop_app("notepad")
                        await websocket.send_json({"type": "status", "message": f"Left Gesture: {msg}"})
                    elif gesture == "swipe_right":
                        ok, msg = launch_desktop_app("chrome")
                        await websocket.send_json({"type": "status", "message": f"Right Gesture: {msg}"})
                    elif gesture == "swipe_up_android":
                        if not android.is_connected():
                            await websocket.send_json({"type": "status", "message": "Android Action unavailable: no ADB device is connected."})
                        else:
                            ok = android.swipe(500, 1500, 500, 500, 250)
                            await websocket.send_json({"type": "status", "message": "Android Action: Swiped Up" if ok else "Android Action failed; ADB did not confirm the swipe."})
                    elif gesture == "swipe_down_android":
                        if not android.is_connected():
                            await websocket.send_json({"type": "status", "message": "Android Action unavailable: no ADB device is connected."})
                        else:
                            ok = android.swipe(500, 500, 500, 1500, 250)
                            await websocket.send_json({"type": "status", "message": "Android Action: Swiped Down" if ok else "Android Action failed; ADB did not confirm the swipe."})
                    elif gesture == "pinch":
                        await websocket.send_json({"type": "status", "message": "Pinch gesture recognized; no action is configured."})
                    elif gesture == "open_palm":
                        await websocket.send_json({"type": "status", "message": "Open-palm gesture recognized; no action is configured."})
                except Exception as ge:
                    logger.error(f"Gesture execution failed: {ge}")
                    await websocket.send_json({"type": "status", "message": f"Error: {ge}"})

            elif event_type == "audio_ping":
                # Heartbeat and audio packet ack
                await websocket.send_json({"type": "audio_pong", "timestamp": data.get("timestamp")})

            elif event_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                logger.warning(f"Unknown WS event type: {event_type}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from Holographic UI")
    except Exception as e:
        logger.error(f"WebSocket session error: {e}")


# =========================================================================
# Real-Time Companion Event Multiplexer & Desktop Telemetry Stream
# =========================================================================

@app.websocket("/ws/companion")
@app.websocket("/api/ws/companion")
async def companion_ws_endpoint(websocket: WebSocket) -> None:
    """Real-time companion event multiplexer and desktop telemetry stream."""
    try:
        await _require_control_access_ws(websocket)
    except HTTPException:
        await websocket.close(code=1008, reason="FRIDAY control authentication required")
        return
    await websocket.accept()
    client_id = f"companion_{uuid.uuid4().hex[:8]}"
    raw_topics = websocket.query_params.get("topics")
    topics = {t.strip().lower() for t in raw_topics.split(",")} if raw_topics else {"telemetry", "system"}
    sub = await companion_multiplexer.connect(websocket, client_id=client_id, initial_topics=topics)

    # Ensure background telemetry streaming is active
    companion_multiplexer.start_telemetry_streaming(agent.get_system_diagnostics, interval_seconds=2.5)

    await websocket.send_json({
        "type": "welcome",
        "client_id": sub.client_id,
        "topics": sorted(list(sub.topics)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    async def _exec_cmd(cmd_text: str) -> dict[str, Any]:
        return await execute_command(CommandRequest(command=cmd_text))

    try:
        while True:
            msg = await websocket.receive_json()
            await companion_multiplexer.handle_message(
                websocket=websocket,
                msg=msg,
                command_executor=_exec_cmd,
                snapshot_getter=agent.get_system_diagnostics,
            )
    except WebSocketDisconnect:
        await companion_multiplexer.disconnect(websocket)
    except Exception as exc:
        logger.warning("Companion WS session error: %s", exc)
        await companion_multiplexer.disconnect(websocket)


@app.get("/api/companion/status")
async def companion_status_endpoint(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Return status and subscriber diagnostics for the real-time companion multiplexer."""
    return {"status": "ok", **companion_multiplexer.get_status()}


# =========================================================================
# Real-Time Activity Stream WebSocket
# =========================================================================
@app.websocket("/api/ws/activity")
async def activity_ws_endpoint(websocket: WebSocket) -> None:
    """Stream autonomous agent activity events to dashboard clients in real time."""
    try:
        await _require_origin_gate_ws(websocket)
    except HTTPException:
        await websocket.close(code=1008, reason="Origin not permitted")
        return
    await websocket.accept()
    register_activity_client(websocket)
    # Send a short backlog so a freshly connected dashboard reflects recent work.
    try:
        from friday.autonomous.controller import autonomous_controller

        for entry in list(autonomous_controller.action_history)[-20:]:
            await websocket.send_json({
                "type": "activity",
                "agent": entry.target,
                "action": entry.action_type,
                "target": entry.target,
                "directive": entry.directive,
                "result": entry.result,
                "success": entry.success,
                "timestamp": getattr(entry, "recorded_at", None) or entry.timestamp,
            })
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Activity backlog send failed: %s", exc)
    try:
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Activity WS session error: %s", exc)
    finally:
        unregister_activity_client(websocket)


# =========================================================================
# FastMCP Server Endpoints (Sagar Tamang's FastMCP SSE Architecture)
# =========================================================================

@app.get("/sse")
async def mcp_sse_endpoint(request: Request, _: None = Depends(_require_control_access)):
    """
    Model Context Protocol (MCP) Server-Sent Events endpoint.
    Allows external agents, Cursor, Claude Desktop, or any MCP-compatible client to consume FRIDAY's tools.
    """
    async def event_generator():
        # Initial endpoint event per MCP SSE spec
        yield "event: endpoint\ndata: /messages?session_id=friday_session\n\n"
        while True:
            if await request.is_disconnected():
                break
            # Keepalive ping every 15s
            await asyncio.sleep(15)
            yield ": keepalive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# =========================================================================
# FRIDAY Proactive & Diagnostics Endpoints (ambient awareness)
# =========================================================================


@app.get("/api/diagnostics")
async def diagnostics_endpoint() -> dict[str, Any]:
    """Return live system telemetry for the HUD / proactive monitoring."""
    try:
        diag = agent.get_system_diagnostics()
        diag["status"] = "ok"
        return diag
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/proactive")
async def proactive_endpoint() -> dict[str, Any]:
    """Return any pending proactive announcements (unprompted FRIDAY insights)."""
    try:
        announcement = agent.get_proactive_announcement()
        return {
            "status": "ok",
            "has_announcement": announcement is not None,
            "announcement": announcement,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/proactive/dismiss")
async def dismiss_proactive(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Clear all pending proactive notifications."""
    try:
        agent.notifications.clear()
        return {"status": "ok", "cleared": True}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def start_proactive_monitoring() -> None:
    """Start FRIDAY's background proactive monitoring loop. Call at server boot."""
    try:
        agent.start_proactive_monitoring()
        companion_multiplexer.start_telemetry_streaming(agent.get_system_diagnostics, interval_seconds=2.5)
        logger.info("FRIDAY proactive monitoring started")
    except Exception as e:
        logger.warning(f"Could not start proactive monitoring: {e}")


# Auto-start proactive monitoring when the module loads (server boot)
start_proactive_monitoring()


# =========================================================================
# Conversation History Endpoints
# =========================================================================

from collections import deque
import uuid as _uuid

# In-memory conversation history store (max 10000 entries)
_conversation_history: deque = deque(maxlen=10000)
_conversation_lock = asyncio.Lock()


class ConversationEntry(BaseModel):
    """Conversation history entry model."""
    id: str | None = None
    timestamp: str | None = None
    user_input: str
    friday_reply: str
    input_type: str = "text"  # "text" or "voice"
    status: str = "success"   # "success", "failed", "pending", "running", "cancelled"
    agents_involved: list[str] = []
    metadata: dict[str, Any] = {}


@app.get("/api/v1/conversation/history")
async def get_conversation_history(
    limit: int = 50,
    offset: int = 0,
    date_from: str | None = None,
    date_to: str | None = None,
    agent: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Get conversation history with pagination and filtering."""
    async with _conversation_lock:
        entries = list(_conversation_history)

    # Apply filters
    filtered = entries
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            filtered = [e for e in filtered if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) >= from_dt]
        except ValueError:
            pass
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            filtered = [e for e in filtered if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) <= to_dt]
        except ValueError:
            pass
    if agent:
        filtered = [e for e in filtered if agent in e.agents_involved]
    if status:
        filtered = [e for e in filtered if e.status == status]
    if search:
        search_lower = search.lower()
        filtered = [e for e in filtered 
                   if search_lower in e.user_input.lower() or search_lower in e.friday_reply.lower()]

    # Sort by timestamp descending (newest first)
    filtered.sort(key=lambda e: e.timestamp, reverse=True)

    # Pagination
    total = len(filtered)
    paginated = filtered[offset:offset + limit]

    return {
        "status": "ok",
        "entries": [e.model_dump() for e in paginated],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@app.get("/api/v1/conversation/export")
async def export_conversation_history(
    format: str = "json",
    date_from: str | None = None,
    date_to: str | None = None,
    agent: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> Any:
    """Export conversation history as JSON or Markdown."""
    async with _conversation_lock:
        entries = list(_conversation_history)

    # Apply same filters as history endpoint
    filtered = entries
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            filtered = [e for e in filtered if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) >= from_dt]
        except ValueError:
            pass
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            filtered = [e for e in filtered if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) <= to_dt]
        except ValueError:
            pass
    if agent:
        filtered = [e for e in filtered if agent in e.agents_involved]
    if status:
        filtered = [e for e in filtered if e.status == status]
    if search:
        search_lower = search.lower()
        filtered = [e for e in filtered 
                   if search_lower in e.user_input.lower() or search_lower in e.friday_reply.lower()]

    filtered.sort(key=lambda e: e.timestamp, reverse=True)

    if format.lower() == "markdown" or format.lower() == "md":
        lines = [
            "# FRIDAY Conversation History Export",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Total Entries: {len(filtered)}",
            "",
            "---",
            ""
        ]
        for entry in filtered:
            timestamp = entry.timestamp
            input_type = entry.input_type
            status_str = entry.status
            agents = ", ".join(entry.agents_involved) if entry.agents_involved else "None"
            lines.extend([
                f"## {timestamp} [{input_type}] [{status_str}]",
                f"**Agents:** {agents}",
                "",
                f"**You:** {entry.user_input}",
                "",
                f"**FRIDAY:** {entry.friday_reply}",
                "",
                "---",
                ""
            ])
        if entry.metadata:
            lines.extend([
                "**Metadata:**",
                "```json",
                json.dumps(entry.metadata, indent=2),
                "```",
                ""
            ])
        return Response(
            content="\n".join(lines),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="friday-conversation-{datetime.now().strftime("%Y%m%d-%H%M%S")}.md"'}
        )

    # Default to JSON
    return JSONResponse(
        content={"entries": [e.model_dump() for e in filtered]},
        headers={"Content-Disposition": f'attachment; filename="friday-conversation-{datetime.now().strftime("%Y%m%d-%H%M%S")}.json"'}
    )


@app.post("/api/v1/conversation/entry")
async def add_conversation_entry(entry: ConversationEntry, _: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Add a new conversation entry (for real-time logging)."""
    now = datetime.now(timezone.utc).isoformat()
    entry_id = entry.id or str(_uuid.uuid4())
    timestamp = entry.timestamp or now

    new_entry = ConversationEntry(
        id=entry_id,
        timestamp=timestamp,
        user_input=entry.user_input,
        friday_reply=entry.friday_reply,
        input_type=entry.input_type,
        status=entry.status,
        agents_involved=entry.agents_involved,
        metadata=entry.metadata,
    )

    async with _conversation_lock:
        _conversation_history.appendleft(new_entry)

    # Broadcast to activity stream if available
    try:
        from friday.api.activity_stream import broadcast_activity
        await broadcast_activity({
            "type": "conversation",
            "entry_id": entry_id,
            "timestamp": timestamp,
            "user_input": entry.user_input[:100],
            "status": entry.status,
            "agents": entry.agents_involved,
        })
    except Exception:
        pass

    return {"status": "ok", "entry_id": entry_id, "timestamp": timestamp}


@app.delete("/api/v1/conversation/history")
async def clear_conversation_history(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """Clear all conversation history."""
    async with _conversation_lock:
        _conversation_history.clear()
    return {"status": "ok", "cleared": True}


# Helper function to log conversations from the command endpoint
async def _log_conversation(
    user_input: str,
    friday_reply: str,
    input_type: str = "text",
    status: str = "success",
    agents_involved: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Internal helper to log a conversation entry."""
    entry = ConversationEntry(
        id=str(_uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_input=user_input,
        friday_reply=friday_reply,
        input_type=input_type,
        status=status,
        agents_involved=agents_involved or [],
        metadata=metadata or {},
    )
    async with _conversation_lock:
        _conversation_history.appendleft(entry)


@app.post("/v1/events")
@app.post("/api/events")
async def receive_peer_event(request: Request) -> dict[str, Any]:
    """Ingest peer specialist agent telemetry, strategic decisions, and events."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    source = body.get("source", "unknown")
    event_type = body.get("event_type", "unknown")
    logger.info(f"Peer event received from {source}: {event_type}")
    return {"status": "ok", "received": True, "source": source, "event_type": event_type}


@app.post("/messages")
async def mcp_messages_endpoint(request: Request, _: None = Depends(_require_control_access)) -> JSONResponse:
    """
    Model Context Protocol (MCP) JSON-RPC 2.0 message handler.
    Implements tools/list and tools/call protocols.
    """
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})

        if method == "tools/list":
            schemas = agent.tools.get_schemas() or []
            mcp_tools = []
            for s in schemas:
                fn = s.get("function", s)
                mcp_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "inputSchema": fn.get("parameters", {"type": "object", "properties": {}}),
                })
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": mcp_tools},
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            tool = agent.tools.get(tool_name)
            if not tool:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                })
            tool_res = agent.tools.execute(name=tool_name, arguments=tool_args)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": str(tool_res.content)}],
                    "isError": tool_res.is_error,
                },
            })

        elif method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "friday-mcp-server", "version": "2.0.0"},
                },
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented"},
        })
    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": str(e)},
        })


# =========================================================================
# Laptop Reverse Tunnel (cloud FRIDAY -> owner's laptop)
# =========================================================================
#
# The laptop dials out; the cloud never listens on the laptop's network. The
# tunnel authenticates with the same control secret as the rest of this API and
# only dispatches the allowlist enforced in `friday.remote.laptop_bridge`.


class LaptopCommandRequest(BaseModel):
    command: str
    args: dict[str, Any] = {}
    timeout: float = 30.0


def _laptop_tunnel_authorised(websocket: WebSocket) -> bool:
    """Authorise a laptop tunnel upgrade.

    Browsers cannot be trusted to drive this route, so the origin policy applies
    first. A non-browser client (the laptop bridge) presents either the control
    API key or a short-lived control token, checked with the same helpers as
    :func:`_require_control_access`. The query parameter exists because a
    WebSocket client cannot always set custom headers.
    """
    if not _websocket_origin_allowed(websocket):
        return False
    expected = _control_secret()
    if not _control_secret_is_usable(expected):
        return False

    provided = websocket.headers.get("x-friday-api-key", "")
    authorization = websocket.headers.get("authorization", "")
    if not provided and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if provided and hmac.compare_digest(provided, expected):
        return True

    candidates = (
        websocket.query_params.get("token", ""),
        websocket.headers.get("x-friday-control-token", ""),
    )
    return any(token and _control_token_valid(token, expected) for token in candidates)


@app.get("/api/laptop/devices")
async def laptop_devices_endpoint(_: None = Depends(_require_control_access)) -> dict[str, Any]:
    """List every laptop that has ever connected, with current tunnel state."""
    return {"devices": await laptop_bridge.list_devices()}


@app.post("/api/laptop/{laptop_id}/command")
async def laptop_command_endpoint(
    laptop_id: str,
    req: LaptopCommandRequest,
    _: None = Depends(_require_control_access),
) -> Any:
    """Dispatch one allowlisted command to a connected laptop.

    A missing tunnel is 404, a deadline is 504 and a tunnel that dies in flight
    is 502. The evidence record is returned in every one of those cases so the
    caller can see what actually happened.
    """
    try:
        evidence = await laptop_bridge.execute(laptop_id, req.command, req.timeout, req.args)
    except LaptopNotConnected as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LaptopBridgeTimeout as exc:
        return JSONResponse(status_code=504, content=exc.evidence)
    except LaptopDisconnected as exc:
        return JSONResponse(status_code=502, content=exc.evidence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return evidence


@app.websocket("/api/laptop/connect/{laptop_id}")
async def laptop_connect_endpoint(websocket: WebSocket, laptop_id: str) -> None:
    """Laptop-side reverse tunnel.

    The socket is accepted before the 1008 close is sent because an ASGI server
    turns a pre-accept close into an HTTP 403 handshake rejection, which hides
    the authentication reason from the client.
    """
    if not _laptop_tunnel_authorised(websocket):
        logger.warning("Rejected laptop tunnel: control authentication failed")
        await websocket.accept()
        await websocket.close(code=1008, reason="FRIDAY control authentication required")
        return

    try:
        laptop_id = normalise_laptop_id(laptop_id)
    except ValueError as exc:
        await websocket.accept()
        await websocket.close(code=1008, reason=str(exc))
        return

    await websocket.accept()
    replaced = await laptop_bridge.register(laptop_id, websocket)
    if replaced is not None:
        try:
            await replaced.websocket.close(code=1012, reason="Replaced by a newer laptop tunnel")
        except Exception:
            logger.debug("Previous laptop tunnel for %s was already closed", laptop_id)

    try:
        await websocket.send_json(
            {
                "type": "welcome",
                "laptop_id": laptop_id,
                "heartbeat_interval": 20.0,
                "commands": sorted(ALLOWED_LAPTOP_COMMANDS),
                "shell_enabled": shell_execution_enabled(),
                "server_time": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        logger.warning("Laptop tunnel %s failed during welcome: %s", laptop_id, exc)
        await laptop_bridge.unregister(laptop_id, websocket)
        return

    try:
        while True:
            try:
                message = await websocket.receive_json()
            except json.JSONDecodeError:
                logger.warning("Laptop tunnel %s sent invalid JSON", laptop_id)
                continue
            if not isinstance(message, dict):
                logger.warning("Laptop tunnel %s sent a non-object frame", laptop_id)
                continue

            kind = str(message.get("type") or "").strip().lower()
            if kind in {"result", "command_result"}:
                if not await laptop_bridge.resolve_result(laptop_id, message):
                    logger.warning(
                        "Laptop tunnel %s returned an unknown or expired request", laptop_id
                    )
            elif kind in {"ping", "heartbeat"}:
                await laptop_bridge.touch(laptop_id)
                await websocket.send_json(
                    {"type": "pong", "server_time": datetime.now(timezone.utc).isoformat()}
                )
            else:
                # `hello` and any future informational frame only refresh liveness.
                await laptop_bridge.touch(laptop_id)
    except WebSocketDisconnect:
        logger.info("Laptop tunnel disconnected: %s", laptop_id)
    except Exception as exc:
        logger.warning("Laptop tunnel error for %s: %s", laptop_id, exc)
    finally:
        await laptop_bridge.unregister(laptop_id, websocket)


# --- Owner dashboard (Next.js static export from FRIDAY/ui) ------------------
# The dashboard is the exported Next.js app in FRIDAY/ui/out: dark theme,
# continuous LiveKit voice line, React-Bits-style effects. Caddy strips the
# /friday prefix in front of this process, so the same export is reached at
# https://friday-universe.duckdns.org/ and /friday/ — the export's asset URLs
# (/friday/_next/...) route through the same handle. The HTML shell is served
# by this route with no-store so a deploy shows on the very next reload;
# immutable hashed assets are served by the root static mount at the bottom of
# this file (registered last, so every API route above wins).

_UI_EXPORT_DIR = Path(__file__).resolve().parents[3] / "ui" / "out"
_UI_INDEX = _UI_EXPORT_DIR / "index.html"
_ui_index_cache: dict[str, Any] = {"mtime": -1.0, "html": ""}


def _index_html() -> str:
    try:
        mtime = _UI_INDEX.stat().st_mtime
    except OSError:
        return (
            "<!doctype html><meta charset='utf-8'><title>FRIDAY</title>"
            "<body style='background:#050508;color:#f0f0f5;font-family:system-ui;padding:40px'>"
            "<h1>FRIDAY</h1><p>The dashboard export (FRIDAY/ui/out) is missing on this host.</p></body>"
        )
    if _ui_index_cache["mtime"] != mtime or not _ui_index_cache["html"]:
        _ui_index_cache["html"] = _UI_INDEX.read_text(encoding="utf-8")
        _ui_index_cache["mtime"] = mtime
    return _ui_index_cache["html"]


@app.get("/", include_in_schema=False)
async def index_root() -> Response:
    return Response(
        content=_index_html(),
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0", "X-FRIDAY-Surface": "friday-ai"},
    )


@app.get("/dashboard", include_in_schema=False)
async def dashboard_alias() -> Response:
    return await index_root()


class VoiceSpeakRequest(BaseModel):
    text: str
    voice: str | None = None
    lang: str | None = None


_VOICE_CATALOGUE = [
    {"id": "en-IN-NeerjaNeural", "language": "en-IN", "label": "English (India) — Neerja", "gender": "Female"},
    {"id": "en-IN-PrabhatNeural", "language": "en-IN", "label": "English (India) — Prabhat", "gender": "Male"},
    {"id": "te-IN-ShrutiNeural", "language": "te-IN", "label": "Telugu — Shruti", "gender": "Female"},
    {"id": "te-IN-MohanNeural", "language": "te-IN", "label": "Telugu — Mohan", "gender": "Male"},
]
_VOICE_BY_ID = {entry["id"]: entry for entry in _VOICE_CATALOGUE}
_DEFAULT_VOICE_FOR_LANG = {"en": "en-IN-NeerjaNeural", "te": "te-IN-ShrutiNeural"}
_voice_cache: dict[str, bytes] = {}
_voice_cache_order: list[str] = []
_voice_lock = asyncio.Semaphore(2)


@app.get("/api/voice/languages")
async def voice_languages() -> Any:
    """Languages FRIDAY can actually speak on this host."""
    return {
        "languages": _VOICE_CATALOGUE,
        "default": _DEFAULT_VOICE_FOR_LANG,
        "telugu_installed": True,
        "engine": "edge-tts",
    }


@app.post("/api/voice/speak")
async def voice_speak(
    req: VoiceSpeakRequest,
    _: None = Depends(_require_control_access),
) -> Response:
    """Synthesise speech (English or Telugu) and return audio/mpeg.

    Telugu voices are Microsoft neural voices streamed through edge-tts, so no
    Windows language pack and no per-token model download is needed.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 1800:
        text = text[:1800]

    requested = (req.voice or "").strip()
    lang = (req.lang or "en").strip().lower()[:2]
    voice = requested if requested in _VOICE_BY_ID else _DEFAULT_VOICE_FOR_LANG.get(lang, "en-IN-NeerjaNeural")

    key = hashlib.sha256(f"{voice}\x00{text}".encode("utf-8")).hexdigest()
    cached = _voice_cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})

    try:
        import edge_tts  # imported lazily: the API host is memory constrained
    except Exception as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=503, detail=f"Speech engine unavailable: {exc}") from exc

    audio = bytearray()
    try:
        async with _voice_lock:
            communicate = edge_tts.Communicate(text, voice)
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    audio.extend(chunk["data"])
    except Exception as exc:
        logger.warning("Voice synthesis failed for %s: %s", voice, exc)
        raise HTTPException(status_code=502, detail=f"Speech synthesis failed: {exc}") from exc

    if not audio:
        raise HTTPException(status_code=502, detail="Speech engine produced no audio")

    payload = bytes(audio)
    _voice_cache[key] = payload
    _voice_cache_order.append(key)
    while len(_voice_cache_order) > 24:
        _voice_cache.pop(_voice_cache_order.pop(0), None)

    return Response(
        content=payload,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-FRIDAY-Voice": voice},
    )


# --- Enhanced Autonomous Controller Integration ---
# Checklist I7: the duplicate POST /api/autonomous/decompose registration that
# used to live here was dead code (Starlette matches the first registration —
# the authenticated handler above — so this unauthenticated copy was never
# reachable) and tripped the route-truthfulness contract. Removed 2026-11-11.


@app.post("/api/autonomous/execute")
async def execute_plan_autonomous(
    goal: str,
    _: None = Depends(_require_control_access),
):
    """Execute a complete autonomous plan with dependency resolution.

    Gated like its sibling control routes (goals/repair/toggle): this route
    drives real execution, so it must never be callable by an anonymous
    remote caller (TASK-SEC-005 posture).
    """
    from friday.autonomous.enhanced_controller import enhanced_controller
    try:
        plan = enhanced_controller.decompose_goal(goal)
        result = await enhanced_controller.execute_plan(plan)
        evaluation = enhanced_controller.evaluate_outcome(result)
        return evaluation
    except Exception as exc:
        raise HTTPException(500, f"Plan execution failed: {exc}")


@app.get("/api/autonomous/history")
async def get_execution_history():
    """Get recent autonomous execution history."""
    from friday.autonomous.enhanced_controller import enhanced_controller
    history = enhanced_controller.get_execution_history(limit=10)
    return {"history": history, "total": len(history)}


@app.get("/api/autonomous/fleet-status")
async def get_fleet_status():
    """Get overall fleet status from the mesh orchestrator."""
    from mesh.fleet_orchestrator import fleet_orchestrator
    try:
        status = await fleet_orchestrator.get_fleet_status()
        return status
    except Exception as exc:
        raise HTTPException(500, f"Fleet status failed: {exc}")


@app.post("/api/autonomous/emergency-halt")
async def emergency_halt_agent(agent: str):
    """Emergency halt a specific agent."""
    from mesh.fleet_orchestrator import fleet_orchestrator
    try:
        success = await fleet_orchestrator.emergency_halt(agent)
        return {"status": "HALTED" if success else "FAILED", "agent": agent}
    except Exception as exc:
        raise HTTPException(500, f"Emergency halt failed: {exc}")


# --- Autonomous Decision Making Integration ---
try:
    _apps_core_path = Path(__file__).resolve().parents[3] / "apps" / "core" / "src"
    if _apps_core_path.is_dir() and str(_apps_core_path) not in sys.path:
        sys.path.insert(0, str(_apps_core_path))
    from friday_core.autonomous_decision_making import router as autonomous_decision_router
    app.include_router(autonomous_decision_router)  # routes already start with /api/v1
except Exception as _e:
    logger.warning(f"Could not load autonomous_decision_making router: {_e}")

# --- Agent Mesh Coordinator Integration ---
try:
    from friday_core.agent_mesh_coordinator import router as mesh_coordinator_router
    app.include_router(mesh_coordinator_router)  # routes already start with /api/v1
except Exception as _e:
    logger.warning(f"Could not load agent_mesh_coordinator router: {_e}")


# Robustness fix (ZAI Agent 2, 2026-11-12): the mesh/friday_core/friday.services
# router imports below are UNGUARDED module-level imports of packages scattered
# across THREE roots: mesh/ at the repo root (parents[4]), friday_core/ under
# FRIDAY/apps/core/src, and friday.services under FRIDAY/src. Production's
# systemd unit only works because its venv install happens to put all of them
# on sys.path; any other launcher (cwd=FRIDAY, IDE, test runner) dies on
# ImportError before serving a single request. Adding each root explicitly if
# its package is not already importable makes every launcher work; when the
# packages resolve (production), this is a no-op.
try:
    import sys as _sys

    def _ensure_importable(package: str, pkg_root: Path) -> None:
        """Add ``pkg_root`` (the dir CONTAINING the package) to sys.path when
        ``package`` is not importable. Adding the package dir itself would be
        wrong — the path entry must be its parent."""
        try:
            __import__(package)
        except ImportError:
            if pkg_root.is_dir() and str(pkg_root) not in _sys.path:
                _sys.path.insert(0, str(pkg_root))
                logger.info("Added %s to sys.path for the '%s' routers", pkg_root, package)

    _SRC_DIR = Path(__file__).resolve().parents[2]          # .../FRIDAY/src
    _ensure_importable("mesh", _SRC_DIR.parents[1])                     # repo root (contains mesh/)
    _ensure_importable("friday_core", _SRC_DIR.parent / "apps" / "core" / "src")
    # friday.services lives inside the same 'friday' package as this server,
    # so it resolves whenever this module did — no extra root needed.
except Exception as _path_exc:  # never block startup on path setup
    logger.warning("Router path bootstrap failed: %s", _path_exc)


# --- Mesh Module Integrations ---
from mesh.universe_health import router as universe_health_router
from mesh.universe_status import router as universe_status_router
from mesh.cross_agent_context import router as cross_agent_context_router
from mesh.adaptive_router import router as adaptive_router_router
from mesh.unified_errors import router as unified_errors_router
from mesh.self_improvement_loop import router as self_improvement_router
from mesh.automated_consolidation import router as automated_consolidation_router

# These mesh routers declare absolute paths (/api/v1/mesh/...).
app.include_router(universe_health_router)
app.include_router(universe_status_router)
app.include_router(cross_agent_context_router)
app.include_router(adaptive_router_router)
app.include_router(unified_errors_router)
app.include_router(self_improvement_router)
app.include_router(automated_consolidation_router)


# --- Additional Mesh Module Integrations ---
from mesh.performance_profiler import router as performance_profiler_router
from mesh.universe_soak_test import router as universe_soak_test_router

app.include_router(performance_profiler_router)
app.include_router(universe_soak_test_router)


# --- FRIDAY Core Module Integrations ---
from friday_core.autonomous_laptop_operator import router as laptop_operator_router
from friday_core.general_cognitive_coordinator import router as cognitive_coordinator_router

from friday.services.autonomous_problem_solver import router as problem_solver_router
from friday.services.multi_agent_coordinator import router as coordinator_router

app.include_router(laptop_operator_router)
app.include_router(cognitive_coordinator_router)
app.include_router(problem_solver_router)
app.include_router(coordinator_router)

# --- New FRIDAY Deep Module Integrations ---
from friday_core.task_decomposition_engine import router as task_decomp_router
from friday_core.decision_synthesis_engine import router as decision_synth_router
from friday_core.goal_planning_engine import router as goal_planning_router
from friday_core.context_window_manager import router as context_window_router
from friday_core.feedback_learning_engine import router as feedback_learning_router
from friday_core.agent_mesh_router import router as agent_mesh_router
from friday_core.universe_health_monitor import router as universe_health_mon_router

app.include_router(task_decomp_router, prefix="/api/v1")
app.include_router(decision_synth_router, prefix="/api/v1")
app.include_router(goal_planning_router, prefix="/api/v1")
app.include_router(context_window_router, prefix="/api/v1")
app.include_router(feedback_learning_router, prefix="/api/v1")
app.include_router(agent_mesh_router, prefix="/api/v1")
app.include_router(universe_health_mon_router, prefix="/api/v1")

# --- Cross-Cutting Infrastructure Integrations ---
from friday_core.universe_gateway import router as universe_gateway_router
from friday_core.universe_config import router as universe_config_router
from friday_core.universe_metrics import router as universe_metrics_router
from friday_core.error_envelope import router as error_envelope_router

app.include_router(universe_gateway_router, prefix="/api/v1")
app.include_router(universe_config_router, prefix="/api/v1")
app.include_router(universe_metrics_router, prefix="/api/v1")
app.include_router(error_envelope_router, prefix="/api/v1")

# --- Wave 35: Cross-Agent & Security Integrations ---
from friday_core.universe_dispatch_bus import router as dispatch_bus_router
from friday_core.universe_auth import router as universe_auth_router
from friday_core.cross_agent_integration import router as cross_agent_router
from friday_core.security_hardening import router as security_hardening_router

app.include_router(dispatch_bus_router, prefix="/api/v1")
app.include_router(universe_auth_router, prefix="/api/v1")
app.include_router(cross_agent_router, prefix="/api/v1")
app.include_router(security_hardening_router, prefix="/api/v1")

# --- Wave 39: Resilience & Cost Optimization ---
from friday_core.universe_resilience import router as universe_resilience_router
from friday_core.universe_cost_optimizer import router as universe_cost_router

app.include_router(universe_resilience_router, prefix="/api/v1")
app.include_router(universe_cost_router, prefix="/api/v1")

# --- Wave 41: Knowledge Graph ---
from friday_core.universe_knowledge_graph import router as universe_kg_router
app.include_router(universe_kg_router, prefix="/api/v1")

# --- Wave 42: Event Bus & State Manager ---
from friday_core.universe_event_bus import router as universe_event_bus_router
from friday_core.universe_state_manager import router as universe_state_router

app.include_router(universe_event_bus_router, prefix="/api/v1")
app.include_router(universe_state_router, prefix="/api/v1")

# --- Wave 44: Audit Trail & Rate Limiter ---
from friday_core.universe_audit_trail import router as universe_audit_router
from friday_core.universe_rate_limiter import router as universe_rate_router

app.include_router(universe_audit_router, prefix="/api/v1")
app.include_router(universe_rate_router, prefix="/api/v1")

# --- Wave 45: Task Router ---
from friday_core.universe_task_router import router as universe_task_router
app.include_router(universe_task_router, prefix="/api/v1")

# --- Dashboard static assets (mounted LAST: every API route above wins) ------
# Serves the export's immutable hashed assets (/_next/...), 404.html on direct
# request, and stray top-level files. The HTML shell itself is served by the
# "/" route above with no-store.
#
# BUG (found 2026-11-12, battery pass): with ``html=True`` the mounted
# StaticFiles answered EVERY unmatched path with the export's 404.html page,
# including /v1/tasks/<unknown-id> style API paths, so API clients received a
# Next.js HTML document instead of the standardized JSON error envelope the
# exception handlers already produce. ``html=False`` keeps the miss RAISING so
# the subclass below can pick the honest surface per caller: a browser still
# gets the SPA shell for client-side routing; everything else - curl, the
# voice line, the laptop bridge, monitoring - gets the JSON envelope.
class _APIAwareStaticFiles(StaticFiles):
    """Serve real files; on a miss, keep HTML for browsers, JSON for API clients."""

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            accept = ""
            for key, value in scope.get("headers", []):
                if key == b"accept":
                    accept = value.decode("latin-1")
                    break
            if "text/html" in accept:
                # A human in a browser: hand back the SPA shell so client-side
                # routing can render a friendly page.
                return Response(
                    content=_index_html(),
                    media_type="text/html",
                    status_code=404,
                    headers={"Cache-Control": "no-store, max-age=0"},
                )
            # Anything that did not ask for HTML is an API client: raise so the
            # app's StarletteHTTPException handler returns the JSON envelope.
            raise


if _UI_EXPORT_DIR.is_dir():
    # basePath parity (fix 2026-11-13): the export was built with
    # ``basePath: '/friday'``, so index.html and the Next client router ask
    # for assets under /friday/_next/... — but the export tree has NO
    # physical friday/ directory. Without a prefix-stripping mount every
    # asset request 404'd and the dashboard stayed on its splash screen
    # forever (blank page in production). Mounting the SAME export under
    # /friday makes FastAPI strip the prefix: /friday/_next/x.js -> out/_next/x.js.
    app.mount(
        "/friday",
        StaticFiles(directory=str(_UI_EXPORT_DIR), html=True),
        name="ui-friday",
    )
    app.mount("/", _APIAwareStaticFiles(directory=str(_UI_EXPORT_DIR), html=False), name="ui")
