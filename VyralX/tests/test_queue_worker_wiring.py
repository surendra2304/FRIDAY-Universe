"""TASK-VYR-002 — the durable task queues need a consumer in production.

VyralX's task APIs persist AgentTask rows for app.worker, but no deployed
unit ran app.worker: submitted tasks sat "queued" forever (the only
consumer was the viral autopilot script's occasional drain phase). The fix
runs the worker loop inside the always-on app process — auto-enabled only
in production so test/dev imports never spawn it, with an explicit
QUEUE_WORKER_ENABLED override either way.

On clean main these tests fail: neither the setting nor the startup
wiring exists.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.main import _queue_worker_should_start


def _cfg(app_env: str, enabled):
    return SimpleNamespace(app_env=app_env, queue_worker_enabled=enabled)


def test_auto_mode_starts_only_in_production():
    assert _queue_worker_should_start(_cfg("production", None)) is True
    assert _queue_worker_should_start(_cfg("prod", None)) is True
    assert _queue_worker_should_start(_cfg("development", None)) is False
    assert _queue_worker_should_start(_cfg("test", None)) is False


def test_explicit_setting_wins_over_auto_mode():
    assert _queue_worker_should_start(_cfg("production", False)) is False
    assert _queue_worker_should_start(_cfg("development", True)) is True


def test_startup_handler_is_registered():
    from app.main import app

    handlers = [getattr(h, "__name__", "") for h in app.router.on_startup]
    assert "_start_queue_worker" in handlers


def test_setting_exists_with_auto_default():
    from app.config import Settings

    assert Settings.model_fields["queue_worker_enabled"].default is None
