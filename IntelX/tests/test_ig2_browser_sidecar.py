"""Tests for TASK-IG2-INT-01: on-demand camofox browser sidecar for IntelX.

Covers bot-wall detection, sidecar config guards, the camofox REST client
(against an httpx MockTransport), the sidecar connector's gates, and the
fallback wrapper's escalation rules. No real browser or network is used.
"""

import httpx
import pytest

from intelx.connectors.browser_sidecar import (
    BrowserSidecarConnector,
    CamofoxClient,
    SidecarConfig,
    SidecarFallbackFetcher,
    SidecarManager,
    detect_bot_wall,
    maybe_wrap_with_sidecar_fallback,
)
from intelx.connectors.web import FetchResult, HttpFetchConnector
from intelx.core.settings import Settings

# ── Bot-wall detection ──────────────────────────────────────────────────────


def test_detect_cloudflare_challenge_body_is_confirmed_wall():
    verdict = detect_bot_wall(403, {"server": "cloudflare"}, b"<title>Just a moment...</title>")
    assert verdict.is_wall
    assert verdict.confidence == "confirmed"
    assert verdict.vendor == "cloudflare"


def test_detect_interstitial_served_with_200_is_wall():
    body = b"Checking your browser before accessing the site. challenge-platform"
    verdict = detect_bot_wall(200, {}, body)
    assert verdict.is_wall
    assert verdict.confidence == "confirmed"


def test_detect_normal_article_is_not_wall():
    body = b"<html><body>" + b"Research findings and analysis. " * 100 + b"</body></html>"
    verdict = detect_bot_wall(200, {"server": "nginx"}, body)
    assert not verdict.is_wall


def test_detect_empty_403_is_suspected_wall():
    verdict = detect_bot_wall(403, {}, b"")
    assert verdict.is_wall
    assert verdict.confidence == "suspected"


def test_detect_429_with_content_is_suspected_wall():
    verdict = detect_bot_wall(429, {}, b"rate limited, slow down please" * 40)
    assert verdict.is_wall
    assert verdict.confidence == "suspected"


def test_detect_404_is_not_wall():
    assert not detect_bot_wall(404, {}, b"not found").is_wall


# ── Config guards ───────────────────────────────────────────────────────────


def test_config_rejects_public_sidecar_host():
    with pytest.raises(ValueError, match="loopback"):
        SidecarConfig(base_url="https://browsers.example.com:9377").validate()


def test_config_accepts_loopback_and_service_name():
    SidecarConfig(base_url="http://127.0.0.1:9377").validate()
    SidecarConfig(base_url="http://camofox:9377").validate()


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("INTELX_CAMOFOX_ENABLED", "true")
    monkeypatch.setenv("INTELX_CAMOFOX_URL", "http://localhost:9999")
    cfg = SidecarConfig.from_env()
    assert cfg.enabled is True
    assert cfg.base_url == "http://localhost:9999"


# ── Camofox REST client ─────────────────────────────────────────────────────


def _camofox_transport(snapshot_text="[heading e1] Example Domain"):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/tabs" and request.method == "POST":
            return httpx.Response(200, json={"tabId": "tab-1"})
        if path == "/tabs/tab-1/snapshot":
            return httpx.Response(
                200, json={"snapshot": snapshot_text, "url": "https://example.com/"}
            )
        if path == "/tabs/tab-1" and request.method == "DELETE":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)


async def test_camofox_client_health_and_snapshot():
    cfg = SidecarConfig(enabled=True, base_url="http://127.0.0.1:9377", idle_stop_s=0)
    client = CamofoxClient(cfg, transport=_camofox_transport())
    assert await client.health() is True
    final_url, text = await client.fetch_snapshot("https://example.com/")
    assert "Example Domain" in text
    assert final_url == "https://example.com/"


async def test_manager_uses_already_running_sidecar_without_start_cmd():
    cfg = SidecarConfig(enabled=True, base_url="http://127.0.0.1:9377", start_cmd="")
    manager = SidecarManager(cfg, client=CamofoxClient(cfg, transport=_camofox_transport()))
    assert await manager.ensure_running() is True
    await manager.stop()  # never started a process: must be a no-op


async def test_manager_reports_unavailable_when_nothing_listens():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    cfg = SidecarConfig(enabled=True, base_url="http://127.0.0.1:9377", start_cmd="")
    manager = SidecarManager(
        cfg, client=CamofoxClient(cfg, transport=httpx.MockTransport(handler))
    )
    assert await manager.ensure_running() is False


# ── Sidecar connector ───────────────────────────────────────────────────────


