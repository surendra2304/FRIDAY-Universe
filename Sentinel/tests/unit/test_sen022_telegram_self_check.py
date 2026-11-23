"""TASK-SEN-022 — Telegram channel on /ready (Sentinel-native suite).

Pins the production gate: in production a missing Telegram channel
makes /ready report telegram_channel=false and the service DEGRADED;
outside production it does not gate (CI/dev run without Telegram
variables by design), mirroring audit_durable. The pure self-check
cases live in tests/test_sen022_telegram_self_check.py (monorepo CI);
this file covers only the endpoint wiring, which needs the full app.
"""
from __future__ import annotations

import sys

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel.apps.api import main as api_main
from sentinel.apps.api.main import app
from sentinel.config.settings import EnvironmentType
from sentinel.gatekeeper import approval_dispatcher as dispatch_mod

TOKEN = "TELEGRAM_BOT_TOKEN"
CHAT = "TELEGRAM_CHAT_ID"

def _dispatch_modules():
    """Every live copy of approval_dispatcher (see tests/repo_isolation.py).

    The monorepo suite imports ``sentinel`` through more than one sys.path
    spelling, so the module object captured at collection time can differ
    from the one check_telegram_channel's lazy import finds in sys.modules
    at call time — and the stale cache lives on the live copy, not the
    captured one (CI 2026-11-23: the captured copy's __file__ carried a
    ``tests/../`` spelling while the live copy's was the clean Sentinel/
    path, and only the live copy's _FILE_ENV_CACHE was populated). Reset
    and patch every copy: the production check reads whichever sys.modules
    holds when it runs.
    """
    mods = {dispatch_mod}
    live = sys.modules.get("sentinel.gatekeeper.approval_dispatcher")
    if live is not None:
        mods.add(live)
    return mods


def _reset_file_env_cache():
    for _mod in _dispatch_modules():
        _mod._FILE_ENV_CACHE = None


def _patch_env_file_candidates(monkeypatch, env_file):
    for _mod in _dispatch_modules():
        monkeypatch.setattr(_mod, "_env_file_candidates", lambda: [env_file])


@pytest.fixture()
def no_telegram(monkeypatch, tmp_path):
    """No Telegram credentials anywhere the dispatcher can see."""
    env_file = tmp_path / "sentinel-test.env"
    env_file.write_text("", encoding="utf-8")
    for name in (TOKEN, CHAT, "SENTINEL_TELEGRAM_BOT_TOKEN",
                 "SENTINEL_TELEGRAM_CHAT_ID", "SENTINEL_ENV_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(env_file))
    _patch_env_file_candidates(monkeypatch, env_file)
    _reset_file_env_cache()
    # No lifespan runs under ASGITransport: make sure no stale boot
    # verdict leaks in from another test.
    if hasattr(app.state, "telegram_channel_ready"):
        delattr(app.state, "telegram_channel_ready")
    yield
    _reset_file_env_cache()
    if hasattr(app.state, "telegram_channel_ready"):
        delattr(app.state, "telegram_channel_ready")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_production_ready_degrades_without_telegram(monkeypatch, no_telegram):
    monkeypatch.setattr(api_main.settings, "environment", EnvironmentType.PRODUCTION)
    monkeypatch.setattr(api_main.settings, "storage_backend", "oracle")
    async with _client() as c:
        body = (await c.get("/ready")).json()
    assert body["checks"]["telegram_channel"] is False
    assert body["ready"] is False
    assert body["status"] == "DEGRADED"
    # The invariant: ready is exactly the AND of the reported checks.
    assert body["ready"] is all(body["checks"].values())


@pytest.mark.asyncio
async def test_production_ready_reports_channel_when_configured(
    monkeypatch, no_telegram, tmp_path
):
    env_file = tmp_path / "sentinel-live.env"
    env_file.write_text(
        f"{TOKEN}=tok-test-value\n{CHAT}=chat-test-value\n", encoding="utf-8")
    monkeypatch.setenv("SENTINEL_ENV_FILE", str(env_file))
    _patch_env_file_candidates(monkeypatch, env_file)
    _reset_file_env_cache()
    monkeypatch.setattr(api_main.settings, "environment", EnvironmentType.PRODUCTION)
    async with _client() as c:
        body = (await c.get("/ready")).json()
    assert body["checks"]["telegram_channel"] is True
    assert body["ready"] is all(body["checks"].values())


@pytest.mark.asyncio
async def test_non_production_ready_does_not_gate_on_telegram(monkeypatch, no_telegram):
    monkeypatch.setattr(api_main.settings, "environment", EnvironmentType.DEVELOPMENT)
    monkeypatch.setattr(api_main.settings, "storage_backend", "memory")
    async with _client() as c:
        resp = await c.get("/ready")
        body = resp.json()
    assert resp.status_code == 200
    assert body["checks"]["telegram_channel"] is True
    assert body["status"] == "READY"


@pytest.mark.asyncio
async def test_ready_prefers_boot_time_verdict(monkeypatch, no_telegram):
    """The lifespan's verdict wins over a live re-check (and vice versa)."""
    monkeypatch.setattr(api_main.settings, "environment", EnvironmentType.PRODUCTION)
    app.state.telegram_channel_ready = True
    try:
        async with _client() as c:
            body = (await c.get("/ready")).json()
        assert body["checks"]["telegram_channel"] is True
    finally:
        delattr(app.state, "telegram_channel_ready")
    # Stashed False with the same (empty) env: the check reports down.
    app.state.telegram_channel_ready = False
    try:
        async with _client() as c:
            body = (await c.get("/ready")).json()
        assert body["checks"]["telegram_channel"] is False
    finally:
        delattr(app.state, "telegram_channel_ready")
