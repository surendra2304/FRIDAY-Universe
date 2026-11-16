"""INTELX On-Demand Anti-Detect Browser Sidecar (camofox-browser pattern, TASK-IG2-INT-01).

Pattern adapted from jo-inc/camofox-browser (MIT License,
https://github.com/jo-inc/camofox-browser): a Camoufox-based anti-detection
browser wrapped in a small REST API (``POST /tabs``, ``GET /tabs/:id/snapshot``,
``DELETE /tabs/:id``) whose accessibility snapshots are ~90% smaller than raw
HTML and whose engine-level fingerprint spoofing passes bot walls that stop a
plain HTTP client.

FRIDAY adaptation — deliberately NOT a resident service:

* A rendering Firefox exceeds IntelX's ~180MB per-service memory cap, so the
  browser is an *on-demand sidecar*: it is started for a job that hit a bot
  wall, used for that fetch, and stopped after a short idle window. Nothing
  browser-shaped runs when no fetch needs it.
* The sidecar is opt-in (``INTELX_CAMOFOX_ENABLED``, default off) because the
  Camoufox binary is a ~300MB disk cost on the tiny fleet VMs; the intended
  hosts are the owner's machine or the future ARM server. With the flag off,
  every code path here is inert and plain HTTP behaviour is unchanged.
* The sidecar is only ever a *fallback*: ``SidecarFallbackFetcher`` wraps the
  hardened ``HttpFetchConnector`` and escalates solely on bot-wall evidence
  (HTTP 401/403/429 or a challenge interstitial). A robots.txt refusal is a
  policy decision, not a bot wall, and is never bypassed.
* The snapshot returned by camofox is accessibility text, not raw HTML. It is
  handed downstream as ``text/plain`` — the same shape the retriever already
  uses for search-snippet fallbacks — never disguised as the page's HTML.
* Anti-detection fetching must stay within target sites' terms; the sidecar
  inherits IntelX's domain policy guard, SSRF pre-validation, and robots.txt
  checks before any browser navigation happens.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass
from typing import Any

import httpx

from intelx.connectors.base import BaseConnector
from intelx.connectors.web import FetchResult, HttpFetchConnector
from intelx.core.errors import ProviderError
from intelx.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Challenge / bot-wall fingerprints, grouped by vendor where identifiable.
# Markers follow the same idea as the DuckDuckGo anti-bot check in
# connectors/search.py, generalised across the common bot-management vendors.
_BOT_WALL_MARKERS: dict[str, tuple[str, ...]] = {
    "cloudflare": (
        "just a moment",
        "attention required",
        "checking your browser",
        "challenge-platform",
        "cf-challenge",
        "challenges.cloudflare.com",
    ),
    "datadome": ("datadome", "captcha-delivery.com", "dd-captcha"),
    "perimeterx": ("perimeterx", "px-captcha", "human security"),
    "imperva_incapsula": ("incapsula", "imperva", "_incapsula_resource"),
    "akamai": ("akamai bot manager", "sec-cpt"),
    "generic": (
        "verify you are human",
        "are you a robot",
        "unusual traffic from your computer network",
        "automated access",
        "bot detection",
        "ddos-guard",
        "sucuri",
        "please complete the security check",
    ),
}

_WALL_STATUSES = {401, 403, 429}
# A wall page with almost no body is still a wall: several vendors answer a
# bare 403 with an empty or near-empty response body.
_SUSPECT_BODY_MAX = 512


@dataclass(frozen=True)
class BotWallVerdict:
    """Classification of a fetch response as (or as not) a bot wall."""

    is_wall: bool
    confidence: str = "none"  # none | suspected | confirmed
    vendor: str | None = None
    reason: str = ""


def detect_bot_wall(
    status_code: int,
    headers: dict[str, str] | None = None,
    body: bytes | str | None = None,
) -> BotWallVerdict:
    """Decide whether a response is a bot-management wall rather than content.

    Confirmed: a known challenge marker is present (any status — Cloudflare
    serves its interstitial with 200 as often as with 403). Suspected: a
    401/403/429 with no usable content, where a browser attempt is the only
    remaining way to learn whether a human would have been served the page.
    """
    text = ""
    if isinstance(body, bytes):
        text = body[:65536].decode("utf-8", errors="replace").lower()
    elif isinstance(body, str):
        text = body[:65536].lower()

    for vendor, markers in _BOT_WALL_MARKERS.items():
        for marker in markers:
            if marker in text:
                return BotWallVerdict(
                    is_wall=True,
                    confidence="confirmed",
                    vendor=None if vendor == "generic" else vendor,
                    reason=f"challenge marker '{marker}' in response body",
                )

    if status_code in _WALL_STATUSES:
        server = ((headers or {}).get("server") or "").lower()
        for vendor in ("cloudflare", "datadome", "akamai"):
            if vendor in server:
                return BotWallVerdict(
                    is_wall=True,
                    confidence="suspected",
                    vendor=vendor,
                    reason=f"HTTP {status_code} served by {vendor}",
                )
        body_len = len(body) if body is not None else 0
        if body_len <= _SUSPECT_BODY_MAX:
            return BotWallVerdict(
                is_wall=True,
                confidence="suspected",
                reason=f"HTTP {status_code} with {body_len}-byte body (no usable content)",
            )
        return BotWallVerdict(
            is_wall=True,
            confidence="suspected",
            reason=f"HTTP {status_code} without challenge markers",
        )

    return BotWallVerdict(is_wall=False, reason=f"HTTP {status_code} with content")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass
class SidecarConfig:
    """Runtime configuration for the camofox sidecar (env-driven, off by default)."""

    enabled: bool = False
    base_url: str = "http://127.0.0.1:9377"
    api_key: str | None = None
    start_cmd: str = ""
    idle_stop_s: float = 120.0
    startup_timeout_s: float = 60.0
    nav_timeout_s: float = 30.0
    user_id: str = "intelx"

    @classmethod
    def from_env(cls) -> SidecarConfig:
        """Build configuration from INTELX_CAMOFOX_* environment variables."""
        cfg = cls(
            enabled=_env_bool("INTELX_CAMOFOX_ENABLED"),
            base_url=os.environ.get("INTELX_CAMOFOX_URL", cls.base_url).rstrip("/"),
            api_key=os.environ.get("INTELX_CAMOFOX_API_KEY") or None,
            start_cmd=os.environ.get("INTELX_CAMOFOX_START_CMD", ""),
            idle_stop_s=_env_float("INTELX_CAMOFOX_IDLE_STOP_S", cls.idle_stop_s),
            startup_timeout_s=_env_float("INTELX_CAMOFOX_STARTUP_TIMEOUT_S", cls.startup_timeout_s),
            nav_timeout_s=_env_float("INTELX_CAMOFOX_NAV_TIMEOUT_S", cls.nav_timeout_s),
            user_id=os.environ.get("INTELX_CAMOFOX_USER_ID", cls.user_id),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        """Fail closed on a sidecar address that is not a local/operator host.

        The camofox API can drive a browser with the operator's session state,
        so IntelX only ever points it at loopback or a single-label operator
        host (e.g. a docker service name) — never at a public FQDN.
        """
        parsed = urllib.parse.urlsplit(self.base_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not host:
            raise ValueError(f"Invalid camofox sidecar URL: {self.base_url!r}")
        is_loopback = host in {"localhost", "127.0.0.1", "::1"}
        is_single_label = "." not in host and ":" not in host
        if not (is_loopback or is_single_label):
            raise ValueError(
                "camofox sidecar URL must be loopback or a single-label operator "
                f"host, got {host!r}"
            )
        if self.idle_stop_s < 0 or self.nav_timeout_s <= 0 or self.startup_timeout_s <= 0:
            raise ValueError("camofox sidecar timeouts must be positive (idle stop may be 0)")


class CamofoxClient:
    """Minimal async client for the camofox-browser REST API."""

    def __init__(
        self,
        config: SidecarConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.config.base_url,
            transport=self._transport,
            timeout=httpx.Timeout(self.config.nav_timeout_s),
            headers=self._headers(),
        )

    async def health(self) -> bool:
        """Return True when the sidecar server answers its health endpoint."""
        try:
            async with self._client() as client:
                resp = await client.get("/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch_snapshot(self, url: str) -> tuple[str, str]:
        """Open ``url`` in a fresh tab and return (final_url, snapshot_text).

        The tab is always closed again; the session is per-user and reused so
        cookies a challenge sets can persist across the single navigation.
        """
        user_id = self.config.user_id
        async with self._client() as client:
            created = await client.post(
                "/tabs",
                json={"userId": user_id, "sessionKey": f"intelx-{int(time.time())}", "url": url},
            )
            if created.status_code >= 400:
                raise ProviderError(
                    "camofox sidecar refused to open a tab",
                    details={"provider": "camofox", "status_code": created.status_code},
                )
            tab_id = self._extract_tab_id(created)
            if tab_id is None:
                tab_id = await self._first_tab_id(client, user_id)
            if tab_id is None:
                raise ProviderError(
                    "camofox sidecar did not report a tab id",
                    details={"provider": "camofox"},
                )
            try:
                snapshot_text = ""
                deadline = time.monotonic() + self.config.nav_timeout_s
                while True:
                    snap = await client.get(
                        f"/tabs/{tab_id}/snapshot", params={"userId": user_id}
                    )
                    if snap.status_code >= 400:
                        raise ProviderError(
                            "camofox sidecar snapshot failed",
                            details={"provider": "camofox", "status_code": snap.status_code},
                        )
                    data = snap.json() if snap.content else {}
                    snapshot_text = str(
                        data.get("snapshot") or data.get("text") or data.get("content") or ""
                    )
                    if snapshot_text.strip() or time.monotonic() >= deadline:
                        break
                    await asyncio.sleep(0.5)
                final_url = str(data.get("url") or url) if snapshot_text else url
                return final_url, snapshot_text
            finally:
                try:
                    await client.request(
                        "DELETE", f"/tabs/{tab_id}", json={"userId": user_id}
                    )
                except Exception:
                    logger.debug("camofox tab close failed (tab %s)", tab_id, exc_info=True)

    @staticmethod
    def _extract_tab_id(response: httpx.Response) -> str | None:
        try:
            data = response.json()
        except Exception:
            return None
        if isinstance(data, dict):
            for key in ("tabId", "id", "tab_id"):
                value = data.get(key)
                if value:
                    return str(value)
            tab = data.get("tab")
            if isinstance(tab, dict) and tab.get("id"):
                return str(tab["id"])
        return None

    async def _first_tab_id(self, client: httpx.AsyncClient, user_id: str) -> str | None:
        try:
            resp = await client.get("/tabs", params={"userId": user_id})
            data = resp.json()
        except Exception:
            return None
        tabs = data.get("tabs") if isinstance(data, dict) else data
        if isinstance(tabs, list) and tabs and isinstance(tabs[0], dict):
            value = tabs[0].get("id") or tabs[0].get("tabId")
            return str(value) if value else None
        return None


class SidecarManager:
    """Owns the sidecar process lifecycle: start per job, stop when idle.

    If no start command is configured, the manager never spawns anything and
    only *uses* a sidecar the operator already runs at the configured URL —
    IntelX never pretends to manage a process it did not start.
    """

    def __init__(
        self,
        config: SidecarConfig,
        client: CamofoxClient | None = None,
    ) -> None:
        self.config = config
        self.client = client or CamofoxClient(config)
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._idle_task: asyncio.Task[None] | None = None
        self._last_used = 0.0

    async def ensure_running(self) -> bool:
        """Ensure the sidecar answers health checks, starting it if configured."""
        async with self._lock:
            self._cancel_idle()
            if await self.client.health():
                self._last_used = time.monotonic()
                return True
            if not self.config.start_cmd:
                return False
            if self._process is None or self._process.returncode is not None:
                logger.info("Starting camofox sidecar on demand: %s", self.config.start_cmd)
                self._process = await asyncio.create_subprocess_shell(
                    self.config.start_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                )
            deadline = time.monotonic() + self.config.startup_timeout_s
            while time.monotonic() < deadline:
                if await self.client.health():
                    self._last_used = time.monotonic()
                    return True
                await asyncio.sleep(0.5)
            logger.warning("camofox sidecar did not become healthy after start")
            return False

    def note_fetch_done(self) -> None:
        """Arm the idle shutdown timer after a fetch completes."""
        self._last_used = time.monotonic()
        if self.config.idle_stop_s <= 0:
            return
        self._cancel_idle()
        self._idle_task = asyncio.create_task(self._idle_stop())

    async def _idle_stop(self) -> None:
        try:
            await asyncio.sleep(self.config.idle_stop_s)
            if time.monotonic() - self._last_used >= self.config.idle_stop_s:
                await self.stop()
        except asyncio.CancelledError:
            pass

    def _cancel_idle(self) -> None:
        if self._idle_task is not None and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def stop(self) -> None:
        """Terminate a sidecar process this manager started (never a foreign one)."""
        self._cancel_idle()
        process, self._process = self._process, None
        if process is None or process.returncode is not None:
            return
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10.0)
        except asyncio.TimeoutError:  # noqa: UP041 — fleet runs py3.10, where this is not yet the builtin alias
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                process.kill()


class BrowserSidecarConnector(BaseConnector):
    """Fetch a page through the on-demand camofox sidecar (accessibility text)."""

    def __init__(
        self,
        config: SidecarConfig | None = None,
        manager: SidecarManager | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = settings or get_settings()
        super().__init__(
            name="camofox_sidecar",
            capabilities=["fetch_html", "bot_wall_fallback"],
            required_credentials=[],
            classification="EXTERNAL_HTTP",
            settings=cfg,
            **kwargs,
        )
        self.settings = cfg
        self.config = config or SidecarConfig.from_env()
        self.manager = manager or SidecarManager(self.config)

    async def _robots_allowed(self, url: str) -> bool:
        """Robots.txt gate mirroring HttpFetchConnector's fail-closed semantics."""
        if not self.settings.RESPECT_ROBOTS:
            return True
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(robots_url)
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
            elif 400 <= resp.status_code < 500:
                parser.allow_all = True
            else:
                parser.disallow_all = True
        except Exception:
            parser.disallow_all = True
        return parser.can_fetch(self.settings.USER_AGENT, url)

    async def fetch(self, target: str, **kwargs: Any) -> FetchResult:
        """Fetch ``target`` via the sidecar, honouring policy, SSRF and robots gates."""
        parsed = urllib.parse.urlparse(target)
        hostname = parsed.hostname or ""
        if parsed.scheme.lower() not in {"http", "https"} or not hostname:
            return FetchResult(
                url=target, final_url=target, content=b"", content_type="text/plain",
                status_code=0, error=f"Invalid or prohibited URL: {target}",
            )
        self.check_policy(hostname)
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        HttpFetchConnector.validate_ssrf(hostname, port)

        if not await self._robots_allowed(target):
            return FetchResult(
                url=target, final_url=target, content=b"", content_type="text/plain",
                status_code=403, robots_ok=False,
                error="Disallowed by robots.txt",
            )

        if not await self.manager.ensure_running():
            return FetchResult(
                url=target, final_url=target, content=b"", content_type="text/plain",
                status_code=0,
                error="camofox sidecar unavailable (not running and no start command configured)",
            )
        try:
            final_url, snapshot = await self.manager.client.fetch_snapshot(target)
        except Exception as exc:
            logger.warning("camofox sidecar fetch failed for %s (%s)", target, type(exc).__name__)
            return FetchResult(
                url=target, final_url=target, content=b"", content_type="text/plain",
                status_code=0, error=f"camofox sidecar fetch failed: {type(exc).__name__}",
            )
        finally:
            self.manager.note_fetch_done()

        content = snapshot.encode("utf-8")
        max_bytes = min(
            kwargs.get("max_bytes", self.settings.MAX_PAGE_BYTES), self.settings.MAX_PAGE_BYTES
        )
        if len(content) > max_bytes:
            content = content[:max_bytes]
        return FetchResult(
            url=target,
            final_url=final_url,
            content=content,
            content_type="text/plain",
            status_code=200 if content else 0,
            robots_ok=True,
            headers={
                "x-intelx-fetch-via": "camofox-sidecar",
                "x-intelx-sidecar-format": "accessibility-snapshot",
            },
            error=None if content else "camofox sidecar returned an empty snapshot",
        )