async def test_sidecar_connector_fetch_returns_snapshot_text(monkeypatch):
    cfg = SidecarConfig(enabled=True, base_url="http://127.0.0.1:9377", idle_stop_s=0)
    manager = SidecarManager(cfg, client=CamofoxClient(cfg, transport=_camofox_transport()))
    settings = Settings(MOCK_MODE=True, RESPECT_ROBOTS=False)
    connector = BrowserSidecarConnector(config=cfg, manager=manager, settings=settings)
    monkeypatch.setattr(
        HttpFetchConnector, "validate_ssrf", classmethod(lambda cls, host, port=80: ["1.2.3.4"])
    )
    result = await connector.fetch("https://example.com/article")
    assert result.status_code == 200
    assert b"Example Domain" in result.content
    assert result.content_type == "text/plain"
    assert result.headers["x-intelx-fetch-via"] == "camofox-sidecar"


async def test_sidecar_connector_unavailable_is_an_honest_empty_result(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    cfg = SidecarConfig(enabled=True, base_url="http://127.0.0.1:9377", start_cmd="")
    manager = SidecarManager(
        cfg, client=CamofoxClient(cfg, transport=httpx.MockTransport(handler))
    )
    settings = Settings(MOCK_MODE=True, RESPECT_ROBOTS=False)
    connector = BrowserSidecarConnector(config=cfg, manager=manager, settings=settings)
    monkeypatch.setattr(
        HttpFetchConnector, "validate_ssrf", classmethod(lambda cls, host, port=80: ["1.2.3.4"])
    )
    result = await connector.fetch("https://example.com/article")
    assert result.content == b""
    assert result.error and "unavailable" in result.error


# ── Fallback wrapper ────────────────────────────────────────────────────────


class _FakeHttp:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.settings = Settings(MOCK_MODE=True)

    async def fetch(self, target, **kwargs):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeSidecar:
    def __init__(self, content=b"browser rendered text"):
        self.calls = 0
        self._content = content

    async def fetch(self, target, **kwargs):
        self.calls += 1
        return FetchResult(
            url=target, final_url=target, content=self._content,
            content_type="text/plain", status_code=200 if self._content else 0,
        )


def _result(status=200, content=b"page body", robots_ok=True, headers=None):
    return FetchResult(
        url="https://example.com/x", final_url="https://example.com/x",
        content=content, content_type="text/html", status_code=status,
        robots_ok=robots_ok, headers=headers or {},
    )


async def test_wrapper_escalates_on_challenge_result():
    http = _FakeHttp(result=_result(403, b"Just a moment... challenge-platform"))
    sidecar = _FakeSidecar()
    wrapper = SidecarFallbackFetcher(http, sidecar=sidecar, config=SidecarConfig(enabled=True))
    out = await wrapper.fetch("https://example.com/x")
    assert out.content == b"browser rendered text"
    assert sidecar.calls == 1


async def test_wrapper_escalates_on_http_status_error():
    request = httpx.Request("GET", "https://example.com/x")
    response = httpx.Response(403, request=request, content=b"forbidden")
    http = _FakeHttp(error=httpx.HTTPStatusError("403", request=request, response=response))
    sidecar = _FakeSidecar()
    wrapper = SidecarFallbackFetcher(http, sidecar=sidecar, config=SidecarConfig(enabled=True))
    out = await wrapper.fetch("https://example.com/x")
    assert out.content == b"browser rendered text"


async def test_wrapper_never_bypasses_robots_refusal():
    http = _FakeHttp(result=_result(403, b"", robots_ok=False))
    sidecar = _FakeSidecar()
    wrapper = SidecarFallbackFetcher(http, sidecar=sidecar, config=SidecarConfig(enabled=True))
    out = await wrapper.fetch("https://example.com/x")
    assert out.robots_ok is False
    assert sidecar.calls == 0


async def test_wrapper_passes_through_normal_result():
    http = _FakeHttp(result=_result(200, b"real article body"))
    sidecar = _FakeSidecar()
    wrapper = SidecarFallbackFetcher(http, sidecar=sidecar, config=SidecarConfig(enabled=True))
    out = await wrapper.fetch("https://example.com/x")
    assert out.content == b"real article body"
    assert sidecar.calls == 0


async def test_wrapper_preserves_original_error_when_sidecar_yields_nothing():
    request = httpx.Request("GET", "https://example.com/x")
    response = httpx.Response(403, request=request, content=b"forbidden")
    http = _FakeHttp(error=httpx.HTTPStatusError("403", request=request, response=response))
    sidecar = _FakeSidecar(content=b"")
    wrapper = SidecarFallbackFetcher(http, sidecar=sidecar, config=SidecarConfig(enabled=True))
    with pytest.raises(httpx.HTTPStatusError):
        await wrapper.fetch("https://example.com/x")


def test_maybe_wrap_is_inert_when_disabled():
    http = _FakeHttp(result=_result())
    assert maybe_wrap_with_sidecar_fallback(http, config=SidecarConfig(enabled=False)) is http
