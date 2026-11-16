"""Deploy watchdog: deployed-HEAD-vs-main divergence check (TASK-OBS-004).

Why this exists (defect D9, proven 2026-11-16): Fleet CD's concurrency
group keeps only ONE pending run per ref. When PR #716's push landed,
PR #703's deploy run was cancelled with zero jobs, and #716's own run
skipped Server 2 through its paths-filter — so three merged Cortex files
were silently stranded on Server 2 and no later push ever healed it.
The fleet had no standing check that a server's deployed HEAD actually
equals origin/main. This module is that check.

Design
------
- ``DeployWatchdog`` holds per-server divergence state. A server whose
  deployed HEAD differs from origin/main starts a divergence episode;
  only when the divergence persists beyond ``grace_seconds`` (default
  1800s — comfortably beyond one Fleet CD cycle, so a deploy still in
  flight never alerts) does it raise ONE alert through the existing
  operations alert path (``AlertEngine.process_delta``, which the API
  lifespan wires to the shared human channel). When the server returns
  to main, a recovery delta is emitted and the episode closes.
- A failed read (git error, network down) yields status UNKNOWN and
  leaves the episode clock untouched: the watchdog never alerts on
  missing evidence, and never resets a running episode because a probe
  hiccupped.
- HEAD sources are injectable callables. Production sources provided
  here: ``git_checkout_head`` (a server's own checkout, stdlib git CLI)
  and ``git_remote_main_head`` (``git ls-remote`` against the repo).
- State stores mirror ``audit_baseline``'s pattern: in-memory for tests
  and tools, JSON file for the production singleton so an episode (and
  its already-alerted flag) survives a Sentinel restart.

Coverage shape in production: the API lifespan runs the LOCAL server
check in-process (Sentinel's own host) when configured, and servers
Sentinel does not run on report their HEAD via
``POST /operations/deploy-watchdog/report`` (see
``scripts/deploy_watchdog_report.py``); the persistence decision always
lives here, in one state store.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
try:
    from enum import StrEnum
except ImportError:  # Python < 3.11: behaviour-identical fallback
    from enum import Enum as _StrEnumBase

    class StrEnum(str, _StrEnumBase):
        """Stand-in for enum.StrEnum (3.11+) on older interpreters."""

        __str__ = str.__str__
        __format__ = str.__format__

        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from sentinel.core.models import SeverityLevel
from sentinel.modules.operations.alerting import alert_engine
from sentinel.modules.operations.baseline import BaselineDelta, ChangeType

logger = logging.getLogger("sentinel.operations.deploy_watchdog")

#: Default grace: divergence must persist longer than one full Fleet CD
#: cycle (a deploy run takes minutes) before it is worth a human alert.
DEFAULT_GRACE_SECONDS = 1800

#: Default production checkout path (one repo checkout per server).
DEFAULT_CHECKOUT_PATH = "/opt/friday_universe"

DEFAULT_REPO_URL = "https://github.com/surendra2304/FRIDAY-Universe.git"


class DeployStatus(StrEnum):
    IN_SYNC = "in_sync"
    DIVERGED = "diverged"  # diverged, still inside the grace window
    ALERTED = "alerted"  # diverged beyond grace; alert has been raised
    UNKNOWN = "unknown"  # a HEAD read failed; no evidence either way


class ServerDeployState(BaseModel):
    server: str
    deployed_head: str | None = None
    main_head: str | None = None
    status: DeployStatus = DeployStatus.UNKNOWN
    diverged_since: datetime | None = None
    alerted: bool = False
    last_checked_at: datetime | None = None
    check_count: int = 0
    read_failures: int = 0


class InMemoryDeployStateStore:
    """Volatile state store (tests, tools, one-shot runs)."""

    def __init__(self) -> None:
        self._states: dict[str, ServerDeployState] = {}

    def get(self, server: str) -> ServerDeployState | None:
        state = self._states.get(server)
        return state.model_copy(deep=True) if state else None

    def put(self, state: ServerDeployState) -> None:
        self._states[state.server] = state.model_copy(deep=True)

    def all(self) -> list[ServerDeployState]:
        return [s.model_copy(deep=True) for s in self._states.values()]


class JsonDeployStateStore:
    """JSON-file state store: episodes survive a Sentinel restart."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, ServerDeployState]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        states: dict[str, ServerDeployState] = {}
        for server, payload in (raw or {}).items():
            try:
                states[server] = ServerDeployState.model_validate(payload)
            except ValueError:
                logger.warning("deploy watchdog: ignoring corrupt state for %s", server)
        return states

    def _save(self, states: dict[str, ServerDeployState]) -> None:
        payload = {s: st.model_dump(mode="json") for s, st in states.items()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def get(self, server: str) -> ServerDeployState | None:
        return self._load().get(server)

    def put(self, state: ServerDeployState) -> None:
        states = self._load()
        states[state.server] = state
        self._save(states)

    def all(self) -> list[ServerDeployState]:
        return list(self._load().values())


def _short(sha: str | None) -> str:
    return (sha or "?")[:8]


class DeployWatchdog:
    """Tracks deployed-HEAD divergence per server and alerts on persistence."""

    def __init__(
        self,
        grace_seconds: int = DEFAULT_GRACE_SECONDS,
        state_store: Any | None = None,
        alert_sink: Callable[[BaselineDelta], Any] | None = None,
    ) -> None:
        self._grace = max(0, grace_seconds)
        self._store = state_store or InMemoryDeployStateStore()
        # Default sink is the operations AlertEngine singleton — the same
        # alert path the scheduler's escalation uses (TASK-SEN-008 wiring
        # attaches the human-channel dispatcher in the API lifespan).
        self._sink = alert_sink or alert_engine.process_delta

    @property
    def grace_seconds(self) -> int:
        return self._grace

    def configure(
        self,
        grace_seconds: int | None = None,
        state_store: Any | None = None,
        alert_sink: Callable[[BaselineDelta], Any] | None = None,
    ) -> None:
        """Reconfigure this instance in place (singleton-safe)."""
        if grace_seconds is not None:
            self._grace = max(0, grace_seconds)
        if state_store is not None:
            self._store = state_store
        if alert_sink is not None:
            self._sink = alert_sink

    # -- core decision ----------------------------------------------------

    def observe(
        self,
        server: str,
        deployed_head: str | None,
        main_head: str | None,
        now: datetime | None = None,
    ) -> ServerDeployState:
        """Fold one observation into the server's state; alert if due."""
        now = now or datetime.now(UTC)
        state = self._store.get(server) or ServerDeployState(server=server)
        state.last_checked_at = now
        state.check_count += 1

        if not deployed_head or not main_head:
            # No evidence: keep any running episode clock untouched.
            state.read_failures += 1
            state.status = DeployStatus.UNKNOWN
            if deployed_head:
                state.deployed_head = deployed_head
            if main_head:
                state.main_head = main_head
            self._store.put(state)
            return state

        state.deployed_head = deployed_head
        state.main_head = main_head

        if deployed_head == main_head:
            was_alerted = state.alerted
            state.status = DeployStatus.IN_SYNC
            state.diverged_since = None
            state.alerted = False
            self._store.put(state)
            if was_alerted:
                self._emit(
                    server,
                    ChangeType.RESOLVED_FINDING,
                    SeverityLevel.LOW,
                    f"Deploy watchdog: {server} is back in sync with "
                    f"origin/main at {_short(main_head)}; the divergence "
                    f"episode is closed.",
                    main_head,
                )
            return state

        # Diverged.
        if state.diverged_since is None:
            state.diverged_since = now
            state.alerted = False
            state.status = DeployStatus.DIVERGED
        elif not state.alerted and (now - state.diverged_since).total_seconds() >= self._grace:
            state.alerted = True
            state.status = DeployStatus.ALERTED
            self._store.put(state)
            self._emit(
                server,
                ChangeType.NEW_FINDING,
                SeverityLevel.HIGH,
                f"Deploy watchdog: {server} deployed HEAD "
                f"{_short(deployed_head)} has diverged from origin/main "
                f"{_short(main_head)} since "
                f"{state.diverged_since.isoformat()} — beyond the "
                f"{self._grace}s grace window (one Fleet CD cycle). A "
                f"merged change is not live on this server; check for a "
                f"cancelled or paths-skipped Fleet CD run (defect class "
                f"D9).",
                deployed_head,
            )
            return state
        elif state.alerted:
            state.status = DeployStatus.ALERTED
        self._store.put(state)
        return state

    def _emit(
        self,
        server: str,
        change_type: ChangeType,
        severity: SeverityLevel,
        description: str,
        head: str,
    ) -> None:
        try:
            self._sink(
                BaselineDelta(
                    delta_id=f"delta-deploy-watchdog-{server}-{change_type.value}-{_short(head)}",
                    target_ref=f"deploy:{server}",
                    change_type=change_type,
                    severity=severity,
                    description=description,
                )
            )
        except Exception as e:  # alerting must never break the check loop
            logger.error("deploy watchdog alert sink failed for %s: %s", server, e)

    # -- provider-driven checks -------------------------------------------

    def check_server(
        self,
        server: str,
        deployed_provider: Callable[[], str | None],
        main_provider: Callable[[], str | None],
        now: datetime | None = None,
    ) -> ServerDeployState:
        """Run one check for a server from two HEAD providers."""
        try:
            deployed = deployed_provider()
        except Exception as e:
            logger.warning("deploy watchdog: deployed HEAD read failed for %s: %s", server, e)
            deployed = None
        try:
            main = main_provider()
        except Exception as e:
            logger.warning("deploy watchdog: origin/main read failed: %s", e)
            main = None
        return self.observe(server, deployed, main, now=now)

    def status(self) -> list[ServerDeployState]:
        return self._store.all()


# -- production HEAD providers (stdlib git CLI) ----------------------------


def git_checkout_head(checkout_path: str) -> str | None:
    """HEAD sha of a local checkout, or None when unreadable."""
    try:
        out = subprocess.run(
            ["git", "-C", checkout_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = (out.stdout or "").strip()
    return sha if out.returncode == 0 and len(sha) >= 7 else None


def git_remote_main_head(repo_url: str, branch: str = "main") -> str | None:
    """origin/main sha via ls-remote, or None when unreachable."""
    try:
        out = subprocess.run(
            ["git", "ls-remote", repo_url, f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    parts = (out.stdout or "").split()
    return parts[0] if parts and len(parts[0]) >= 7 else None


# -- run loop (mirrors the Memora consumer's lifecycle shape) ---------------


async def run_deploy_watchdog(
    watchdog: DeployWatchdog,
    server_name: str,
    checkout_path: str,
    repo_url: str = DEFAULT_REPO_URL,
    interval_seconds: float = 600.0,
) -> None:
    """Periodically check the LOCAL server's deployed HEAD against main."""
    interval = max(30.0, interval_seconds)
    logger.info(
        "Deploy watchdog started for %s (checkout %s, every %.0fs, grace %ds)",
        server_name,
        checkout_path,
        interval,
        watchdog.grace_seconds,
    )
    while True:
        try:
            state = watchdog.check_server(
                server_name,
                lambda: git_checkout_head(checkout_path),
                lambda: git_remote_main_head(repo_url),
            )
            if state.status in (DeployStatus.DIVERGED, DeployStatus.ALERTED):
                logger.warning(
                    "deploy watchdog: %s %s (deployed %s, main %s)",
                    server_name,
                    state.status.value,
                    _short(state.deployed_head),
                    _short(state.main_head),
                )
        except Exception as e:  # the loop must survive any single failure
            logger.error("deploy watchdog cycle failed for %s: %s", server_name, e)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
    logger.info("Deploy watchdog stopped for %s", server_name)


#: Global watchdog singleton (configured in place by the API lifespan
#: when the watchdog is enabled; endpoints read/observe through it).
deploy_watchdog = DeployWatchdog()


def configure_deploy_watchdog(
    grace_seconds: int = DEFAULT_GRACE_SECONDS,
    state_path: str | Path | None = None,
) -> DeployWatchdog:
    """Configure the singleton in place with production settings."""
    deploy_watchdog.configure(
        grace_seconds=grace_seconds,
        state_store=JsonDeployStateStore(state_path)
        if state_path
        else InMemoryDeployStateStore(),
    )
    return deploy_watchdog


__all__ = [
    "DEFAULT_CHECKOUT_PATH",
    "DEFAULT_GRACE_SECONDS",
    "DEFAULT_REPO_URL",
    "DeployStatus",
    "DeployWatchdog",
    "InMemoryDeployStateStore",
    "JsonDeployStateStore",
    "ServerDeployState",
    "configure_deploy_watchdog",
    "deploy_watchdog",
    "git_checkout_head",
    "git_remote_main_head",
    "run_deploy_watchdog",
]