class SidecarFallbackFetcher:
    """HttpFetchConnector wrapper that escalates bot-walled fetches to the sidecar.

    Only bot-wall evidence triggers escalation. Successful fetches, robots
    refusals, and every other error pass through untouched, so enabling the
    sidecar can never make a previously-refused fetch succeed for the wrong
    reason. If the sidecar is disabled or unavailable, the original outcome
    (result or exception) is preserved exactly.
    """

    def __init__(
        self,
        http_connector: HttpFetchConnector,
        sidecar: BrowserSidecarConnector | None = None,
        config: SidecarConfig | None = None,
    ) -> None:
        self.http_connector = http_connector
        self.config = config or (
            sidecar.config if sidecar is not None else SidecarConfig.from_env()
        )
        self.sidecar = sidecar
        if self.sidecar is None and self.config.enabled:
            self.sidecar = BrowserSidecarConnector(
                config=self.config, settings=http_connector.settings
            )

    @property
    def enabled(self) -> bool:
        return self.config.enabled and self.sidecar is not None

    async def fetch(self, target: str, **kwargs: Any) -> FetchResult:
        """Fetch via HTTP first; escalate to the browser sidecar only on a bot wall."""
        try:
            result = await self.http_connector.fetch(target, **kwargs)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status in _WALL_STATUSES and self.enabled:
                fallback = await self._try_sidecar(target, kwargs)
                if fallback is not None:
                    return fallback
            raise
        if not result.robots_ok:
            # A robots refusal is policy, not a bot wall — never bypass it.
            return result
        verdict = detect_bot_wall(result.status_code, result.headers, result.content)
        if verdict.is_wall and self.enabled:
            fallback = await self._try_sidecar(target, kwargs)
            if fallback is not None:
                return fallback
        return result

    async def _try_sidecar(self, target: str, kwargs: dict[str, Any]) -> FetchResult | None:
        assert self.sidecar is not None
        result = await self.sidecar.fetch(target, **kwargs)
        if result.content:
            logger.info("Bot-wall fallback via camofox sidecar succeeded for %s", target)
            return result
        logger.info("Bot-wall fallback via camofox sidecar yielded nothing for %s", target)
        return None


def maybe_wrap_with_sidecar_fallback(
    http_connector: HttpFetchConnector,
    config: SidecarConfig | None = None,
) -> HttpFetchConnector | SidecarFallbackFetcher:
    """Wrap ``http_connector`` with sidecar fallback when the operator enabled it.

    Returns the connector unchanged when the sidecar is disabled (the default),
    so call sites can wrap unconditionally.
    """
    cfg = config or SidecarConfig.from_env()
    if not cfg.enabled:
        return http_connector
    return SidecarFallbackFetcher(http_connector, config=cfg)


__all__ = [
    "BotWallVerdict",
    "BrowserSidecarConnector",
    "CamofoxClient",
    "SidecarConfig",
    "SidecarFallbackFetcher",
    "SidecarManager",
    "detect_bot_wall",
    "maybe_wrap_with_sidecar_fallback",
]
